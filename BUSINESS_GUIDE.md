# SCM KPI Report — Guide for Business Users

This guide explains, in plain language, what each number in the KPI report
means, exactly how it's calculated (formula), which sheet column(s) it comes
from, and a worked example. For the technical/engineering write-up, see
[DOCUMENTATION.md](DOCUMENTATION.md).

Every formula below is taken directly from the current code in
[app/core/kpi_engine.py](app/core/kpi_engine.py) — if the sheet or the code
changes, re-check this guide against that file rather than assuming it's
still accurate.

## 1. What is this report?

Every time it runs, the report answers two questions from the `SCM_Export`
sheet:

1. **"How is our order book moving, month by month?"** — the 5-number KPI
   table (Opening / New / Total / Despatched / Balance).
2. **"Which countries have pending or overdue orders right now, and why?"**
   — the overdue breakup table, 11 numbers per country.

An optional AI-written summary sits on top, calling out the trend and the
biggest risk in a few sentences.

## 2. Sheet columns, in plain terms

| Sheet column | What it means for the business |
|---|---|
| `Month` | Which month this order line was booked in. Every row belongs to exactly one month — there is no separate "carried forward" row; a row that ships late is simply edited in place, and its Loading Date decides which month gets credit for the despatch (see §3). |
| `Quantity` | How many machines/units are on this order line. This is the number that gets added up for every KPI in this report. |
| `Loading (Dispatched) Date` | The date the order actually left / was loaded for shipment. If this cell is blank or says "Pending" (or holds a future date), the order **has not shipped yet**. |
| `Country` | Which country/dealer's order this is — used to group the breakup table, one row per country. |
| `Production Commitment Date` | When the machine was originally due to be ready. |
| `Production Commitment Revise Date` | The factory's latest revised production commitment, when one has been given. Wins over the original date wherever both are used. |
| `Production Completion Date` | When production actually finished. If this is filled in, the machine is no longer counted as "pending" on production — even if its commitment date has passed — because the work is genuinely done. |
| `revision commitment of loading date` | A *different* column from the one above — this is the revised loading/despatch commitment. It only drives **Pending Orders**; nothing else reads it. |
| `Container Placement date` / `Container Revision Date` | When the container is expected, and any revision to that date. |
| `actual_container` | When the container actually arrived/was assigned. If this is filled in, the order is no longer counted as "pending" on the container — mirrors `Production Completion Date` above, just for the container side. |
| `Vessel Cut-Off Date` | The shipping line's cut-off date for that order's vessel. |
| `no of times commitment changes(prod)` | How many times the factory has pushed back its production commitment for that order. |
| `no of comm container changes` | How many times the container commitment has changed for that order. |
| `Commercial Clearance Status` | Export/customs clearance status. Only a **blank cell** or the literal word **"Pending"** (any capitalisation) count as pending — every other value (Completed, Cleared, Done, Yes, or anything else you type in there, typos included) is treated as cleared. |
| `over due days` | A legacy column, kept in the sheet but no longer used by any KPI in this report. |

## 3. The monthly summary table

Five numbers per month, each with its formula and its own worked example.

### Opening Order
> Orders still owed to customers at the *start* of the month.

**Formula:** `Opening Order(month) = Balance(previous month)` — and `0` for
the first month in the report (nothing to carry in).

**Worked example:** April is the first month in the report, so April's
Opening Order = **0**. April's Balance comes out to 8 (see the Balance
example below) — so May's Opening Order = **8**.

### New Order
> Brand-new order quantity booked *in* this month.

**Formula:** `New Order(month) = SUM(Quantity)` for every row whose `Month`
cell equals this month — regardless of when (or whether) it later ships.

**Worked example:** Two rows are booked in April: qty 10 and qty 8.
New Order (April) = 10 + 8 = **18**.

### Total Order
> Everything we owe customers this month.

**Formula:** `Total Order = Opening Order + New Order`

**Worked example:** May's Opening Order = 8 (April's Balance), and May's New
Order = 12 (one row booked in May). Total Order (May) = 8 + 12 = **20**.

### Despatched
> Orders that actually shipped during this calendar month.

**Formula:** `Despatched(month) = SUM(Quantity)` for every row whose
`Loading (Dispatched) Date` is a real, parseable date that is **on or before
today** *and* whose calendar month matches — no matter which `Month` the row
was originally booked under. A row booked in April that finally ships in
June is credited to June's Despatched, not April's.

**Worked example:** A qty-8 row was booked in April, but its
`Loading (Dispatched) Date` doesn't get filled in until **10-06-2026**.
That date falls in June, so this row contributes 0 to April's Despatched and
0 to May's Despatched — it only counts once, as **8**, toward **June's**
Despatched, the month it actually shipped.

### Balance
> What's still owed at month end. Becomes next month's Opening Order.

