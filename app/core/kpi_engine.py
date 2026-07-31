"""KPI computation. Pure functions over a DataFrame — no I/O."""
from datetime import date

import pandas as pd

# Month name -> calendar number, used both to order MONTH_ORDER below and to
# tell which calendar month a Loading (Dispatched) Date actually falls in (see
# _is_dispatched_in_year_month).
MONTH_NUM = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}

# All 12 calendar months, in order. Derived from MONTH_NUM so the two can
# never drift apart.
MONTH_ORDER = sorted(MONTH_NUM, key=MONTH_NUM.get)

# Every string that should resolve to a given month: the full name, its
# 3-letter abbreviation, and its 1/2-digit calendar number (all matched
# case/whitespace-insensitively by normalize_month).
_MONTH_ALIASES = {
    full: {full, full[:3], str(num), f"{num:02d}"}
    for full, num in MONTH_NUM.items()
}
_MONTH_LOOKUP = {
    alias: full for full, aliases in _MONTH_ALIASES.items() for alias in aliases
}


def normalize_month(value: str | int | None) -> str | None:
    """Resolve flexible month input to its canonical MONTH_ORDER name.

    Accepts a full name ("July"/"JULY"/" july "), a 3-letter abbreviation
    ("Jul"/"JUL"), or a calendar number ("7", "07", 7). Returns ``None`` if
    ``value`` is blank or doesn't match any of the above, so callers can
    surface a clear error instead of silently matching nothing.
    """
    if value is None:
        return None
    key = str(value).strip().upper()
    if not key:
        return None
    return _MONTH_LOOKUP.get(key)


def _normalized_month_column(df: pd.DataFrame) -> pd.Series:
    """The sheet's ``Month`` column, each value resolved through
    ``normalize_month`` (so 'June'/'Jun'/'JUNE'/'6'/'06' all become 'JUNE').

    Different people fill in the sheet over time and don't all spell months
    the same way; matching on the raw string (as this used to do) silently
    drops any row that isn't the one exact canonical form, undercounting that
    month and throwing off which month ``latest_month`` picks as current.
    A value that doesn't resolve to any known month (e.g. a genuine typo like
    'Augest') becomes ``None`` here and is reported via
    ``unmapped_month_values`` rather than silently vanishing.
    """
    return _col(df, "Month").map(normalize_month)


def unmapped_month_values(df: pd.DataFrame) -> list[str]:
    """Distinct raw ``Month`` values that don't resolve to any real month.

    Surfaces data-entry typos (e.g. 'Augest') that would otherwise silently
    drop that row out of every KPI count. Blank cells are ignored.
    """
    raw = _col(df, "Month").astype(str).str.strip()
    unresolved = raw[(raw != "") & raw.map(normalize_month).isna()]
    return sorted(unresolved.unique().tolist())

# Raw sheet column headers (SCM_Export tab, columns A–T). Kept here so a header
# rename in the sheet is a one-line fix.
# The reporting year the row belongs to. The planning team enters this per row;
# it's what keeps a later year's reused MAY/JUNE/JULY labels from merging into
# this year's buckets (see _for_year / latest_year).
COL_YEAR = "Year"
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
COL_PRODUCTION_COMPLETION = "Production Completion (Roll-out)Date"
COL_ACTUAL_CONTAINER = "actual_container"
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


def compute_month_kpis(df: pd.DataFrame, month: str, year: int, prev_balance: int = 0) -> dict:
    # Opening order carries over from the previous month's balance. Balance is
    # always >= 0 (see below), so opening order is never negative either.
    opening_order = prev_balance

    # Match via normalize_month, not a raw string compare, so 'July'/'JUL'/'7'
    # all land in the same bucket as 'JULY' regardless of how a given row was
    # typed (see _normalized_month_column).
    in_month = _normalized_month_column(df) == month.upper()
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
    dispatched_mask = _is_dispatched_in_year_month(_col(df, COL_LOADING_DATE), year, month)
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


def _is_future_period(df: pd.DataFrame) -> pd.Series:
    """True where a row's (Year, Month) hasn't started yet as of today.

    Lets a team pre-stage a future order in the sheet (a forecasted Month/Year
    with a quantity, dispatch still blank) without it counting as a current new
    or pending order — it's simply not "now" yet. Rows with a missing or
    unparseable Year or Month are treated as NOT future (kept), the same
    "don't silently drop data" fallback ``_for_year`` uses.
    """
    today = date.today()
    years = pd.to_numeric(df.get(COL_YEAR, pd.Series(dtype=str, index=df.index)), errors="coerce")
    months = _normalized_month_column(df).map(MONTH_NUM)
    known = years.notna() & months.notna()
    future = known & ((years > today.year) | ((years == today.year) & (months > today.month)))
    return future.fillna(False)


