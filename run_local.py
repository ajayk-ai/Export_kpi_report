"""Run the KPI report against a local Excel file (no Google Sheets, no email).

Reads an .xlsx, computes the KPIs + country breakup, prints the plain-text
summary, and writes an HTML preview you can open in a browser. Use this to
validate changes before pointing the pipeline at the real Google Sheet.

Run:  uv run python run_local.py [path\\to\\data.xlsx]
Default file: data/test_data.xlsx
"""
import sys
import webbrowser
from pathlib import Path

import pandas as pd

from app.core.kpi_engine import compute_all_kpis, compute_country_breakup, latest_month
from app.core.report import html_report, text_summary

DEFAULT_FILE = Path(__file__).resolve().parent / "data" / "test_data.xlsx"
PREVIEW = Path(__file__).resolve().parent / "data" / "report_preview.html"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    if not path.exists():
        raise SystemExit(f"File not found: {path}\nRun: uv run python make_test_data.py")

    # Read every cell as text, matching how gspread's get_all_records hands the
    # sheet to the pipeline (dates stay 'DD-MM-YYYY' strings, blanks stay blank).
    df = pd.read_excel(path, dtype=str).fillna("")

    kpis = compute_all_kpis(df)
    month = latest_month(df)
    breakup = compute_country_breakup(df, month=month)

    # No AI summary here — keep the local run fully offline.
    text = text_summary(kpis, breakup, ai_summary="")
    print(text)
    print("\n--- monthly KPIs (balance must never be negative) ---")
    for k in kpis:
        flag = "  <-- NEGATIVE!" if k["balance"] < 0 or k["opening_order"] < 0 else ""
        print(
            f"{k['month']:<6} opening={k['opening_order']:>4} new={k['new_order']:>4} "
            f"total={k['total_order']:>4} despatched={k['dispatched']:>4} "
            f"balance={k['balance']:>4}{flag}"
        )

    html = html_report(kpis, breakup, ai_summary="", month=month)
    PREVIEW.write_text(html, encoding="utf-8")
    print(f"\nHTML preview written to: {PREVIEW}")
    try:
        webbrowser.open(PREVIEW.as_uri())
    except Exception:
        pass


if __name__ == "__main__":
    main()