**Formula:** `Balance = Total Order − Despatched`

A negative Balance (shown in red) means more shipped this month than was
owed — usually old backlog finally clearing out. Non-negative Balance is
shown in green.

**Worked example:** April's Total Order = 18 and April's Despatched = 10
(only one of the two April rows has shipped so far). Balance (April) =
18 − 10 = **8**. This 8 becomes May's Opening Order.

### Putting it all together — a full multi-month walkthrough

Rows in the sheet (only the relevant columns shown):

| Month | Quantity | Loading Date |
|---|---|---|
| APRIL | 10 | 15-04-2026 |
| APRIL | 8  | *(blank at first — see below)* |
| MAY   | 12 | 20-05-2026 |
| JUNE  | 5  | *(blank — still not shipped)* |

Suppose the April qty-8 row doesn't actually ship until **10-06-2026** — the
same row just gets its `Loading Date` filled in that day; it doesn't turn
into a new row.

**APRIL** — Opening = 0 (first month). New = 10 + 8 = **18** (both rows
belong to April). Despatched = **10** (only the first row's date falls in
April so far — the second row is still blank at this point). Total = 0 + 18
= **18**. Balance = 18 − 10 = **8**.

**MAY** — Opening = **8** (April's balance). New = **12** (May's own row).
Total = 8 + 12 = **20**. Despatched = **12** (only the May row's date falls
in May — the April qty-8 row hasn't shipped yet). Balance = 20 − 12 = **8**.

**JUNE** — Opening = **8** (May's balance — still the same unshipped April
units). New = **5** (June's own row). Total = 8 + 5 = **13**. Despatched =
**8** — the April qty-8 row's Loading Date (10-06-2026) now falls in June,
so June gets credit for it, even though it was booked in April. June's own
row is still blank, so it contributes 0. Balance = 13 − 8 = **5**.

```
APRIL: Opening=0, New=18, Total=18, Despatched=10, Balance=8
MAY:   Opening=8, New=12, Total=20, Despatched=12, Balance=8
JUNE:  Opening=8, New=5,  Total=13, Despatched=8,  Balance=5
```

This is the whole point of despatch-by-actual-ship-date: the April backlog
doesn't vanish from the report and doesn't get double counted — it sits in
Balance until the month it truly ships, then reduces Balance in *that*
month.

## 4. The country overdue breakup

One row per unique, non-blank `Country`. By default this table looks across
**all months in the sheet** (not just the latest one), so a stale order
booked months ago still shows up if it's still pending — set `REPORT_MONTH`
if you want it scoped to a single month instead.

Two of the eleven numbers below (**Pending Orders** and **Over Due
Breakup**) look at *all* of that country's rows. The other nine are all
scoped to that country's **currently overdue rows** (i.e. the rows counted
in Over Due Breakup) — they're a breakdown of *why* those specific orders
are overdue, not independent counts across the country's whole order book.

> **Note:** "Pending Orders" is computed but is only shown in the plain-text
> version of the report (console/email fallback) — it does not appear as a
> column in the HTML table you see in the browser/email.

> **There used to be a "Production Overdue" and a "Container Overdue"
> column here too.** Both were removed — they were a narrower, and
> confusingly named, subset of "No of machines pending" that only fired
> once a *revision* date specifically existed and had slipped again. The
> "No of machines pending" KPIs (6 and 8 below) now carry that signal, with
> an extra check against whether the work is actually done yet.

### Shared example data — one country, used for every KPI below

Assume **today is 17-Jul-2026**, and `Kenya` has exactly these 5 rows:

| Row | Qty | Loading Date | Prod. Commit. Date | Prod. Commit. Revise Date | Prod. Completion Date | Container Placement | Container Revision | actual_container | Vessel Cut-Off | Prod. changes | Container changes | Clearance Status | revision commitment of loading date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 6 | *(blank)* | 05-06-2026 | *(blank)* | *(blank)* | *(blank)* | *(blank)* | *(blank)* | 20-07-2026 | 2 | 0 | Pending | *(blank)* |
| B | 4 | *(blank)* | 01-05-2026 | 10-07-2026 | *(blank)* | 15-06-2026 | *(blank)* | *(blank)* | 18-07-2026 | 1 | 1 | Completed | 05-07-2026 |
| C | 3 | 10-07-2026 | 01-06-2026 | *(blank)* | *(blank)* | *(blank)* | *(blank)* | *(blank)* | *(blank)* | 0 | 0 | Done | *(blank)* |
| D | 5 | *(blank)* | *(blank)* | *(blank)* | *(blank)* | 25-07-2026 *(future)* | *(blank)* | *(blank)* | *(blank)* | 0 | 0 | *(blank)* | *(blank)* |
| E | 7 | *(blank)* | 10-06-2026 | *(blank)* | 15-07-2026 | 12-07-2026 | *(blank)* | 18-07-2026 | 22-07-2026 | 1 | 2 | Completed | *(blank)* |

Row C already shipped (10-07-2026 is a real, past date), so it's excluded
from every "still pending" calculation below. Row E is deliberately built
to show what "already done" looks like: it's late on its original
commitment dates, but both `Production Completion Date` and
`actual_container` are filled in — the work actually happened, it just
happened after the original promise.

---

**1. Pending Orders**
**Formula:** `SUM(Quantity)` where Loading Date is blank **OR**
`revision commitment of loading date` is a past date.
**Worked example:** every row except C has a blank Loading Date:
A (6) + B (4) + D (5) + E (7) = **22**. (C is shipped, so excluded.)

**2. Over Due Breakup**
**Formula:** `SUM(Quantity)` where Loading Date is blank **AND** the
*effective* production commitment date is past — using
`Production Commitment Revise Date` if one's been given, otherwise falling
back to `Production Commitment Date`.
**Worked example:**
- A: no revise date → falls back to 05-06-2026, which is past → counts (6).
- B: revise date 10-07-2026 is past → counts (4).
- D: no revise date and no original date either → no effective date at all
  → **not** counted (a commitment that was never given isn't "overdue" yet,
  it's just "pending" — see KPI 1).
- E: no revise date → falls back to 10-06-2026, which is past → counts (7).

Total = 6 + 4 + 7 = **17**. These three rows (A, B, E) are Kenya's "overdue
rows" — every KPI below is scoped to just these three.

**3. No of Days Delay from 1st Commitment**
**Formula:** `today − MIN(Production Commitment Date)` among the overdue
rows (A, B, E) — the single oldest date, not an average.
**Worked example:** oldest of A's 05-06-2026, B's 01-05-2026, and E's
10-06-2026 is **01-05-2026**. 17-Jul-2026 − 01-May-2026 = **77 days**.

**4. New Committed Date**
**Formula:** the **earliest** effective commitment date among the overdue
rows (Revise Date if given, else original date). This is the *oldest*
still-unresolved commitment, not the newest — despite the name, it
highlights the worst-lagging promise, matching KPI 3 above.
**Worked example:** A's effective date = 05-06-2026 (no revise, falls
back). B's effective date = 10-07-2026 (has a revise date). E's effective
date = 10-06-2026 (no revise, falls back). Earliest of the three =
**05-06-2026**.

**5. Container Expected Date**
**Formula:** per row, the *effective* container date — `Container Revision
Date` if one's been given, else `Container Placement date` — then the
**earliest** such date among the overdue rows. Same fallback-then-earliest
shape as New Committed Date (KPI 4), just for container dates.
**Worked example:** none of A, B, or E has a Container Revision Date, so
all fall back to their Placement date. A's placement is blank too (no
effective date at all — excluded). B's placement is 15-06-2026. E's
placement is 12-07-2026. Earliest of the two available = **15-06-2026**.

