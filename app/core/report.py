"""Render KPIs as plain text and as an HTML email report.

The HTML breakup table mirrors the SUMMARY sheet layout: a yellow date banner
and a pink "Commitment not Given – Over Due days" band over a 3-row header,
followed by a Sub Total row.
"""
from datetime import date, datetime
from html import escape
from urllib.parse import urlencode

from ..config import settings
from .kpi_engine import DATE_FORMAT

# Brand-ish palette (inline styles are required for email clients).
_HEADER_BG = "#1f2937"      # slate
_ACCENT = "#2563eb"         # blue
_AI_BG = "#eff6ff"          # light blue
_POS = "#16a34a"            # green
_NEG = "#dc2626"            # red
_ROW_ALT = "#f9fafb"        # light grey
_BORDER = "#e5e7eb"

# Sheet-matching bands for the breakup table.
_BANNER_YELLOW = "#ffe599"
_HDR_YELLOW = "#fff2cc"
_BANNER_PINK = "#f4cccc"
_HDR_PINK = "#fce4e4"
_GRID = "#c9c9c9"


def _report_date() -> str:
    """Today as e.g. '7-Jul-2026' to match the sheet's date banner."""
    today = date.today()
    return f"{today.day}-{today:%b}-{today.year}"


# --------------------------------------------------------------------------- #
# Plain text (email fallback + console)
# --------------------------------------------------------------------------- #
def text_summary(
    kpis: list[dict],
    breakup: list[dict] | None = None,
    ai_summary: str = "",
) -> str:
    """Plain-text version, used as the email fallback and for console output.

    Shows every month's KPI line so the opening/balance carry-forward trend is
    visible; the breakup below is already scoped to its target month.
    """
    lines = [
        f"{k['month']}: "
        f"Opening={k['opening_order']}, "
        f"New={k['new_order']}, "
        f"Total={k['total_order']}, "
        f"Despatched={k['dispatched']}, "
        f"Balance={k['balance']}"
        for k in kpis
    ]
    body = "\n".join(lines)
    if ai_summary:
        body = f"AI Summary:\n{ai_summary}\n\n{body}"
    if breakup:
        body = f"{body}\n\n{_breakup_text(breakup)}"
    return body


def _breakup_text(breakup: list[dict]) -> str:
    """Plain-text version of the per-country overdue breakup, with a subtotal."""
    header = f"Overdue Breakup by Country ({_report_date()}) - Commitment not Given:"
    lines = [header]
    totals = _subtotals(breakup)
    for b in breakup:
        lines.append(
            f"- {b['country']}: Pending={b['pending_orders']}, "
            f"OverDue={b['over_due_breakup']}, "
            f"DaysDelay={b['days_delay']}, "
            f"NewCommitted={b['new_committed_date'] or '-'}, "
            f"ContainerExpected={b['container_expected_date'] or '-'}, "
            f"VesselCutOff={b['vessel_cutoff'] or '-'}, "
            f"Prdn(pending={b['prdn_machines_pending']}, "
            f"changes={b['prdn_commitment_changes']}), "
            f"Container(pending={b['container_machines_pending']}, "
            f"changes={b['container_commitment_changes']}), "
            f"ClearancePending={b['clearance_pending']}"
        )
    lines.append(
        f"- SUB TOTAL: Pending={totals['pending_orders']}, "
        f"OverDue={totals['over_due_breakup']}, "
        f"Prdn(pending={totals['prdn_machines_pending']}), "
        f"Container(pending={totals['container_machines_pending']}), "
        f"ClearancePending={totals['clearance_pending']}"
    )
    return "\n".join(lines)


# Count-based columns that total in the Sub Total row. Average columns
# (days_delay, *_commitment_changes) and date columns are not summed.
_SUM_KEYS = (
    "pending_orders",
    "over_due_breakup",
    "prdn_machines_pending",
    "container_machines_pending",
    "clearance_pending",
)


