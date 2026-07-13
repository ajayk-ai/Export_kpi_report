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
from .kpi_engine import compute_all_kpis, compute_country_breakup, latest_month
from .report import html_report, text_summary


@dataclass(frozen=True)
class ReportResult:
    """Everything a single pipeline run produces, ready to print/serve/email."""

    month: str
    kpis: list[dict]
    breakup: list[dict]
    ai_summary: str
    text: str
    html: str


def build_report(
    df: pd.DataFrame | None = None,
    *,
    month: str | None = None,
    use_ai: bool = True,
) -> ReportResult:
    """Run the pipeline and return the full result (no email side effects).

    If ``df`` is given, it is used as the data source (handy for testing against
    a local Excel/CSV file); otherwise data is fetched from Google Sheets.
    ``month`` overrides the breakup's target month; when ``None`` it falls back
    to ``REPORT_MONTH`` from .env, then the latest month in the data. Set
    ``use_ai=False`` to skip the Gemini call (e.g. for a fast local preview).
    """
    if df is None:
        df = get_data_as_dataframe(settings.sheet_id, settings.worksheet_name)

    kpis = compute_all_kpis(df)
    # Label for the monthly-summary section and the email subject.
    report_month = month or settings.report_month or latest_month(df)
    # The per-country breakup spans ALL months by default: an order booked in a
    # prior month can still be pending/overdue today, so scoping to one month
    # would hide it. Pass an explicit `month` (or set REPORT_MONTH) to scope it.
    breakup_month = month or settings.report_month or None  # None/"" -> all data
    breakup = compute_country_breakup(df, month=breakup_month)
    ai_summary = generate_summary(kpis, breakup) if use_ai else ""

    text = text_summary(kpis, breakup, ai_summary)
    html = html_report(kpis, breakup, ai_summary, month=breakup_month)
    return ReportResult(report_month, kpis, breakup, ai_summary, text, html)


def run(send: bool = False, df: pd.DataFrame | None = None) -> str:
    """Run the full pipeline and return the plain-text summary.

    If ``send`` is True, also email the HTML report (with the AI summary and a
    plain-text fallback) to ``EMAIL_RECIPIENT``.
    """
    result = build_report(df)

    if send:
        if not settings.email_recipient:
            raise RuntimeError("EMAIL_RECIPIENT is not set in .env.")
        # Unique subject per send so looped emails don't collapse into one thread.
        stamp = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        subject = f"{settings.email_subject} - {result.month} - {stamp}"
        send_summary_email(settings.email_recipient, subject, result.text, result.html)

    return result.text