**6. Prdn Committment Pending → No of machines**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Production Completion Date` is blank **AND** (the effective commitment
date — Revise Date if given, else original — is past, **or** no commitment
date was ever given at all).
**Worked example:**
- A: completion blank, effective 05-06-2026 is past → counts (6).
- B: completion blank, effective 10-07-2026 is past → counts (4).
- E: `Production Completion Date` is filled in (15-07-2026) → **excluded
  outright**, even though its own commitment date (10-06-2026) is also
  past — the machine is actually done, so it isn't "pending" anymore.

Total = 6 + 4 = **10**.

**7. Prdn Committment Pending → No of commitment changes**
**Formula:** `SUM(no of times commitment changes(prod))` across the
overdue rows (all three — this count isn't gated by completion status, it's
just a history of how often the commitment moved).
**Worked example:** A (2) + B (1) + E (1) = **4**.

**8. Container Committment Pending → No of machines**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`actual_container` is blank **AND** (the effective container date —
Revision Date if given, else Placement date — is past, **or** no container
date was ever given at all).
**Worked example:**
- A: `actual_container` blank, and neither Container Revision nor Placement
  was ever given → **counts anyway (6)** — a container nobody has even
  scheduled yet is still pending, not exempt.
- B: `actual_container` blank, effective placement 15-06-2026 is past →
  counts (4).
- E: `actual_container` is filled in (18-07-2026) → **excluded outright**,
  even though its placement date (12-07-2026) is also past — the container
  actually arrived.

Total = 6 + 4 = **10**.

**9. Container Committment Pending → No of commitment changes**
**Formula:** `SUM(no of comm container changes)` across the overdue rows
(also not gated by `actual_container`).
**Worked example:** A (0) + B (1) + E (2) = **3**.

**10. Vessel Cut off**
**Formula:** the **earliest** `Vessel Cut-Off Date` among the overdue rows.
**Worked example:** A = 20-07-2026, B = 18-07-2026, E = 22-07-2026 →
earliest = **18-07-2026**.

**11. Commerical Clearance no of Pending**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Commercial Clearance Status` is blank or literally "Pending".
**Worked example:** A: "Pending" → counts (6). B: "Completed" → doesn't
count. E: "Completed" → doesn't count. Total = **6**.

