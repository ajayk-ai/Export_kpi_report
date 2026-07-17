"""KPI computation. Pure functions over a DataFrame — no I/O."""
from datetime import date

import pandas as pd

MONTH_ORDER = ["MAY", "JUNE", "JULY"]  # extend as needed

# Month name -> calendar number, used to tell which calendar month a Loading
# (Dispatched) Date actually falls in (see _is_dispatched_in_month).
MONTH_NUM = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}

# Raw sheet column headers (SCM_Export tab, columns A–T). Kept here so a header
# rename in the sheet is a one-line fix.
COL_COUNTRY = "Country"
COL_QUANTITY = "Quantity"
COL_MACHINE_REVISION = "production commitment Revise Date"
COL_MACHINE_READINESS = "production commitment Date"             # -> Days Delay from 1st Commitment
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
COL_REVISION_COMMITMENT_LOADING = "revision commitment of loading date"  # -> New Committed Date

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

    # Despatched = every order line whose Loading (Dispatched) Date actually
    # falls in this month — regardless of which month the order was originally
    # booked in. Orders carry forward from a prior month's Balance and often
    # ship later than their own Month bucket, so despatch has to be attributed
    # to the month it really happened in, not the order's booking month.
    dispatched_mask = _is_dispatched_in_month(_col(df, COL_LOADING_DATE), month)
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


def _is_dispatched_in_month(loading: pd.Series, month: str) -> pd.Series:
    """True where the row's Loading (Dispatched) Date actually falls in ``month``.

    A dispatch counts when the loading cell holds a real date (day-first
    ``DD-MM-YYYY``) that is BOTH:

    * on or before today — a load date in the future hasn't shipped yet; and
    * in the calendar month being reported on — regardless of which month the
      order was originally booked in, since carry-forward orders routinely ship
      later than their own Month bucket.

    Anything else doesn't count towards this month's Despatched: a blank cell,
    the literal ``Pending``, a future-dated load, or a load that happened in a
    different month. (No year is stored anywhere, so the month numbers are
    compared within the loading date's own year, which is what the single-year
    reporting window needs.)
    """
    loaded = pd.to_datetime(loading, format=DATE_FORMAT, errors="coerce")
    target = MONTH_NUM.get(month.strip().upper())
    if target is None:
        return pd.Series(False, index=loading.index)
    in_target_month = loaded.dt.month == target
    not_future = loaded <= pd.Timestamp(date.today())
    return loaded.notna() & in_target_month & not_future


def _clearance_pending(series: pd.Series) -> pd.Series:
    """True where clearance is pending — status is literally 'Pending' or blank."""
    return series.astype(str).str.strip().str.lower().isin(_CLEARANCE_PENDING_VALUES)


def _dates(col: pd.Series) -> pd.Series:
    """Parse a day-first date column; unparseable/blank cells become NaT."""
    return pd.to_datetime(col, format=DATE_FORMAT, errors="coerce")


def _is_past(col: pd.Series) -> pd.Series:
    """Mask: date cell holds a real date earlier than today."""
    parsed = _dates(col)
    return parsed.notna() & (parsed < pd.Timestamp(date.today()))


def _is_blank_date(col: pd.Series) -> pd.Series:
    """Mask: date cell is blank/unparseable (no date committed)."""
    return _dates(col).isna()