def _subtotals(breakup: list[dict]) -> dict:
    return {key: sum(int(b[key]) for b in breakup) for key in _SUM_KEYS}


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
def _balance_color(value: int) -> str:
    return _NEG if value < 0 else _POS


def _kpi_rows_html(kpis: list[dict]) -> str:
    cells = []
    for i, k in enumerate(kpis):
        bg = _ROW_ALT if i % 2 else "#ffffff"
        balance_color = _balance_color(k["balance"])
        cells.append(
            f'<tr style="background:{bg};">'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};font-weight:600;">{escape(str(k["month"]))}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};text-align:right;">{k["opening_order"]}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};text-align:right;">{k["new_order"]}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};text-align:right;">{k["total_order"]}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};text-align:right;">{k["dispatched"]}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {_BORDER};text-align:right;font-weight:700;color:{balance_color};">{k["balance"]}</td>'
            f"</tr>"
        )
    return "".join(cells)


def _summary_table_html(kpis: list[dict]) -> str:
    header_cell = (
        'style="padding:10px 14px;text-align:right;color:#ffffff;'
        'font-weight:600;font-size:13px;"'
    )
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:26px;">
      <thead>
        <tr style="background:{_ACCENT};">
          <th style="padding:10px 14px;text-align:left;color:#ffffff;font-weight:600;font-size:13px;">Month</th>
          <th {header_cell}>Opening Order</th>
          <th {header_cell}>New Order</th>
          <th {header_cell}>Total Order</th>
          <th {header_cell}>Despatched</th>
          <th {header_cell}>Balance</th>
        </tr>
      </thead>
      <tbody>
        {_kpi_rows_html(kpis)}
      </tbody>
    </table>"""


def _ai_body_html(ai_summary: str) -> str:
    """Render the AI summary: '- ' lines as bullets, 'Key Takeaway:' highlighted."""
    bullets, takeaway, other = [], "", []
    for raw in ai_summary.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("key takeaway"):
            takeaway = line.split(":", 1)[1].strip() if ":" in line else line
        elif line[0] in "-•*":
            bullets.append(line.lstrip("-•* ").strip())
        else:
            other.append(line)

    parts = []
    if other:
        parts.append(
            f'<div style="color:#374151;line-height:1.5;margin-bottom:8px;">{escape(" ".join(other))}</div>'
        )
    if bullets:
        items = "".join(
            f'<li style="margin:4px 0;">{escape(b)}</li>' for b in bullets
        )
        parts.append(
            f'<ul style="margin:6px 0 0 0;padding-left:20px;color:#374151;line-height:1.5;">{items}</ul>'
        )
    if takeaway:
        parts.append(
            f'<div style="margin-top:12px;padding:8px 12px;background:#dbeafe;'
            f'border-radius:4px;color:#1e3a8a;font-weight:600;">💡 Key Takeaway: {escape(takeaway)}</div>'
        )
    return "".join(parts)


def _ai_section_html(ai_summary: str) -> str:
    if not ai_summary:
        return ""
    return (
        f'<div style="background:{_AI_BG};border-left:4px solid {_ACCENT};'
        f'padding:14px 18px;margin:0 0 22px 0;border-radius:6px;">'
        f'<div style="font-weight:700;color:{_ACCENT};margin-bottom:6px;">🤖 AI Summary (Gemini)</div>'
        f"{_ai_body_html(ai_summary)}"
        f"</div>"
    )


# Shared cell styling for the sheet-like breakup grid.
_TH = f"border:1px solid {_GRID};padding:6px 8px;font-size:11px;color:#1f2937;"
_TD = f"border:1px solid {_GRID};padding:6px 8px;font-size:12px;text-align:center;"
_TD_LEFT = f"border:1px solid {_GRID};padding:6px 8px;font-size:12px;font-weight:600;"


def _num(value: int, *, blank_zero: bool = True) -> str:
    """A number for a data cell — blank instead of 0 to match the sheet look."""
    return "" if (blank_zero and int(value) == 0) else str(int(value))


def _avg_num(value: float) -> str:
    """An average for a data cell — whole number, blank instead of 0."""
    v = round(float(value))
    if v == 0:
        return ""
    return str(v)


def _parse_date(value: str):
    """Parse a ``DD-MM-YYYY`` sheet date string; ``None`` if blank/unparseable."""
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        return None


def _days_delay_style(days_delay: float) -> str:
    """Red when the average loading-commitment changes reach 5+."""
    return f"color:{_NEG};font-weight:700;" if float(days_delay) >= 5 else ""


def _missed_date_style(value: str) -> str:
    """Red when a committed/expected date has already passed; today or later is fine."""
    parsed = _parse_date(value)
    return f"color:{_NEG};font-weight:700;" if parsed and parsed < date.today() else ""


def _machines_pending_style(value: int) -> str:
    """Red when more than 5 machines are pending."""
    return f"color:{_NEG};font-weight:700;" if int(value) > 5 else ""


def _vessel_cutoff_style(value: str) -> str:
    """Red when the vessel cut-off is within 3 days of today (either side)."""
    parsed = _parse_date(value)
    if parsed and abs((parsed - date.today()).days) <= 3:
        return f"color:{_NEG};font-weight:700;"
    return ""


def _over_due_cell(country: str, over: int) -> str:
    """The Over Due Breakup value, linked to the country's filtered sheet view.

    Clicking it opens the Apps Script Web App (see appscript/CountryFilterLink.gs),
    which filters the sheet down to that country and redirects the browser there.
    Renders as plain text if FILTER_WEBAPP_URL isn't configured.
    """
    if not settings.filter_webapp_url:
        return str(over)
    href = f"{settings.filter_webapp_url}?{urlencode({'country': country})}"
    return f'<a href="{escape(href)}" style="color:inherit;text-decoration:underline;">{over}</a>'


def _breakup_rows_html(breakup: list[dict]) -> str:
    rows = []
    for i, b in enumerate(breakup):
        bg = _ROW_ALT if i % 2 else "#ffffff"
        over = int(b["over_due_breakup"])
        over_color = _NEG if over > 0 else "#1f2937"
        rows.append(
            f'<tr style="background:{bg};">'
            f'<td style="{_TD_LEFT}">{escape(b["country"])}</td>'
            f'<td style="{_TD}font-weight:700;color:{over_color};">{_over_due_cell(b["country"], over)}</td>'
            f'<td style="{_TD}{_days_delay_style(b["days_delay"])}">{_avg_num(b["days_delay"])}</td>'
            f'<td style="{_TD}{_missed_date_style(b["new_committed_date"])}">{escape(b["new_committed_date"])}</td>'
            f'<td style="{_TD}{_missed_date_style(b["container_expected_date"])}">{escape(b["container_expected_date"])}</td>'
            f'<td style="{_TD}{_machines_pending_style(b["prdn_machines_pending"])}">{_num(b["prdn_machines_pending"])}</td>'
            f'<td style="{_TD}">{_avg_num(b["prdn_commitment_changes"])}</td>'
            f'<td style="{_TD}{_machines_pending_style(b["container_machines_pending"])}">{_num(b["container_machines_pending"])}</td>'
            f'<td style="{_TD}">{_avg_num(b["container_commitment_changes"])}</td>'
            f'<td style="{_TD}{_vessel_cutoff_style(b["vessel_cutoff"])}">{escape(b["vessel_cutoff"])}</td>'
            f'<td style="{_TD}">{_num(b["clearance_pending"])}</td>'
            f"</tr>"
        )
    return "".join(rows)


def _breakup_subtotal_html(breakup: list[dict]) -> str:
    t = _subtotals(breakup)
    sub_td = f"{_TD}font-weight:700;background:{_HDR_YELLOW};"
    return (
        f"<tr>"
        f'<td style="{_TD_LEFT}background:{_HDR_YELLOW};">Sub Total</td>'
        f'<td style="{sub_td}color:{_NEG};">{t["over_due_breakup"]}</td>'
        f'<td style="{sub_td}"></td>'  # Days Delay (average, not summed)
        f'<td style="{sub_td}"></td>'  # New Committed Date (dates don't total)
        f'<td style="{sub_td}"></td>'  # Container Expected Date
        f'<td style="{sub_td}">{t["prdn_machines_pending"]}</td>'
        f'<td style="{sub_td}"></td>'  # Prdn commitment changes (average)
        f'<td style="{sub_td}">{t["container_machines_pending"]}</td>'
        f'<td style="{sub_td}"></td>'  # Container commitment changes (average)
        f'<td style="{sub_td}"></td>'  # Vessel Cut off
        f'<td style="{sub_td}">{t["clearance_pending"]}</td>'
        f"</tr>"
    )


def _breakup_section_html(breakup: list[dict]) -> str:
    if not breakup:
        return ""
    yellow_banner = f"{_TH}background:{_BANNER_YELLOW};font-weight:700;font-size:13px;text-align:center;"
    pink_banner = f"{_TH}background:{_BANNER_PINK};font-weight:700;font-size:13px;text-align:center;"
    y = f"{_TH}background:{_HDR_YELLOW};font-weight:600;text-align:center;vertical-align:middle;"
    p = f"{_TH}background:{_HDR_PINK};font-weight:600;text-align:center;vertical-align:middle;"
    return f"""
    <div style="overflow-x:auto;">
    <table style="border-collapse:collapse;font-family:Segoe UI,Roboto,Arial,sans-serif;">
      <thead>
        <tr>
          <th colspan="5" style="{yellow_banner}">{_report_date()}</th>
          <th colspan="6" style="{pink_banner}">Commitment not Given - Over Due days</th>
        </tr>
        <tr>
          <th rowspan="2" style="{y}text-align:left;">Breakup - Dealer / Customer</th>
          <th rowspan="2" style="{y}">Over Due Breakup</th>
          <th rowspan="2" style="{y}">No of Days Delay from 1st Committment</th>
          <th rowspan="2" style="{y}">New Committed Date</th>
          <th rowspan="2" style="{y}">Container Expected Date</th>
          <th colspan="2" style="{p}">Prdn Committment Pending</th>
          <th colspan="2" style="{p}">Container Committment Pending</th>
          <th rowspan="2" style="{p}">Vessel Cut off</th>
          <th rowspan="2" style="{p}">Commerical Clearance no of Pending</th>
        </tr>
        <tr>
          <th style="{p}">No of machines</th>
          <th style="{p}">No of commitment changes</th>
          <th style="{p}">No of machines</th>
          <th style="{p}">No of commitment changes</th>
        </tr>
      </thead>
      <tbody>
        {_breakup_rows_html(breakup)}
        {_breakup_subtotal_html(breakup)}
      </tbody>
    </table>
    </div>"""


def html_report(
    kpis: list[dict],
    breakup: list[dict] | None = None,
    ai_summary: str = "",
    month: str | None = None,
) -> str:
    """A self-contained, inline-styled HTML report suitable for email."""
    return f"""\
<div style="font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:1100px;margin:0 auto;color:#111827;">
  <div style="background:{_HEADER_BG};padding:22px 24px;border-radius:8px 8px 0 0;">
    <div style="color:#ffffff;font-size:20px;font-weight:700;">Export KPI Report</div>
    <div style="color:#9ca3af;font-size:13px;margin-top:4px;">Generated on {date.today():%d %b %Y}</div>
  </div>
  <div style="border:1px solid {_BORDER};border-top:none;border-radius:0 0 8px 8px;padding:24px;">
    {_ai_section_html(ai_summary)}
    {_summary_table_html(kpis)}
    {_breakup_section_html(breakup or [])}
    <div style="color:#9ca3af;font-size:12px;margin-top:18px;">
      Balance = Total Order − Despatched. Over Due Breakup and the commitment
      columns cover {escape(month) if month else "all months, as of today"}.
    </div>
  </div>
</div>"""