def _drop_future_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose (Year, Month) is a period that hasn't started yet.

    Applied at every KPI entry point (``latest_year``, ``latest_month``,
    ``compute_all_kpis``, ``compute_country_breakup``) so a pre-staged future
    order can never inflate a new-order count, pad out the monthly summary
    with extra rows, or get flagged pending/overdue before its time.
    """
    return df[~_is_future_period(df)]


def latest_year(df: pd.DataFrame) -> int:
    """The most recent reporting year in the sheet's ``Year`` column.

    This is what makes the report "current year only": everything downstream is
    scoped to this year (see ``_for_year``). Falls back to the current calendar
    year when the column is missing or holds no usable year, so an old sheet
    without a Year column keeps behaving exactly as it did before. Rows for a
    period that hasn't started yet (see ``_drop_future_rows``) are ignored, so
    a pre-staged future order can't make the report jump ahead of itself.
    """
    df = _drop_future_rows(df)
    years = pd.to_numeric(df.get(COL_YEAR, pd.Series(dtype=str)), errors="coerce").dropna()
    return int(years.max()) if not years.empty else date.today().year


def _for_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Only the rows whose ``Year`` column matches ``year``.

    Two safety fallbacks keep this from ever blanking a report by accident:
    if the sheet has no Year column, or the column is present but entirely
    blank, every row is kept (the old single-year behaviour). Rows left blank
    while other rows are filled are treated as unlabelled and excluded — fill
    the Year on every row so nothing is silently dropped.
    """
    if COL_YEAR not in df.columns:
        return df
    years = pd.to_numeric(df[COL_YEAR], errors="coerce")
    if years.notna().sum() == 0:
        return df
    return df[years == year]


def latest_month(df: pd.DataFrame, year: int | None = None) -> str:
    """The most recent month present in the data, per ``MONTH_ORDER``.

    Scoped to ``year`` (default: the latest year in the sheet) so the label
    reflects the year actually being reported. Falls back to the last configured
    month if that year has none of them. Future-period rows are ignored (see
    ``_drop_future_rows``), so a pre-staged future month can't get picked as
    the "latest" one before it actually arrives.
    """
    df = _drop_future_rows(df)
    df = _for_year(df, year if year is not None else latest_year(df))
    present = set(_normalized_month_column(df).dropna())
    for month in reversed(MONTH_ORDER):
        if month in present:
            return month
    return MONTH_ORDER[-1]


def _earliest_year(df: pd.DataFrame, default: int) -> int:
    """The earliest reporting year in the sheet's ``Year`` column, or ``default``
    when the column is absent/blank."""
    years = pd.to_numeric(df.get(COL_YEAR, pd.Series(dtype=str)), errors="coerce").dropna()
    return int(years.min()) if not years.empty else default


def compute_all_kpis(df: pd.DataFrame, year: int | None = None) -> list[dict]:
    """Compute KPIs for each month of ``year``, carrying balance forward.

    Balance/opening-order carries forward continuously across BOTH months and
    years: a pending order (blank Loading Date) logged in December of one year
    must still count as January's opening balance the next year, and keep
    rolling forward — a year boundary is not a reset. To get that right, every
    year from the earliest one present in the sheet through the target
    ``year`` is walked chronologically (12 months each), but only the target
    year's rows are returned; earlier years are computed solely to seed the
    correct running balance.

    ``year`` defaults to the latest year in the sheet's ``Year`` column. Each
    returned row carries its ``year``. The result is trimmed on both ends: it
    stops at the latest month that actually has data in the target year (via
    ``latest_month``), so a report doesn't show empty future months; and it
    skips leading months that are both dataless (no new orders) AND carry no
    balance forward (a zero opening order), so a year that starts reporting
    partway through (e.g. business data beginning in May) doesn't pad the
    table with meaningless January-April zero rows. A month with a non-zero
    opening order is always kept, even with no new orders of its own, since
    that's exactly how a pending order carried from a prior year is shown.
    Rows pre-staged for a period that hasn't started yet are ignored (see
    ``_drop_future_rows``) — a forecasted order doesn't count until its own
    month/year actually arrives.
    """
    df = _drop_future_rows(df)
    target_year = year if year is not None else latest_year(df)
    start_year = _earliest_year(df, target_year)

    results = []
    prev_balance = 0
    for y in range(start_year, target_year + 1):
        year_df = _for_year(df, y)
        for month in MONTH_ORDER:
            kpi = compute_month_kpis(year_df, month, y, prev_balance)
            prev_balance = kpi["balance"]
            if y == target_year:
                kpi["year"] = y
                results.append(kpi)

    cutoff = MONTH_ORDER.index(latest_month(df, target_year)) + 1
    results = results[:cutoff]

    start = 0
    for i, kpi in enumerate(results):
        if kpi["new_order"] != 0 or kpi["opening_order"] != 0:
            start = i
            break
    else:
        start = max(0, len(results) - 1)
    return results[start:]


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


