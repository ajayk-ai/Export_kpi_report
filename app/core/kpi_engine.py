"""KPI computation. Pure functions over a DataFrame — no I/O."""
from datetime import date

import pandas as pd

MONTH_ORDER = ["MAY", "JUNE", "JULY"]  # extend as needed

# Month name -> calendar number, used to tell whether a dispatch slipped into a
# later month than the order's own Month bucket (see _is_dispatched).
MONTH_NUM = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}

# Raw sheet column headers (SCM_Export tab, columns A–T). Kept here so a header
# rename in the sheet is a one-line fix.
COL_MONTH = "Month"
COL_COUNTRY = "Country"
COL_QUANTITY = "Quantity"
COL_MACHINE_REVISION = "Machine Revision Date"
# The sheet header is misspelled ("commitement"); accept both spellings so this
# keeps working if the typo is ever corrected.
COL_PRDN_CHANGES = (
    "no of times commitment changes(prod)",
    "no of times commitement changes(prod)",
)
COL_CONTAINER_PLACEMENT = "Container Placement date"
COL_CONTAINER_REVISION = "Container Revision Date"
COL_CONTAINER_CHANGES = "no of comm container changes"
COL_LOADING_DATE = "Loading (Dispatched) Date"
COL_OVERDUE_DAYS = "over due days"
COL_VESSEL_CUTOFF = "Vessel Cut-Off Date"
COL_CLEARANCE_STATUS = "Commercial Clearance Status"
# Columns referenced by the business-logic doc's breakup KPIs.
COL_COMMITMENT_LOADING = "commitment of loading date"          # -> Overdue Breakup
COL_REVISION_COMMITMENT_LOADING = "revision commitment of loading date"  # -> New Committed Date
# The sheet header carries a double space; accept the single-space form too.
COL_COMMITMENT_LOADING_CHANGES = (
    "no of commitment loading  changes",
    "no of commitment loading changes",
)
COL_PRODUCTION_COMPLETION = "Production Completion Date"       # -> Prdn machines pending

DATE_FORMAT = "%d-%m-%Y"  # sheet stores dates day-first (e.g. 07-07-2026)

# A machine's clearance is pending when its status is literally "Pending" or
# blank (per the business-logic doc); every other value counts as cleared.
_CLEARANCE_PENDING_VALUES = {"pending", "", "nan", "none"}


def compute_month_kpis(df: pd.DataFrame, month: str, prev_balance: int = 0) -> dict:
    # Opening order carries over from the previous month's balance. Balance is
    # always >= 0 (see below), so opening order is never negative either.
    opening_order = prev_balance

    # Case/whitespace-insensitive month match, so 'July'/' JULY ' both work.
    in_month = _col(df, "Month").astype(str).str.strip().str.upper() == month.upper()
    qty = _to_numeric(_col(df, COL_QUANTITY))

    # New orders: every order line in the month. (There's no longer an Order Type
    # column to distinguish new vs carry-over — an order is simply counted in the
    # month it belongs to.)
    new_order = int(qty[in_month].sum())

    total_order = opening_order + new_order

    # Despatched = order lines in the month that have really shipped for their
    # month (a loading date in this month or earlier; a later-month date is still
    # pending). These rows are a subset of the month's rows, so dispatched <=
    # new_order, which keeps balance (open orders) at zero or positive.
    dispatched_mask = in_month & _is_dispatched(
        _col(df, COL_LOADING_DATE), _col(df, COL_MONTH)
    )
    dispatched = int(qty[dispatched_mask].sum())

    balance = total_order - dispatched

    return {
        "month": month,
        "opening_order": int(opening_order),
        "new_order": int(new_order),
        "total_order": int(total_order),
        "dispatched": int(dispatched),
        "balance": int(balance),
    }


def latest_month(df: pd.DataFrame) -> str:
    """The most recent month present in the data, per ``MONTH_ORDER``.

    Falls back to the last configured month if the sheet has none of them.
    """
    present = set(df.get("Month", pd.Series(dtype=str)).astype(str).str.strip().str.upper())
    for month in reversed(MONTH_ORDER):
        if month in present:
            return month
    return MONTH_ORDER[-1]


