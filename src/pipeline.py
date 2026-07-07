"""Orchestration: fetch sheet data -> compute KPIs -> AI summary -> format -> send."""
from datetime import datetime

from .config import settings
from .email_client import send_summary_email
from .gemini_client import generate_summary
from .kpi_engine import compute_all_kpis, compute_country_breakup, latest_month
from .report import html_report, text_summary
from .sheets_client import get_data_as_dataframe


def run(send: bool = False) -> str:
    """Run the full pipeline and return the plain-text summary.

    If ``send`` is True, also email an HTML report (with an AI summary and a
    plain-text fallback) to ``EMAIL_RECIPIENT``.
    """
    df = get_data_as_dataframe(settings.sheet_id, settings.worksheet_name)
    kpis = compute_all_kpis(df)
    # Breakup is filtered to REPORT_MONTH from .env, or the latest month in the
    # data when that's blank.
    month = settings.report_month or latest_month(df)
    breakup = compute_country_breakup(df, month=month)
    ai_summary = generate_summary(kpis, breakup)

    text = text_summary(kpis, breakup, ai_summary, month=month)

    if send:
        if not settings.email_recipient:
            raise RuntimeError("EMAIL_RECIPIENT is not set in .env.")
        html = html_report(kpis, breakup, ai_summary, month=month)
        # Unique subject per send so looped emails don't collapse into one thread.
        stamp = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        subject = f"{settings.email_subject} - {month} - {stamp}"
        send_summary_email(settings.email_recipient, subject, text, html)

    return text
