"""HTTP endpoints for the Export KPI report.

The star of the show is ``GET /report``: it runs the exact same pipeline as the
email and returns the identical HTML template, so you can eyeball the live
report in a browser against the real Google Sheet before anything is emailed.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from ..config import settings
from ..core.data_source import load
from ..core.pipeline import build_report

router = APIRouter()

SourceParam = Query("sheet", pattern="^(sheet|local)$", description="Data source")


@router.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse, tags=["meta"])
def index() -> str:
    """A tiny landing page linking to the live report and JSON."""
    return f"""\
<!doctype html><meta charset="utf-8">
<title>Export KPI Automation</title>
<style>
  body{{font-family:Segoe UI,Roboto,Arial,sans-serif;max-width:640px;margin:48px auto;color:#111827;padding:0 16px;}}
  a{{color:#2563eb;}} code{{background:#f3f4f6;padding:2px 6px;border-radius:4px;}}
  li{{margin:8px 0;}}
</style>
<h1>Export KPI Automation</h1>
<p>Live report endpoints (the <code>/report</code> HTML is the exact email template):</p>
<ul>
  <li><a href="/report?source=sheet">/report?source=sheet</a> — live report from Google Sheets</li>
  <li><a href="/report?source=local">/report?source=local</a> — from local <code>data/test_data.xlsx</code> (offline)</li>
  <li><a href="/report?source=local&amp;ai=false">/report?source=local&amp;ai=false</a> — skip the AI summary (fast)</li>
  <li><a href="/report.json?source=local">/report.json?source=local</a> — raw KPI + breakup JSON</li>
  <li><a href="/docs">/docs</a> — interactive API docs</li>
</ul>
<p>Filter the breakup month with <code>&amp;month=july</code> (name, abbreviation, or
number all work) and pick a reporting year with <code>&amp;year=2027</code>.
Email a send with <code>POST /send</code>.</p>"""


@router.get("/report", response_class=HTMLResponse, tags=["report"])
def report_html(
    source: str = SourceParam,
    month: str | None = Query(None, description="Breakup month: name, abbreviation, or number; blank = latest"),
    year: int | None = Query(None, description="Reporting year, e.g. 2027; blank = latest in data"),
    ai: bool = Query(True, description="Include the Gemini AI summary"),
) -> HTMLResponse:
    """The live HTML report — identical to what gets emailed."""
    try:
        df = load(source)
        result = build_report(df, month=month, year=year, use_ai=ai)
    except Exception as exc:  # noqa: BLE001 - surface a readable page, not a stack trace
        return HTMLResponse(_error_html(exc, source), status_code=502)
    return HTMLResponse(result.html)


@router.get("/report.json", tags=["report"])
def report_json(
    source: str = SourceParam,
    month: str | None = Query(None),
    year: int | None = Query(None),
    ai: bool = Query(False),
) -> JSONResponse:
    """The report data (KPIs + per-country breakup) as JSON."""
    try:
        df = load(source)
        result = build_report(df, month=month, year=year, use_ai=ai)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(
        {
            "month": result.month,
            "year": result.year,
            "kpis": result.kpis,
            "breakup": result.breakup,
            "ai_summary": result.ai_summary,
        }
    )


@router.post("/send", tags=["report"])
def send_report(
    source: str = SourceParam,
    month: str | None = Query(None),
    year: int | None = Query(None),
    recipient: str | None = Query(None, description="Override EMAIL_RECIPIENT"),
    ai: bool = Query(True),
) -> dict:
    """Compute the report and email it (to ``recipient`` or ``EMAIL_RECIPIENT``)."""
    to = recipient or settings.email_recipient
    if not to:
        raise HTTPException(status_code=400, detail="No recipient set (EMAIL_RECIPIENT).")
    try:
        from ..clients.email_client import send_summary_email

        df = load(source)
        result = build_report(df, month=month, year=year, use_ai=ai)
        stamp = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        subject = f"{settings.email_subject} - {result.month} - {stamp}"
        send_summary_email(to, subject, result.text, result.html)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"sent": True, "recipient": to, "month": result.month}


def _error_html(exc: Exception, source: str) -> str:
    hint = (
        "Try <a href='/report?source=local'>?source=local</a> to preview against "
        "the bundled test data without Google Sheets."
        if source == "sheet"
        else "Run <code>python make_test_data.py</code> to create the local test file."
    )
    from html import escape

    return f"""\
<!doctype html><meta charset="utf-8"><title>Report error</title>
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:48px auto;color:#111827;">
  <h2 style="color:#dc2626;">Could not build the report</h2>
  <p><b>Source:</b> {escape(source)}</p>
  <pre style="background:#f3f4f6;padding:12px;border-radius:6px;white-space:pre-wrap;">{escape(str(exc))}</pre>
  <p>{hint}</p>
</div>"""