def _blank_or_fallback_past(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    """True where the primary date is past, falling back to the fallback date
    when the primary cell is blank/unparseable.

    An explicit primary date always wins, even over a past fallback date —
    the fallback is only consulted when the primary gives no date at all.
    """
    primary_dates = _dates(primary)
    fallback_dates = _dates(fallback)
    effective = primary_dates.where(primary_dates.notna(), fallback_dates)
    return effective.notna() & (effective < pd.Timestamp(date.today()))


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


def _min_date(mask: pd.Series, *cols: pd.Series) -> str:
    """Earliest (min) date across the given columns for the masked rows.

    Returns a ``DD-MM-YYYY`` string, or "" when none of the cells hold a date.
    """
    best = None
    for col in cols:
        parsed = pd.to_datetime(col[mask], format=DATE_FORMAT, errors="coerce").dropna()
        if not parsed.empty:
            candidate = parsed.min()
            best = candidate if best is None else min(best, candidate)
    return best.strftime(DATE_FORMAT) if best is not None else ""


def _worst_delay_days(mask: pd.Series, col: pd.Series) -> int:
    """Days between today and the oldest (earliest) date in ``col`` among masked rows.

    The oldest still-overdue Production Commitment Date is that group's single
    worst delay from 1st commitment — not an average across rows. Returns 0
    when no masked row holds a real date.
    """
    parsed = pd.to_datetime(col[mask], format=DATE_FORMAT, errors="coerce").dropna()
    if parsed.empty:
        return 0
    oldest = parsed.min()
    return max(0, (pd.Timestamp(date.today()) - oldest).days)


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
    prdn_changes = _to_numeric(_col(df, COL_PRDN_CHANGES))
    container_changes = _to_numeric(_col(df, COL_CONTAINER_CHANGES))

    # Date columns for the latest-committed dates shown per country.
    revision_commitment_loading = _col(df, COL_REVISION_COMMITMENT_LOADING)
    container_placement = _col(df, COL_CONTAINER_PLACEMENT)
    vessel_cutoff = _col(df, COL_VESSEL_CUTOFF)
    machine_readiness = _col(df, COL_MACHINE_READINESS)

    # Row masks, each straight from the doc's KPI definitions.
    loading_date = _col(df, COL_LOADING_DATE)
    # KPI 2 — Pending Orders: loading date blank, OR the revised loading
    # commitment has already slipped past today.
    pending_orders = _is_blank_date(loading_date) | _is_past(
        _col(df, COL_REVISION_COMMITMENT_LOADING)
    )
    # KPI 3 — Over Due Breakup: not yet dispatched, AND overdue on production
    # commitment — checked against the Production Commitment Revise Date if
    # one's been given, falling back to the Production Commitment Date when
    # no revise date has been set yet.
    overdue_breakup = _is_blank_date(loading_date) & _blank_or_fallback_past(
        _col(df, COL_MACHINE_REVISION), machine_readiness
    )
    machine_revision_past = _is_past(_col(df, COL_MACHINE_REVISION))
    # KPI 7A — Prdn machines pending: no Production Commitment Date given yet,
    # OR one was given but has since been superseded by a Production
    # Commitment Revise Date that's itself now overdue (same
    # blank-or-revised-is-late shape as KPI 2).
    prdn_pending = _is_blank_date(machine_readiness) | machine_revision_past
    prdn_overdue = machine_revision_past                                     # KPI 7C
    container_revision = _col(df, COL_CONTAINER_REVISION)
    # KPI 8A — Container machines pending: no placement date given yet, OR one
    # was given but is now overdue and no Container Revision Date has been set
    # yet either — once a revision date exists, the row is tracked via
    # Container Overdue (KPI 8C) instead, not counted as pending anymore.
    container_pending = _is_blank_date(container_placement) | (
        _is_past(container_placement) & _is_blank_date(container_revision)
    )
    container_overdue = _is_past(container_revision)                         # KPI 8C
    clearance_pending = _clearance_pending(_col(df, COL_CLEARANCE_STATUS))   # KPI 10

    results = []
    for country, idx in df.groupby(COL_COUNTRY).groups.items():
        if str(country).strip() == "":
            continue  # skip blank/unlabelled country rows
        rows = df.index.isin(idx)

        def machines(mask: pd.Series, _rows: pd.Series = rows) -> int:
            return int(qty[_rows & mask].sum())

        def average(series: pd.Series, _rows: pd.Series = rows) -> int:
            vals = series[_rows]
            return round(float(vals.mean())) if len(vals) else 0

        results.append(
            {
                "country": str(country),
                "pending_orders": machines(pending_orders),          # KPI 2
                "over_due_breakup": machines(overdue_breakup),       # KPI 3
                "days_delay": _worst_delay_days(rows & overdue_breakup, machine_readiness),  # KPI 4
                "new_committed_date": _max_date(rows, revision_commitment_loading),  # KPI 5
                "container_expected_date": _max_date(rows, container_placement),     # KPI 6
                "prdn_machines_pending": machines(prdn_pending),     # KPI 7A
                "prdn_commitment_changes": average(prdn_changes),    # KPI 7B
                "prdn_overdue": machines(prdn_overdue),              # KPI 7C
                "container_machines_pending": machines(container_pending),  # KPI 8A
                "container_commitment_changes": average(container_changes),  # KPI 8B
                "container_overdue": machines(container_overdue),    # KPI 8C
                "vessel_cutoff": _min_date(rows, vessel_cutoff),     # KPI 9
                "clearance_pending": machines(clearance_pending),    # KPI 10
            }
        )

    results.sort(key=lambda r: r["over_due_breakup"], reverse=True)
    return results
