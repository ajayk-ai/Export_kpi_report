"""Scenario checks for the dynamic month/year reporting logic.

Covers the real operational pattern: multiple teams edit the same sheet over
time (market team logs new orders, planning team fills in dispatch info later,
rows aren't necessarily in chronological order), and reporting must carry
opening balance forward correctly across both months AND years using the
Year column -- e.g. a pending order from Dec-2026 must show up as Jan-2027's
opening balance.

No test framework is added; this follows the same "run it, read the output"
pattern as run_local.py.

Run:  uv run python verify_month_year.py
"""
from datetime import date
from unittest.mock import patch

import pandas as pd

from app.core.kpi_engine import compute_all_kpis, compute_country_breakup, normalize_month

# All scenarios run under this fixed "today" so results never depend on (or
# drift with) the real wall-clock date. Chosen well after every non-future
# test date below, so only the explicitly-future case in TC6 counts as future.
FIXED_TODAY = date(2027, 6, 1)

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))


def _row(month, year, qty, country="TESTLAND", loading="", **overrides) -> dict:
    row = {
        "Month": month,
        "Year": year,
        "Country": country,
        "Quantity": qty,
        "Loading (Dispatched) Date": loading,
        "Commercial Clearance Status": "Pending",
        "production commitment Date": "",
        "production commitment Revise Date": "",
        "Production Completion Date": "",
        "Container Placement date": "",
        "Container Revision Date": "",
        "actual_container": "",
        "no of comm container changes": 0,
        "no of times commitment changes(prod)": 0,
        "revision commitment of loading date": "",
        "Vessel Cut-Off Date": "",
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
def test_same_year_carry_forward():
    """TC1: opening order for a month = previous month's balance (same year)."""
    df = pd.DataFrame([
        _row("MAY", 2026, 10, loading=""),            # pending -> carries to June
        _row("JUNE", 2026, 5, loading="10-06-2026"),
    ])
    kpis = {k["month"]: k for k in compute_all_kpis(df, year=2026)}
    check(
        "TC1 same_year_carry_forward: June opening == May balance (==10)",
        kpis["JUNE"]["opening_order"] == kpis["MAY"]["balance"] == 10,
        f"May balance={kpis['MAY']['balance']}, June opening={kpis['JUNE']['opening_order']}",
    )


def test_cross_year_carry_forward():
    """TC2: Dec-2026 pending order becomes Jan-2027 opening order, via the Year column."""
    df = pd.DataFrame([
        _row("DECEMBER", 2026, 8, loading=""),         # pending -> carries into 2027
        _row("JANUARY", 2027, 5, loading="05-01-2027"),
    ])
    kpis_2027 = {k["month"]: k for k in compute_all_kpis(df, year=2027)}
    check(
        "TC2 cross_year_carry_forward: Jan-2027 opening == Dec-2026 balance (==8)",
        kpis_2027["JANUARY"]["opening_order"] == 8,
        f"Jan-2027 opening={kpis_2027['JANUARY']['opening_order']}",
    )


def test_multiple_pending_orders_accumulate():
    """TC3: several teams' pending rows in the same prior month all roll forward together."""
    df = pd.DataFrame([
        _row("DECEMBER", 2026, 8, country="BRAZIL", loading=""),
        _row("DECEMBER", 2026, 4, country="INDIA", loading=""),
        _row("JANUARY", 2027, 3, country="USA", loading="05-01-2027"),
    ])
    kpis_2027 = {k["month"]: k for k in compute_all_kpis(df, year=2027)}
    check(
        "TC3 multiple_pending_orders_accumulate: Jan-2027 opening == 8+4 (==12)",
        kpis_2027["JANUARY"]["opening_order"] == 12,
        f"Jan-2027 opening={kpis_2027['JANUARY']['opening_order']}",
    )


def test_dispatched_prior_year_order_does_not_carry():
    """TC4: an order already dispatched in its own month/year must NOT carry forward."""
    df = pd.DataFrame([
        _row("DECEMBER", 2026, 8, loading="20-12-2026"),  # dispatched, not pending
        _row("JANUARY", 2027, 3, loading=""),
    ])
    kpis_2027 = {k["month"]: k for k in compute_all_kpis(df, year=2027)}
    check(
        "TC4 dispatched_prior_year_order_does_not_carry: Jan-2027 opening == 0",
        kpis_2027["JANUARY"]["opening_order"] == 0,
        f"Jan-2027 opening={kpis_2027['JANUARY']['opening_order']}",
    )


def test_row_order_in_sheet_does_not_matter():
    """TC5: rows entered out of chronological order (multi-team edits) give the same result."""
    rows = [
        _row("JANUARY", 2027, 5, loading="05-01-2027"),
        _row("DECEMBER", 2026, 8, loading=""),
    ]
    a = compute_all_kpis(pd.DataFrame(rows), year=2027)
    b = compute_all_kpis(pd.DataFrame(list(reversed(rows))), year=2027)
    check(
        "TC5 row_order_in_sheet_does_not_matter: same result regardless of row order",
        a == b,
        f"forward={a}, reversed={b}",
    )


def test_future_dispatch_date_not_counted_yet():
    """TC6: a Loading Date later than 'today' must not count as dispatched yet."""
    df = pd.DataFrame([
        _row("JULY", 2026, 10, loading="30-12-2027"),  # future relative to FIXED_TODAY
    ])
    kpis = {k["month"]: k for k in compute_all_kpis(df, year=2026)}
    check(
        "TC6 future_dispatch_date_not_counted_yet: stays pending (balance==10, dispatched==0)",
        kpis["JULY"]["balance"] == 10 and kpis["JULY"]["dispatched"] == 0,
        f"July={kpis['JULY']}",
    )


def test_future_month_year_row_is_ignored():
    """TC9: a row pre-staged for a period that hasn't started yet is ignored
    entirely -- not counted as a new order, and not shown as pending in the
    country breakup -- until its own month/year actually arrives."""
    df = pd.DataFrame([
        _row("JANUARY", 2027, 5, loading="10-01-2027"),               # already happened
        _row("DECEMBER", 2027, 15, country="FUTURELAND", loading=""),  # future period, blank dispatch
    ])
    kpis = {k["month"]: k for k in compute_all_kpis(df, year=2027)}
    check(
        "TC9a future_month_year_row_is_ignored: December doesn't appear, January unaffected",
        "DECEMBER" not in kpis and kpis["JANUARY"]["new_order"] == 5,
        f"kpis={kpis}",
    )
    countries = {b["country"] for b in compute_country_breakup(df)}
    check(
        "TC9b future_month_year_row_is_ignored: FUTURELAND absent from the breakup",
        "FUTURELAND" not in countries,
        f"countries={countries}",
    )


def test_breakup_spans_all_years_by_default():
    """TC7: country breakup shows pending orders from every year unless one is requested."""
    df = pd.DataFrame([
        _row("DECEMBER", 2026, 8, country="BRAZIL", loading=""),
        _row("JANUARY", 2027, 5, country="USA", loading="05-01-2027"),
    ])
    countries_all = {b["country"] for b in compute_country_breakup(df)}
    countries_2027_only = {b["country"] for b in compute_country_breakup(df, year=2027)}
    check(
        "TC7a breakup_spans_all_years_by_default: BRAZIL (2026) visible with no year filter",
        "BRAZIL" in countries_all,
        f"countries_all={countries_all}",
    )
    check(
        "TC7b breakup_explicit_year_scopes_down: BRAZIL excluded when year=2027",
        "BRAZIL" not in countries_2027_only,
        f"countries_2027_only={countries_2027_only}",
    )


def test_normalize_month_flexible_input():
    """TC8: REPORT_MONTH / --month / ?month= accept name, abbreviation, or number."""
    cases = [
        ("July", "JULY"), ("JUL", "JULY"), ("jul", "JULY"),
        ("7", "JULY"), ("07", "JULY"), ("garbage", None), ("", None),
    ]
    bad = [(v, e, normalize_month(v)) for v, e in cases if normalize_month(v) != e]
    check("TC8 normalize_month_flexible_input: all formats resolve correctly", not bad, str(bad))


def main() -> None:
    with patch("app.core.kpi_engine.date") as mock_date:
        mock_date.today.return_value = FIXED_TODAY
        for fn in [
            test_same_year_carry_forward,
            test_cross_year_carry_forward,
            test_multiple_pending_orders_accumulate,
            test_dispatched_prior_year_order_does_not_carry,
            test_row_order_in_sheet_does_not_matter,
            test_future_dispatch_date_not_counted_yet,
            test_future_month_year_row_is_ignored,
            test_breakup_spans_all_years_by_default,
            test_normalize_month_flexible_input,
        ]:
            fn()

    print()
    failed = [name for name, ok, _ in results if not ok]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
