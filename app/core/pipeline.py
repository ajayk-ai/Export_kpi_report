"""Orchestration: fetch sheet data -> compute KPIs -> AI summary -> format -> send.

``build_report`` is the single place the pipeline runs; both the CLI
(``run``) and the FastAPI routes call it so the console, the live web preview,
and the emailed report are always identical.
"""
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ..clients.email_client import send_summary_email
from ..clients.gemini_client import generate_summary
from ..clients.sheets_client import get_data_as_dataframe
from ..config import settings
from .kpi_engine import (
    compute_all_kpis,
    compute_country_breakup,
    latest_month,
    latest_year,
    normalize_month,
)
from .report import html_report, text_summary


@dataclass(frozen=True)
class ReportResult:
    """Everything a single pipeline run produces, ready to print/serve/email."""

    month: str
    year: int
    kpis: list[dict]
    breakup: list[dict]
    ai_summary: str
    text: str
    html: str


def build_report(
    df: pd.DataFrame | None = None,
    *,
    month: str | None = None,
    year: int | None = None,
    use_ai: bool = True,
) -> ReportResult:
    """Run the pipeline and return the full result (no email side effects).

    If ``df`` is given, it is used as the data source (handy for testing against
    a local Excel/CSV file); otherwise data is fetched from Google Sheets.
    ``month`` overrides the breakup's target month — accepts a full name, a
    3-letter abbreviation, or a number (e.g. "July"/"Jul"/"7"); when ``None`` it
    falls back to ``REPORT_MONTH`` from .env, then the latest month in the
    data. ``year`` overrides the reporting year; when ``None`` it falls back to
    ``REPORT_YEAR`` from .env, then the latest year in the data. Set
    ``use_ai=False`` to skip the Gemini call (e.g. for a fast local preview).
    """
    if df is None:
        df = get_data_as_dataframe(settings.sheet_id, settings.worksheet_name)

    # The reporting year: an explicit override, else REPORT_YEAR from .env,
    # else the latest year the planning team has entered in the sheet's Year
    # column (today's year if the column is absent/blank). Every section below
    # is scoped to it, so accumulating live data across years never merges a
    # later year's reused month labels into this report. Balance still carries
    # forward continuously from earlier years (see compute_all_kpis) — a
    # pending order never disappears just because the year rolled over.
    report_year = year if year is not None else settings.report_year
    if report_year is None:
        report_year = latest_year(df)
    kpis = compute_all_kpis(df, year=report_year)

    # Month input (arg, then REPORT_MONTH) accepts flexible formats; resolve it
    # to the canonical name the data uses. A value that doesn't match anything
    # recognizable fails loudly instead of silently matching zero rows.
    month_input = month or settings.report_month
    if month_input:
        normalized = normalize_month(month_input)
        if normalized is None:
            raise ValueError(
                f"Unrecognized month {month_input!r}. Use a full name (July), "
                "a 3-letter abbreviation (Jul), or a number (7 or 07)."
            )
        month_input = normalized

    # Label for the monthly-summary section and the email subject.
    report_month = month_input or latest_month(df, report_year)
    # The per-country breakup spans ALL months AND ALL years by default: an
    # order booked in a prior month (or a prior year) can still be
    # pending/overdue today, so scoping to `report_year` here would hide it —
    # the whole point of the report_year is to pick which year's monthly
    # summary to show, not to make older pending orders disappear. Pass an
    # explicit `month` (or set REPORT_MONTH) to scope the breakup by month.
    breakup_month = month_input or None  # None/"" -> all data
    breakup = compute_country_breakup(df, month=breakup_month)
    ai_summary = generate_summary(kpis, breakup) if use_ai else ""

    text = text_summary(kpis, breakup, ai_summary, year=report_year)
    html = html_report(kpis, breakup, ai_summary, month=breakup_month, year=report_year)
    return ReportResult(report_month, report_year, kpis, breakup, ai_summary, text, html)


def run(
    send: bool = False,
    df: pd.DataFrame | None = None,
    *,
    month: str | None = None,
    year: int | None = None,
) -> str:
    """Run the full pipeline and return the plain-text summary.

    If ``send`` is True, also email the HTML report (with the AI summary and a
    plain-text fallback) to ``EMAIL_RECIPIENT``.
    """
    result = build_report(df, month=month, year=year)

    if send:
        if not settings.email_recipient:
            raise RuntimeError("EMAIL_RECIPIENT is not set in .env.")
        # Unique subject per send so looped emails don't collapse into one thread.
        stamp = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        subject = f"{settings.email_subject} - {result.month} - {stamp}"
        send_summary_email(settings.email_recipient, subject, result.text, result.html)

    return result.text