def compute_all_kpis(df: pd.DataFrame) -> list[dict]:
    """Compute KPIs for each month in MONTH_ORDER, carrying balance forward."""
    results = []
    prev_balance = 0
    for month in MONTH_ORDER:
        kpi = compute_month_kpis(df, month, prev_balance)
        results.append(kpi)
        prev_balance = kpi["balance"]
    return results


def _col(df: pd.DataFrame, name: str | tuple[str, ...]) -> pd.Series:
    """Return a column, or an all-blank column if the sheet doesn't have it.

    ``name`` may be a single header or several accepted spellings; the first one
    present wins. Lets the breakup run against tabs that are missing some of the
    A–T columns instead of raising KeyError — a missing column contributes 0.
    """
    names = (name,) if isinstance(name, str) else name
    for candidate in names:
        if candidate in df.columns:
            return df[candidate]
    return pd.Series([""] * len(df), index=df.index)


def _to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a column to numbers, treating blanks/garbage as 0."""
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _is_dispatched(loading: pd.Series, months: pd.Series) -> pd.Series:
    """True only where the order has really shipped.

    A dispatch counts when the loading cell holds a real date (day-first
    ``DD-MM-YYYY``) that is BOTH:

    * on or before today — a load date in the future hasn't shipped yet; and
    * in the order's ``Month`` bucket or earlier — a date in a *later* month than
      the bucket is a dispatch that slipped past its month.

    Anything else is still pending/open: a blank cell, the literal ``Pending``, a
    future-dated load, or a later-month load. (Buckets carry no year, so the month
    numbers are compared within the loading date's own year, which is what the
    single-year reporting window needs.)
    """
    loaded = pd.to_datetime(loading, format=DATE_FORMAT, errors="coerce")
    bucket = months.astype(str).str.strip().str.upper().map(MONTH_NUM)
    # not_slipped is False for a later-month dispatch; unknown bucket names fall
    # back to "any real date counts", preserving the old behaviour.
    not_slipped = (loaded.dt.month <= bucket) | bucket.isna()
    # not_future is False for a load date after today (still to happen).
    not_future = loaded <= pd.Timestamp(date.today())
    return loaded.notna() & not_slipped & not_future


def _clearance_pending(series: pd.Series) -> pd.Series:
    """True where clearance is pending — status is literally 'Pending' or blank."""
    return series.astype(str).str.strip().str.lower().isin(_CLEARANCE_PENDING_VALUES)


def _dates(col: pd.Series) -> pd.Series:
    """Parse a day-first date column; unparseable/blank cells become NaT."""
    return pd.to_datetime(col, format=DATE_FORMAT, errors="coerce")


def _blank_or_past(col: pd.Series) -> pd.Series:
    """Mask: date cell is blank/unparseable OR earlier than today."""
    parsed = _dates(col)
    return parsed.isna() | (parsed < pd.Timestamp(date.today()))


def _is_past(col: pd.Series) -> pd.Series:
    """Mask: date cell holds a real date earlier than today."""
    parsed = _dates(col)
    return parsed.notna() & (parsed < pd.Timestamp(date.today()))


def _is_blank_date(col: pd.Series) -> pd.Series:
    """Mask: date cell is blank/unparseable (no date committed)."""
    return _dates(col).isna()


def _max_date(mask: pd.Series, *cols: pd.Series) -> str:
    """Latest (max) date across the given columns for the masked rows.

    Returns a ``DD-MM-YYYY`` string, or "" when none of the cells hold a date.
    """
    best = None
    for col in cols:
        parsed = pd.to_datetime(col[mask], format=DATE_FORMAT, errors="coerce").dropna()
        if not parsed.empty:
            candidate = parsed.max()
            best = candidate if best is None else max(best, candidate)
    return best.strftime(DATE_FORMAT) if best is not None else ""


def compute_country_breakup(
    df: pd.DataFrame, month: str | None = None
) -> list[dict]:
    """Per-country breakup dashboard, one row per unique Country.

    Every KPI follows the business-logic doc (``logic_docs/Export Kpi
    project.docx``). If ``month`` is given, only that month's rows are
    considered. All "count" KPIs are expressed in machines (sum of Quantity over
    the matching rows); the "commitment changes" KPIs are averages of their
    respective change-count columns across the country's rows.
    """
    if df.empty or COL_COUNTRY not in df.columns:
        return []

    df = df.copy()
    if month is not None:
        df = df[df["Month"].astype(str).str.strip().str.upper() == month.upper()]
        if df.empty:
            return []

    qty = _to_numeric(_col(df, COL_QUANTITY))
    commitment_loading_changes = _to_numeric(_col(df, COL_COMMITMENT_LOADING_CHANGES))
    prdn_changes = _to_numeric(_col(df, COL_PRDN_CHANGES))
    container_changes = _to_numeric(_col(df, COL_CONTAINER_CHANGES))

    # Date columns for the latest-committed dates shown per country.
    revision_commitment_loading = _col(df, COL_REVISION_COMMITMENT_LOADING)
    container_placement = _col(df, COL_CONTAINER_PLACEMENT)
    vessel_cutoff = _col(df, COL_VESSEL_CUTOFF)

    # Row masks, each straight from the doc's KPI definitions.
    # KPI 2 — Pending Orders: loading date blank, OR the revised loading
    # commitment has already slipped past today.
    pending_orders = _is_blank_date(_col(df, COL_LOADING_DATE)) | _is_past(
        _col(df, COL_REVISION_COMMITMENT_LOADING)
    )
    overdue_breakup = _blank_or_past(_col(df, COL_COMMITMENT_LOADING))       # KPI 3
    prdn_pending = _is_blank_date(_col(df, COL_PRODUCTION_COMPLETION))       # KPI 7A
    prdn_overdue = _is_past(_col(df, COL_MACHINE_REVISION))                  # KPI 7C
    container_pending = _is_blank_date(_col(df, COL_CONTAINER_PLACEMENT))    # KPI 8A
    container_overdue = _is_past(_col(df, COL_CONTAINER_REVISION))           # KPI 8C
    clearance_pending = _clearance_pending(_col(df, COL_CLEARANCE_STATUS))   # KPI 10

    results = []
    for country, idx in df.groupby(COL_COUNTRY).groups.items():
        if str(country).strip() == "":
            continue  # skip blank/unlabelled country rows
        rows = df.index.isin(idx)

        def machines(mask: pd.Series, _rows: pd.Series = rows) -> int:
            return int(qty[_rows & mask].sum())

        def average(series: pd.Series, _rows: pd.Series = rows) -> float:
            vals = series[_rows]
            return round(float(vals.mean()), 1) if len(vals) else 0.0

        results.append(
            {
                "country": str(country),
                "pending_orders": machines(pending_orders),          # KPI 2
                "over_due_breakup": machines(overdue_breakup),       # KPI 3
                "days_delay": average(commitment_loading_changes),   # KPI 4
                "new_committed_date": _max_date(rows, revision_commitment_loading),  # KPI 5
                "container_expected_date": _max_date(rows, container_placement),     # KPI 6
                "prdn_machines_pending": machines(prdn_pending),     # KPI 7A
                "prdn_commitment_changes": average(prdn_changes),    # KPI 7B
                "prdn_overdue": machines(prdn_overdue),              # KPI 7C
                "container_machines_pending": machines(container_pending),  # KPI 8A
                "container_commitment_changes": average(container_changes),  # KPI 8B
                "container_overdue": machines(container_overdue),    # KPI 8C
                "vessel_cutoff": _max_date(rows, vessel_cutoff),     # KPI 9
                "clearance_pending": machines(clearance_pending),    # KPI 10
            }
        )

    results.sort(key=lambda r: r["over_due_breakup"], reverse=True)
    return results
