"""Generate the SCM_Export KPI test-case dataset (50 rows, full 23-column schema).

Data is kept *consistent per model*: every Model maps to one Dealer and one FOB
Price (see ``MODELS``), so the same model always looks the same across rows.

Every row is crafted against a "today" of 13-Jul-2026 (dates before that are
overdue; dates after are still fine). The JULY rows drive the per-country
breakup; MAY/JUNE feed the monthly Opening/New/Total/Despatched/Balance
carry-forward.

Run:
    uv run python make_test_data.py            # write data/test_data.xlsx only
    uv run python make_test_data.py --push     # ALSO overwrite the Google Sheet
                                               # (clears the target worksheet first!)
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "data" / "test_data.xlsx"

# Exact headers of the SCM_Export_Orders sheet (note the lowercase
# 'actual_container' and the double space in 'commitment loading  changes').
COLUMNS = [
    "Month",
    "Country",
    "Dealer",
    "Model",
    "Quantity",
    "Serial Number",
    "FOB Price",
    "production commitment Date",
    "production commitment Revise Date",     # past -> Production Overdue
    "no of times commitment changes(prod)",  # -> Prdn commitment changes (avg)
    "Production Completion Date",             # blank -> Prdn machines pending
    "backlog days",
    "Container Placement date",              # blank -> Container machines pending; -> Container Expected Date
    "Container Revision Date",               # past -> Container Overdue
    "actual_container",
    "no of comm container changes",          # -> Container commitment changes (avg)
    "commitment of loading date",            # blank/past -> Overdue Breakup
    "revision commitment of loading date",   # -> New Committed Date (max); past -> Pending Orders
    "no of commitment loading  changes",     # -> Days Delay from 1st Commitment (avg)
    "Loading (Dispatched) Date",             # blank -> Pending Orders
    "over due days",
    "Vessel Cut-Off Date",                   # -> Vessel Cut-Off (max)
    "Commercial Clearance Status",           # "Pending"/blank -> Clearance Pending
    # Reporting year the row belongs to. Appended LAST on purpose: the onEdit
    # Apps Script (appscript/code.gs) addresses columns by number, so inserting
    # this mid-sheet would shift them. The planning team fills it per row; the
    # report auto-scopes to the latest year present (see kpi_engine.latest_year).
    "Year",
]

# Model -> (Dealer, FOB Price). One source of truth so a model's dealer/price is
# identical on every row that uses it.
MODELS = {
    "X200": ("Atlas Machinery", 42000),
    "X250": ("Atlas Machinery", 46000),
    "Z100": ("Atlas Machinery", 39000),
    "G90":  ("Rhein Traktor", 51000),
    "G120": ("Rhein Traktor", 55000),
    "H70":  ("Bharat Agri", 33000),
    "H80":  ("Bharat Agri", 35000),
    "B45":  ("Amazonia Equip", 29000),
    "B60":  ("Amazonia Equip", 32000),
    "K30":  ("Savannah Motors", 27000),
    "K35":  ("Savannah Motors", 31000),
    "J55":  ("Sakura Heavy", 60000),
    "J60":  ("Sakura Heavy", 64000),
}


def _row(month, country, model, qty, *, year=2026, readiness="", machine_revision="",
         prdn_changes=0, production_completion="", backlog=0,
         container_placement="", container_revision="", actual_container="",
         container_changes=0, commitment_loading="", revision_commitment_loading="",
         loading_changes=0, loading="", overdue_days=0, vessel="",
         clearance="Completed"):
    # Dealer + FOB come from the model catalog, never passed per row.
    dealer, fob = MODELS[model]
    return {
        "Month": month,
        "Country": country,
        "Dealer": dealer,
        "Model": model,
        "Quantity": qty,
        "Serial Number": "",  # filled sequentially in build_dataframe
        "FOB Price": fob,
        "production commitment Date": readiness,
        "production commitment Revise Date": machine_revision,
        "no of times commitment changes(prod)": prdn_changes,
        "Production Completion Date": production_completion,
        "backlog days": backlog,
        "Container Placement date": container_placement,
        "Container Revision Date": container_revision,
        "actual_container": actual_container,
        "no of comm container changes": container_changes,
        "commitment of loading date": commitment_loading,
        "revision commitment of loading date": revision_commitment_loading,
        "no of commitment loading  changes": loading_changes,
        "Loading (Dispatched) Date": loading,
        "over due days": overdue_days,
        "Vessel Cut-Off Date": vessel,
        "Commercial Clearance Status": clearance,
        "Year": year,
    }


def _days_before(date_str: str, days: int) -> str:
    """``date_str`` (DD-MM-YYYY) shifted back by ``days`` days."""
    return (datetime.strptime(date_str, "%d-%m-%Y") - timedelta(days=days)).strftime("%d-%m-%Y")


def _shipped(month, country, model, qty, loading):
    """A clean, fully-dispatched line (only feeds the monthly summary)."""
    return _row(month, country, model, qty, loading=loading,
                readiness=_days_before(loading, 5),
                production_completion=loading, container_placement=loading,
                commitment_loading="31-12-2026", clearance="Completed")


# --------------------------------------------------------------------------- #
# The scenario. "today" = 13-07-2026.
# --------------------------------------------------------------------------- #
ROWS = [
    # ===== MAY: shipped baseline; one open line carries forward ==============
    _row("MAY", "BRAZIL", "B45", 8, loading="", readiness="05-05-2026", clearance="Pending"),  # open -> carries
    _shipped("MAY", "USA", "X200", 20, "10-05-2026"),
    _shipped("MAY", "GERMANY", "G90", 15, "12-05-2026"),
    _shipped("MAY", "INDIA", "H70", 10, "18-05-2026"),
    _shipped("MAY", "USA", "X250", 8, "08-05-2026"),
    _shipped("MAY", "GERMANY", "G120", 6, "14-05-2026"),
    _shipped("MAY", "INDIA", "H80", 9, "20-05-2026"),
    _shipped("MAY", "MEXICO", "Z100", 11, "09-05-2026"),
    _shipped("MAY", "CHILE", "B60", 7, "16-05-2026"),
    _shipped("MAY", "PERU", "K35", 5, "22-05-2026"),
    _shipped("MAY", "JAPAN", "J60", 4, "25-05-2026"),
    _shipped("MAY", "NIGERIA", "H70", 6, "28-05-2026"),
    _shipped("MAY", "SPAIN", "G90", 5, "11-05-2026"),
    _shipped("MAY", "CANADA", "X200", 9, "13-05-2026"),
    _shipped("MAY", "VIETNAM", "J60", 4, "27-05-2026"),

    # ===== JUNE: mostly shipped, two carry forward ===========================
    _row("JUNE", "GERMANY", "G90", 7, loading="", readiness="24-06-2026"),   # open -> carries
    _row("JUNE", "BRAZIL", "B45", 6, loading="", readiness="26-06-2026"),    # open -> carries
    _shipped("JUNE", "USA", "X200", 18, "09-06-2026"),
    _shipped("JUNE", "KENYA", "K30", 12, "15-06-2026"),
    _shipped("JUNE", "JAPAN", "J55", 9, "20-06-2026"),
    _shipped("JUNE", "USA", "X200", 10, "07-06-2026"),
    _shipped("JUNE", "INDIA", "H70", 7, "18-06-2026"),
    _shipped("JUNE", "MEXICO", "Z100", 9, "10-06-2026"),
    _shipped("JUNE", "CHILE", "B45", 6, "15-06-2026"),
    _shipped("JUNE", "PERU", "K30", 8, "19-06-2026"),
    _shipped("JUNE", "EGYPT", "G120", 5, "23-06-2026"),
    _shipped("JUNE", "VIETNAM", "J55", 4, "26-06-2026"),
    _shipped("JUNE", "NIGERIA", "H80", 6, "14-06-2026"),
    _shipped("JUNE", "SPAIN", "G120", 5, "21-06-2026"),
    _shipped("JUNE", "CANADA", "Z100", 7, "24-06-2026"),
    _shipped("JUNE", "KENYA", "K35", 5, "17-06-2026"),

    # ===== JULY: the breakup month; each country a distinct KPI profile ======
    # USA: heavy overdue, mix of past/future so overdue is a subset of pending.
    _row("JULY", "USA", "X200", 10, loading="", commitment_loading="26-06-2026",
         loading_changes=6, revision_commitment_loading="10-07-2026",
         production_completion="", prdn_changes=30, machine_revision="05-07-2026",
         readiness="28-06-2026", container_placement="08-07-2026", container_changes=25,
         container_revision="06-07-2026", vessel="14-07-2026",
         overdue_days=17, clearance="Pending"),
    _row("JULY", "USA", "X250", 6, loading="", commitment_loading="28-06-2026",
         loading_changes=8, revision_commitment_loading="16-07-2026",
         production_completion="", prdn_changes=40, machine_revision="20-07-2026",
         readiness="30-06-2026", container_placement="", container_changes=21,
         container_revision="25-07-2026", vessel="30-07-2026",
         overdue_days=15, clearance="Completed"),

    # GERMANY: fully clean — everything committed in the future / done.
    _row("JULY", "GERMANY", "G90", 12, loading="20-07-2026",
         commitment_loading="25-07-2026", loading_changes=0,
         revision_commitment_loading="", production_completion="10-07-2026",
         prdn_changes=0, machine_revision="30-07-2026",
         readiness="15-07-2026", container_placement="22-07-2026", container_changes=0,
         container_revision="24-07-2026", vessel="28-07-2026", clearance="Completed"),

    # INDIA: commitment blank (overdue), container placement blank (container pending).
    _row("JULY", "INDIA", "H70", 8, loading="", commitment_loading="",
         loading_changes=3, revision_commitment_loading="12-07-2026",
         production_completion="09-07-2026", prdn_changes=5, machine_revision="",
         readiness="01-07-2026", container_placement="", container_changes=4,
         container_revision="10-07-2026", vessel="15-07-2026",
         overdue_days=6, clearance=""),

    # BRAZIL: shipped in the PAST (still counts as Pending per the doc), overdue.
    _row("JULY", "BRAZIL", "B45", 5, loading="05-07-2026",
         commitment_loading="07-07-2026", loading_changes=4,
         revision_commitment_loading="11-07-2026", production_completion="",
         prdn_changes=12, machine_revision="08-07-2026",
         readiness="03-07-2026", container_placement="07-07-2026", container_changes=9,
         container_revision="09-07-2026", vessel="25-07-2026",
         overdue_days=6, clearance="Pending"),

    # JAPAN: everything fine EXCEPT clearance is pending.
    _row("JULY", "JAPAN", "J55", 7, loading="18-07-2026",
         commitment_loading="20-07-2026", loading_changes=1,
         revision_commitment_loading="", production_completion="11-07-2026",
         prdn_changes=2, machine_revision="22-07-2026",
         readiness="12-07-2026", container_placement="19-07-2026", container_changes=1,
         container_revision="21-07-2026", vessel="26-07-2026", clearance="Pending"),

    # KENYA: worst case — >5 machines pending on both prod & container (red rules).
    _row("JULY", "KENYA", "K30", 9, loading="", commitment_loading="01-07-2026",
         loading_changes=5, revision_commitment_loading="05-07-2026",
         production_completion="", prdn_changes=20, machine_revision="03-07-2026",
         readiness="25-06-2026", container_placement="", container_changes=15,
         container_revision="02-07-2026", vessel="12-07-2026",
         overdue_days=12, clearance="Pending"),
    _row("JULY", "KENYA", "K35", 4, loading="", commitment_loading="03-07-2026",
         loading_changes=7, revision_commitment_loading="14-07-2026",
         production_completion="", prdn_changes=26, machine_revision="06-07-2026",
         readiness="28-06-2026", container_placement="", container_changes=19,
         container_revision="04-07-2026", vessel="16-07-2026",
         overdue_days=10, clearance="Pending"),

    # MEXICO: mostly overdue across two lines/models.
    _row("JULY", "MEXICO", "Z100", 9, loading="", commitment_loading="04-07-2026",
         loading_changes=2, revision_commitment_loading="13-07-2026",
         production_completion="", prdn_changes=8, machine_revision="07-07-2026",
         readiness="29-06-2026", container_placement="06-07-2026", container_changes=6,
         container_revision="08-07-2026", vessel="20-07-2026",
         overdue_days=9, clearance="Pending"),
    _row("JULY", "MEXICO", "X250", 4, loading="", commitment_loading="02-07-2026",
         loading_changes=4, revision_commitment_loading="15-07-2026",
         production_completion="10-07-2026", prdn_changes=10,
         machine_revision="09-07-2026", readiness="27-06-2026",
         container_placement="05-07-2026",
         container_changes=8, container_revision="07-07-2026", vessel="18-07-2026",
         overdue_days=11, clearance="Pending"),

    # CHILE: fully clean (future commitments).
    _row("JULY", "CHILE", "B60", 6, loading="21-07-2026",
         commitment_loading="24-07-2026", loading_changes=1,
         revision_commitment_loading="", production_completion="10-07-2026",
         prdn_changes=0, machine_revision="28-07-2026",
         readiness="18-07-2026", container_placement="23-07-2026", container_changes=0,
         container_revision="26-07-2026", vessel="29-07-2026", clearance="Completed"),

    # PERU: overdue + container pending, clearance blank, across two lines.
    _row("JULY", "PERU", "K35", 8, loading="", commitment_loading="30-06-2026",
         loading_changes=5, revision_commitment_loading="12-07-2026",
         production_completion="09-07-2026", prdn_changes=3, machine_revision="",
         readiness="20-06-2026", container_placement="", container_changes=7,
         container_revision="10-07-2026", vessel="15-07-2026",
         overdue_days=13, clearance=""),
    _row("JULY", "PERU", "K30", 5, loading="", commitment_loading="29-06-2026",
         loading_changes=6, revision_commitment_loading="11-07-2026",
         production_completion="", prdn_changes=9, machine_revision="05-07-2026",
         readiness="22-06-2026", container_placement="", container_changes=5,
         container_revision="03-07-2026", vessel="14-07-2026",
         overdue_days=14, clearance="Pending"),

    # EGYPT: heavy overdue across two lines.
    _row("JULY", "EGYPT", "G120", 10, loading="", commitment_loading="25-06-2026",
         loading_changes=6, revision_commitment_loading="15-07-2026",
         production_completion="", prdn_changes=22, machine_revision="05-07-2026",
         readiness="18-06-2026", container_placement="07-07-2026", container_changes=18,
         container_revision="06-07-2026", vessel="14-07-2026",
         overdue_days=18, clearance="Pending"),
    _row("JULY", "EGYPT", "H80", 3, loading="", commitment_loading="27-06-2026",
         loading_changes=4, revision_commitment_loading="14-07-2026",
         production_completion="", prdn_changes=16, machine_revision="08-07-2026",
         readiness="20-06-2026", container_placement="", container_changes=12,
         container_revision="09-07-2026", vessel="16-07-2026",
         overdue_days=16, clearance="Pending"),

    # NIGERIA: production overdue only.
    _row("JULY", "NIGERIA", "H70", 5, loading="19-07-2026",
         commitment_loading="22-07-2026", loading_changes=0,
         revision_commitment_loading="", production_completion="",
         prdn_changes=9, machine_revision="08-07-2026",
         readiness="01-07-2026", container_placement="20-07-2026", container_changes=2,
         container_revision="21-07-2026", vessel="27-07-2026", clearance="Completed"),

    # VIETNAM: past-shipped but overdue, both prod & container overdue.
    _row("JULY", "VIETNAM", "J55", 7, loading="04-07-2026",
         commitment_loading="06-07-2026", loading_changes=4,
         revision_commitment_loading="11-07-2026", production_completion="",
         prdn_changes=14, machine_revision="09-07-2026",
         readiness="28-06-2026", container_placement="05-07-2026", container_changes=11,
         container_revision="07-07-2026", vessel="24-07-2026",
         overdue_days=7, clearance="Pending"),

    # SPAIN: clearance pending only.
    _row("JULY", "SPAIN", "G90", 6, loading="18-07-2026",
         commitment_loading="20-07-2026", loading_changes=1,
         revision_commitment_loading="", production_completion="11-07-2026",
         prdn_changes=2, machine_revision="23-07-2026",
         readiness="14-07-2026", container_placement="19-07-2026", container_changes=1,
         container_revision="22-07-2026", vessel="26-07-2026", clearance="Pending"),

    # CANADA: blank commitment (overdue), container pending.
    _row("JULY", "CANADA", "X200", 8, loading="", commitment_loading="",
         loading_changes=3, revision_commitment_loading="12-07-2026",
         production_completion="", prdn_changes=10, machine_revision="06-07-2026",
         readiness="26-06-2026", container_placement="", container_changes=5,
         container_revision="09-07-2026", vessel="16-07-2026",
         overdue_days=8, clearance="Pending"),
]


def build_dataframe() -> pd.DataFrame:
    """The full test dataset as a DataFrame with the exact sheet columns."""
    rows = [dict(r) for r in ROWS]
    for i, r in enumerate(rows, start=1):
        # Serial ties to the row's month for a little realism, e.g. M-JUL-0031.
        r["Serial Number"] = f"M-{str(r['Month'])[:3].upper()}-{i:04d}"
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--push", action="store_true",
        help="Also overwrite the Google Sheet worksheet (clears it first!).",
    )
    args = parser.parse_args()

    df = build_dataframe()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(OUT, index=False, sheet_name="SCM_Export_Orders")
    print(f"Wrote {len(df)} rows x {len(df.columns)} cols to {OUT}")

    if args.push:
        # Imported lazily so the offline path never needs Google credentials.
        from app.clients.sheets_client import overwrite_worksheet
        from app.config import settings

        n = overwrite_worksheet(settings.sheet_id, settings.worksheet_name, df)
        print(f"Pushed {n} rows to Google Sheet worksheet '{settings.worksheet_name}'.")


if __name__ == "__main__":
    main()
