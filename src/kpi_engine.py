"""KPI computation. Pure functions over a DataFrame — no I/O."""
import pandas as pd

MONTH_ORDER = ["APRIL", "MAY", "JUNE"]  # extend as needed

# Raw sheet column headers (SCM_Export tab, columns A–T). Kept here so a header
# rename in the sheet is a one-line fix.
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

DATE_FORMAT = "%d-%m-%Y"  # sheet stores dates day-first (e.g. 07-07-2026)

# Clearance statuses that count as done; anything else (e.g. "Pending", blank)
# is treated as clearance pending.
_CLEARANCE_DONE = {"completed", "complete", "cleared", "done", "yes"}


def compute_month_kpis(df: pd.DataFrame, month: str, prev_balance: int = 0) -> dict:
    # Opening order carries over from the previous month's balance.
    opening_order = prev_balance

    # New orders: Order Type 'N' in the current month.
    new_order = df[
        (df["Month"] == month) & (df["Order Type (N / O)"] == "N")
    ]["Quantity"].sum()

    total_order = opening_order + new_order

    # Despatched: rows with a loading date, in the current month.
    dispatched = df[
        df["Loading (Dispatched) Date"].notna() & (df["Month"] == month)
    ]["Quantity"].sum()

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


def _is_dispatched(series: pd.Series) -> pd.Series:
    """True only where the loading cell holds a real date.

    In the sheet an order that hasn't shipped shows a blank cell or the literal
    ``Pending`` — neither is a dispatch, so both count as still open. Dispatch
    dates are stored day-first (``DD-MM-YYYY``); anything that doesn't parse as
    such is treated as not-yet-dispatched.
    """
    return pd.to_datetime(series, format=DATE_FORMAT, errors="coerce").notna()


def _clearance_pending(series: pd.Series) -> pd.Series:
    """True where clearance is not done — status is 'Pending', blank, etc."""
    return ~series.astype(str).str.strip().str.lower().isin(_CLEARANCE_DONE)


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
    """Per-country overdue & 'commitment not given' breakup.

    If ``month`` is given, only that month's rows are considered. One row per
    country that still has an open (undispatched or overdue) order, so
    zero-overdue countries with open orders still appear. Commitment-section
    metrics are scoped to overdue rows (``over due days`` > 0), matching the
    sheet's "Commitment not Given – Over Due days" grouping.
    """
    if df.empty or COL_COUNTRY not in df.columns:
        return []

    df = df.copy()
    if month is not None:
        df = df[df["Month"].astype(str).str.strip().str.upper() == month.upper()]
        if df.empty:
            return []

    qty = _to_numeric(_col(df, COL_QUANTITY))
    overdue_days = _to_numeric(_col(df, COL_OVERDUE_DAYS))
    prdn_changes = _to_numeric(_col(df, COL_PRDN_CHANGES))
    container_changes = _to_numeric(_col(df, COL_CONTAINER_CHANGES))
    is_open = ~_is_dispatched(_col(df, COL_LOADING_DATE))
    is_overdue = overdue_days > 0

    # Date columns used for the "latest committed" dates shown per country.
    machine_revision = _col(df, COL_MACHINE_REVISION)
    container_placement = _col(df, COL_CONTAINER_PLACEMENT)
    container_revision = _col(df, COL_CONTAINER_REVISION)
    vessel_cutoff = _col(df, COL_VESSEL_CUTOFF)

    # "No of machines pending" = open (not-yet-dispatched) machines. Prod- and
    # container-side use the same open set; they differ only when open machines
    # are still awaiting a production vs container date (none are, in this data).
    prdn_pending = is_open
    container_pending = is_open
    # Clearance pending = any row (not just overdue) whose clearance isn't done;
    # in this data the pending clearances sit on open, not-yet-overdue rows.
    clearance_pending = _clearance_pending(_col(df, COL_CLEARANCE_STATUS))

    results = []
    for country, idx in df.groupby(COL_COUNTRY).groups.items():
        rows = df.index.isin(idx)
        open_rows = rows & is_open
        overdue_rows = rows & is_overdue
        if not open_rows.any() and not overdue_rows.any():
            continue  # nothing outstanding to report
        if str(country).strip() == "":
            continue  # skip blank/unlabelled country rows

        overdue_day_values = overdue_days[overdue_rows]

        results.append(
            {
                "country": str(country),
                "over_due_breakup": int(qty[overdue_rows].sum()),
                "days_delay": int(overdue_day_values.max()) if overdue_rows.any() else 0,
                # Latest committed dates across the country's overdue rows.
                "new_committed_date": _max_date(overdue_rows, machine_revision),
                "container_expected_date": _max_date(
                    overdue_rows, container_placement, container_revision
                ),
                "vessel_cutoff": _max_date(overdue_rows, vessel_cutoff),
                "prdn_machines_pending": int(qty[rows & prdn_pending].sum()),
                "prdn_commitment_changes": int(prdn_changes[overdue_rows].sum()),
                "container_machines_pending": int(qty[rows & container_pending].sum()),
                "container_commitment_changes": int(
                    container_changes[overdue_rows].sum()
                ),
                "clearance_pending": int(qty[rows & clearance_pending].sum()),
            }
        )

    results.sort(key=lambda r: r["over_due_breakup"], reverse=True)
    return results