---

So Kenya's printed row would read:

```
Kenya: Pending=22, OverDue=17, DaysDelay=77, NewCommitted=05-06-2026,
       ContainerExpected=15-06-2026, Vessel=18-07-2026,
       Prdn(pending=10, changes=4),
       Container(pending=10, changes=3),
       ClearancePending=6
```

Countries are listed **worst-first**, sorted by Over Due Breakup (KPI 2) —
not by Days Delay, so a country with a smaller quantity but longer delay can
still be listed below one with a bigger quantity but shorter delay.

The **Sub Total** row at the bottom only totals the "count" columns
(Pending Orders isn't shown there since it isn't in the HTML table either;
Over Due Breakup, both "No of machines" columns, and Clearance Pending are
summed). Days Delay, the two "No of commitment changes" columns, and every
date column are left blank in Sub Total — an oldest-date, a change count,
or a date doesn't mean anything once you add it across countries.

### One structural quirk worth knowing

"Prdn – No of machines pending" can never fall into its own "no commitment
date was ever given" branch — a row can only be in the overdue-rows group
in the first place (KPI 2) if it *has* a real effective production
commitment date. That branch only ever fires for **Container** pending
(KPI 8), because a row's overdue status is decided entirely by its
*production* dates — a row can be overdue on production while having zero
container information at all, as row A shows above.

## 5. What counts as "shipped" / "overdue" / "clearance done"?

- **Shipped/Despatched** = the `Loading (Dispatched) Date` cell holds a real
  date in `DD-MM-YYYY` format that is on or before today. A blank cell, the
  word "Pending", or a future-dated cell all mean *not shipped yet*.
- **Overdue** (drives Over Due Breakup and everything scoped to it) = not
  yet shipped, and the *effective* production commitment date has passed:
  `Production Commitment Revise Date` if one's been given, otherwise
  `Production Commitment Date`. A row with **no** commitment date given at
  all is "pending" but not yet "overdue" — there's nothing to be late
  against.
- **Clearance done** = anything other than a blank cell or the literal word
  "Pending" (case-insensitive). This is intentionally permissive — a status
  cell with a typo or an unexpected value (e.g. "In progress") is treated
  as cleared, since only "blank" and "Pending" are recognised as not-done.

## 6. The AI summary

If a Gemini API key is configured, the report includes a short AI-written
paragraph: 3–5 bullet points on the order/despatch trend and the biggest
overdue risk, plus one "Key Takeaway" line, generated from the top 3 overdue
countries (only those with `over_due_breakup > 0`) plus every month's KPI
line. It's generated fresh from the same numbers shown in the tables — it
doesn't add new data, just narrates what's already there. If no key is set
(or the AI call fails for any reason), this section is simply left out and
the rest of the report is unaffected.

## 7. Common questions

**Why is the first month's Opening Order always 0?**
Because there's no earlier month in the report to carry a balance in from.

**A country shows 0 in "Over Due Breakup" but still appears — why?**
Because it still has un-shipped orders (they show up under "Pending
Orders" and possibly "No of machines pending"), even though none of them
are late yet — for example, a row with no commitment date given at all.

**Why doesn't "Balance" match what I expect from just this month's rows?**
Balance is cumulative — it carries forward everything unshipped from every
prior month, not just this month's new orders.

**An order was booked last month but only shipped this month — where does it show up?**
As Despatched *this* month, not the month it was booked in — the same sheet
row just gets its Loading Date filled in when it ships. See the worked
example in §3.

**Why does "New Committed Date" show an older date than I expected?**
It's not the newest revision — it's the *earliest* effective commitment
date among that country's currently overdue rows, i.e. the oldest
unresolved promise. It's meant to line up with "Days Delay from 1st
Commitment" (§4, KPI 3), which is also driven by the oldest date.

**A row's commitment date is clearly in the past, but it's not counted in
"No of machines pending" — why?**
Check `Production Completion Date` (or `actual_container` for the
container side). If either is filled in, the work is actually done, even
though it happened after the original promise — so it's no longer
"pending," it's just late history. See row E in the §4 worked example.

**Why does a row with literally no commitment date show up in "No of
machines pending" at all?**
A machine with nothing scheduled yet — no original date, no revision — is
still pending; there's just nothing to compare against today. This only
ever shows up on the **container** side in practice (KPI 8), since a row
can only be counted as overdue in the first place (KPI 2) if it has a real
*production* commitment date — see "One structural quirk worth knowing" at
the end of §4.