def _is_dispatched_in_year_month(loading: pd.Series, year: int, month: str) -> pd.Series:
    """True where the row's Loading (Dispatched) Date actually falls in
    ``month`` of ``year``.

    A dispatch counts when the loading cell holds a real date (day-first
    ``DD-MM-YYYY``) that is BOTH:

    * on or before today — a load date in the future hasn't shipped yet; and
    * in the calendar month AND year being reported on — regardless of which
      month/year the order was originally booked in, since carry-forward
      orders routinely ship later than their own Month bucket. Checking the
      year (not just the month number) matters once reports span multiple
      years, so a January-2027 dispatch never gets counted toward a
      January-2026 report just because both are "January".

    Anything else doesn't count towards this month's Despatched: a blank cell,
    the literal ``Pending``, a future-dated load, or a load that happened in a
    different month/year.
    """
    loaded = pd.to_datetime(loading, format=DATE_FORMAT, errors="coerce")
    target = MONTH_NUM.get(month.strip().upper())
    if target is None:
        return pd.Series(False, index=loading.index)
    in_target_month = (loaded.dt.month == target) & (loaded.dt.year == year)
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


def _effective_dates(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    """Per-row date: `primary` where it parses to a real date, else `fallback`.

    An explicit primary date always wins, even over a fallback date — the
    fallback is only consulted when the primary gives no date at all.
    """
    primary_dates = _dates(primary)
    fallback_dates = _dates(fallback)
    return primary_dates.where(primary_dates.notna(), fallback_dates)


def _blank_or_fallback_past(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    """True where the effective (primary-or-fallback) date is past."""
    effective = _effective_dates(primary, fallback)
    return effective.notna() & (effective < pd.Timestamp(date.today()))


def _past_or_never_given(effective: pd.Series) -> pd.Series:
    """True where a precomputed effective date (see ``_effective_dates``) is
    either past, or was never given at all (no primary or fallback date) —
    a commitment nobody has scheduled yet is still "pending", it just has
    nothing to compare against today.
    """
    return effective.isna() | (effective < pd.Timestamp(date.today()))


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


def _earliest_effective_date(mask: pd.Series, effective: pd.Series) -> str:
    """Earliest (min) date in a precomputed per-row ``effective`` date series
    (see ``_effective_dates``), among the masked rows.

    The oldest still-open commitment is that group's single most overdue
    "New Committed Date" — not an average or the latest across rows. Returns
    "" when no masked row holds a real date.
    """
    parsed = effective[mask].dropna()
    return parsed.min().strftime(DATE_FORMAT) if not parsed.empty else ""


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
    df: pd.DataFrame, month: str | None = None, year: int | None = None
) -> list[dict]:
    """Per-country breakup dashboard, one row per unique Country.

    Every KPI follows the business-logic doc (``logic_docs/Export Kpi
    project.docx``). By default this spans ALL years, not just the latest one:
    an order booked in a prior year can still be pending/overdue today, so
    scoping to one year by default would hide it, the same way scoping to one
    month would (see the ``month`` behavior below). Pass an explicit ``year``
    to scope down to just that year. If ``month`` is given, only that month's
    rows are considered. All "count" KPIs are expressed in machines (sum of
    Quantity over the matching rows); the "commitment changes" KPIs are sums of
    their respective change-count columns across the country's overdue rows.
    Rows pre-staged for a period that hasn't started yet are ignored (see
    ``_drop_future_rows``) — a forecasted order isn't "pending" until its own
    month/year actually arrives.
    """
    df = _drop_future_rows(df)
    if year is not None:
        df = _for_year(df, year)
    if df.empty or COL_COUNTRY not in df.columns:
        return []

    df = df.copy()
    if month is not None:
        # Accept the same flexible input normalize_month does (full name,
        # abbreviation, or number) rather than requiring an already-canonical
        # name — callers other than the pipeline shouldn't have to pre-resolve it.
        target = normalize_month(month) or month.strip().upper()
        df = df[_normalized_month_column(df) == target]
        if df.empty:
            return []

    qty = _to_numeric(_col(df, COL_QUANTITY))
    prdn_changes = _to_numeric(_col(df, COL_PRDN_CHANGES))
    container_changes = _to_numeric(_col(df, COL_CONTAINER_CHANGES))

    # Date columns for the latest-committed dates shown per country.
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
    machine_revision = _col(df, COL_MACHINE_REVISION)
    # Effective production commitment date per row: the Revise Date when
    # one's been given, else the (original) Production Commitment Date.
    effective_commitment_date = _effective_dates(machine_revision, machine_readiness)
    overdue_breakup = _is_blank_date(loading_date) & _blank_or_fallback_past(
        machine_revision, machine_readiness
    )
    # KPI 7A — Prdn machines pending: production not actually complete yet
    # (Production Completion Date is blank), AND the effective commitment
    # date — Revise Date if one's been given, else the original Production
    # Commitment Date — has already passed, OR no commitment date was ever
    # given at all (nothing scheduled yet is still pending, not exempt).
    production_complete = _col(df, COL_PRODUCTION_COMPLETION)
    prdn_pending = _is_blank_date(production_complete) & _past_or_never_given(
        effective_commitment_date
    )
    container_revision = _col(df, COL_CONTAINER_REVISION)
    # Effective container date per row: the Revision Date when one's been
    # given, else the (original) Container Placement date. Mirrors
    # effective_commitment_date above, just for the container KPIs.
    effective_container_date = _effective_dates(container_revision, container_placement)
    # KPI 8A — Container machines pending: the container hasn't actually
    # arrived yet (actual_container is blank), AND the effective container
    # date — Revision Date if given, else the original Placement date — has
    # already passed, OR no container date was ever given at all. Same shape
    # as KPI 7A, just for the container side.
    actual_container = _col(df, COL_ACTUAL_CONTAINER)
    container_pending = _is_blank_date(actual_container) & _past_or_never_given(
        effective_container_date
    )
    clearance_pending = _clearance_pending(_col(df, COL_CLEARANCE_STATUS))   # KPI 10

    results = []
    for country, idx in df.groupby(COL_COUNTRY).groups.items():
        if str(country).strip() == "":
            continue  # skip blank/unlabelled country rows
        rows = df.index.isin(idx)
        # KPIs 4-9 all live under the report's single "Commitment not Given -
        # Over Due days" banner alongside Over Due Breakup (KPI 3) — they're
        # a breakdown OF that overdue population, not independent counts over
        # the country's whole order book. Every one of them must be scoped to
        # overdue_breakup, or (like here) they overcount against rows that
        # already dispatched or were never overdue to begin with.
        overdue_rows = rows & overdue_breakup

        def machines(mask: pd.Series, _rows: pd.Series = rows) -> int:
            return int(qty[_rows & mask].sum())

        def total(series: pd.Series, _rows: pd.Series = rows) -> int:
            return int(series[_rows].sum())

        results.append(
            {
                "country": str(country),
                "pending_orders": machines(pending_orders),          # KPI 2
                "over_due_breakup": machines(overdue_breakup),       # KPI 3
                "days_delay": _worst_delay_days(overdue_rows, machine_readiness),  # KPI 4
                "new_committed_date": _earliest_effective_date(overdue_rows, effective_commitment_date),  # KPI 5
                "container_expected_date": _earliest_effective_date(overdue_rows, effective_container_date),  # KPI 6
                "prdn_machines_pending": machines(prdn_pending, overdue_rows),     # KPI 7A
                "prdn_commitment_changes": total(prdn_changes, overdue_rows),      # KPI 7B
                "container_machines_pending": machines(container_pending, overdue_rows),  # KPI 8A
                "container_commitment_changes": total(container_changes, overdue_rows),    # KPI 8B
                "vessel_cutoff": _min_date(overdue_rows, vessel_cutoff),     # KPI 9
                "clearance_pending": machines(clearance_pending, overdue_rows),    # KPI 10
            }
        )

    results.sort(key=lambda r: r["over_due_breakup"], reverse=True)
    return results
