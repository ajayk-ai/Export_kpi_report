"""Generate a local Excel test file that mimics the SCM_Export sheet.

Writes ``data/test_data.xlsx`` with a MAY / JUNE / JULY scenario so the pipeline
can be exercised offline before touching the real Google Sheet. There is NO
"Order Type (N / O)" column any more — every order line simply counts in the
month it belongs to, and an order is "open" (still pending) when its
Loading (Dispatched) Date is blank/Pending.

Run:  uv run python make_test_data.py
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "data" / "test_data.xlsx"

# Column names must match kpi_engine's COL_* constants exactly.
COLUMNS = [
    "Country",
    "Month",
    "Quantity",
    "Machine Revision Date",       # -> New Committed Date
    "no of times commitment changes(prod)",
    "Container Placement date",
    "Container Revision Date",     # -> Container Expected Date (latest of the two)
    "no of comm container changes",
    "Loading (Dispatched) Date",   # blank/Pending = still open
    "over due days",               # > 0 = overdue row
    "Vessel Cut-Off Date",
    "Commercial Clearance Status",
]

# Handy shorthand for a fully-shipped, on-time, cleared line (not overdue, not open).
def shipped(country, month, qty, loading):
    return {
        "Country": country,
        "Month": month,
        "Quantity": qty,
        "Machine Revision Date": "",
        "no of times commitment changes(prod)": 0,
        "Container Placement date": "",
        "Container Revision Date": "",
        "no of comm container changes": 0,
        "Loading (Dispatched) Date": loading,
        "over due days": 0,
        "Vessel Cut-Off Date": "",
        "Commercial Clearance Status": "Completed",
    }


# An open, overdue line for the July "Commitment not Given" breakup. Loading is
# left blank (Pending) so it stays an open order and feeds the balance.
def overdue(country, qty, days, committed, container_exp, vessel, prdn_chg,
            cont_chg, clearance="Pending"):
    return {
        "Country": country,
        "Month": "JULY",
        "Quantity": qty,
        "Machine Revision Date": committed,
        "no of times commitment changes(prod)": prdn_chg,
        "Container Placement date": container_exp,
        "Container Revision Date": container_exp,
        "no of comm container changes": cont_chg,
        "Loading (Dispatched) Date": "",  # Pending -> open order
        "over due days": days,
        "Vessel Cut-Off Date": vessel,
        "Commercial Clearance Status": clearance,
    }


rows = [
    # ---- MAY: everything shipped, clean opening (balance stays small) ----
    shipped("USA", "MAY", 20, "10-05-2026"),
    shipped("MEXICO", "MAY", 15, "12-05-2026"),
    shipped("BRAZIL", "MAY", 10, "18-05-2026"),
    shipped("COLOMBIA", "MAY", 8, ""),           # one still open -> carries forward

    # ---- JUNE: most shipped, a couple carry forward ----
    shipped("USA", "JUNE", 18, "09-06-2026"),
    shipped("COLOMBIA", "JUNE", 12, "15-06-2026"),
    shipped("PERU", "JUNE", 9, "20-06-2026"),
    shipped("CHILE", "JUNE", 7, ""),             # open -> carries forward
    shipped("MEXICO", "JUNE", 6, ""),            # open -> carries forward
    shipped("BRAZIL", "JUNE", 5, "10-07-2026"),  # JUNE order, loaded in JULY ->
    #                                              slipped to next month -> PENDING

    # ---- JULY: new orders, several still open & overdue (breakup section) ----
    # Mix so the report's red rules are all exercised:
    #   days_delay >= 5 -> red ; committed/expected date < today (11-07-2026) -> red ;
    #   vessel cut-off within 3 days of today -> red ; machines pending > 5 -> red.
    shipped("USA", "JULY", 12, "05-07-2026"),    # loaded in the past -> dispatched
    shipped("USA", "JULY", 6, "15-07-2026"),     # loaded AFTER today (11-07) ->
    #                                              future dispatch -> PENDING
    overdue("USA", 8, 8, "26-06-2026", "05-07-2026", "12-07-2026", 34, 28),
    overdue("COLOMBIA", 19, 7, "26-06-2026", "06-07-2026", "12-07-2026", 24, 24),
    overdue("MEXICO", 8, 4, "15-07-2026", "16-07-2026", "16-07-2026", 12, 9),  # not-red cases
    overdue("PERU", 10, 6, "28-06-2026", "09-07-2026", "14-07-2026", 25, 9),
    overdue("CHILE", 5, 9, "26-06-2026", "05-07-2026", "12-07-2026", 22, 21),
    overdue("BRAZIL", 4, 6, "26-06-2026", "07-07-2026", "13-07-2026", 13, 19),
]

df = pd.DataFrame(rows, columns=COLUMNS)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(OUT, index=False, sheet_name="SCM_Export_Orders")
print(f"Wrote {len(df)} rows to {OUT}")
