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
   — the overdue breakup table, 13 numbers per country.

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
| `revision commitment of loading date` | A *different* column from the one above — this is the revised loading/despatch commitment. It only drives **Pending Orders**; nothing else reads it. |
| `Container Placement date` / `Container Revision Date` | When the container is expected, and any revision to that date. |
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

Two of the thirteen numbers below (**Pending Orders** and **Over Due
Breakup**) look at *all* of that country's rows. The other eleven are all
scoped to that country's **currently overdue rows** (i.e. the rows counted
in Over Due Breakup) — they're a breakdown of *why* those specific orders
are overdue, not independent counts across the country's whole order book.

> **Note:** "Pending Orders" is computed but is only shown in the plain-text
> version of the report (console/email fallback) — it does not appear as a
> column in the HTML table you see in the browser/email.

### Shared example data — one country, used for every KPI below

Assume **today is 17-Jul-2026**, and `Kenya` has exactly these 4 rows:

| Row | Qty | Loading Date | Prod. Commit. Date | Prod. Commit. Revise Date | Container Placement | Container Revision | Vessel Cut-Off | Prod. changes | Container changes | Clearance Status | revision commitment of loading date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 6 | *(blank)* | 05-06-2026 | *(blank)* | *(blank)* | *(blank)* | 20-07-2026 | 2 | 0 | Pending | *(blank)* |
| B | 4 | *(blank)* | 01-05-2026 | 10-07-2026 | 15-06-2026 | *(blank)* | 18-07-2026 | 1 | 1 | Completed | 05-07-2026 |
| C | 3 | 10-07-2026 | 01-06-2026 | *(blank)* | *(blank)* | *(blank)* | *(blank)* | 0 | 0 | Done | *(blank)* |
| D | 5 | *(blank)* | *(blank)* | *(blank)* | 25-07-2026 *(future)* | *(blank)* | *(blank)* | 0 | 0 | *(blank)* | *(blank)* |

Row C already shipped (10-07-2026 is a real, past date), so it's excluded
from every "still pending" calculation below.

---

**1. Pending Orders**
**Formula:** `SUM(Quantity)` where Loading Date is blank **OR**
`revision commitment of loading date` is a past date.
**Worked example:** A (blank loading) + B (blank loading, and its
revision-of-loading-date is also past) + D (blank loading) =
6 + 4 + 5 = **15**. (C is shipped, so excluded.)

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

Total = 6 + 4 = **10**. These two rows (A, B) are Kenya's "overdue rows" —
every KPI below is scoped to just these two.

**3. No of Days Delay from 1st Commitment**
**Formula:** `today − MIN(Production Commitment Date)` among the overdue
rows (A, B) — the single oldest date, not an average.
**Worked example:** oldest of A's 05-06-2026 and B's 01-05-2026 is
**01-05-2026**. 17-Jul-2026 − 01-May-2026 = **77 days**.

**4. New Committed Date**
**Formula:** the **earliest** effective commitment date among the overdue
rows (Revise Date if given, else original date). This is the *oldest*
still-unresolved commitment, not the newest — despite the name, it
highlights the worst-lagging promise, matching KPI 3 above.
**Worked example:** A's effective date = 05-06-2026 (no revise, falls
back). B's effective date = 10-07-2026 (has a revise date). Earliest of the
two = **05-06-2026**.

**5. Container Expected Date**
**Formula:** the **latest** `Container Placement date` among the overdue
rows. (Only the placement date feeds this — a Container Revision Date, even
if present, isn't looked at here.)
**Worked example:** A has none; B has 15-06-2026. Result = **15-06-2026**.

**6. Prdn Committment Pending → No of machines**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Production Commitment Date` is blank or past, **OR** the Revise Date is
past.
**Worked example:** A: original date past → counts (6). B: original date
past → counts (4). Total = **10**.

**7. Prdn Committment Pending → No of commitment changes**
**Formula:** `SUM(no of times commitment changes(prod))` across the
overdue rows (this used to be an average across *all* rows; it is now a
**sum across just the overdue rows**).
**Worked example:** A (2) + B (1) = **3**.

**8. Production Overdue**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Production Commitment Revise Date` specifically is past (a blank revise
date does **not** count here, even though it counts in KPI 6 above).
**Worked example:** A: revise date is blank → doesn't count (0). B: revise
date 10-07-2026 is past → counts (4). Total = **4**.

**9. Container Committment Pending → No of machines**
**Formula:** among the overdue rows, `SUM(Quantity)` where the Container
Placement date is blank, **or** it's past *and* the Container Revision Date
is either blank or also past.
**Worked example:** A: placement blank → counts (6). B: placement past,
revision blank → counts (4). Total = **10**.

**10. Container Committment Pending → No of commitment changes**
**Formula:** `SUM(no of comm container changes)` across the overdue rows
(also a sum now, not an average).
**Worked example:** A (0) + B (1) = **1**.

**11. Container Overdue**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Container Revision Date` specifically is past.
**Worked example:** neither A nor B has a revision date set → **0**. (Note
this is smaller than KPI 9's "no of machines pending" — a row can be
*pending* a container commitment without yet being formally *overdue* on a
revised container date.)

**12. Vessel Cut off**
**Formula:** the **earliest** `Vessel Cut-Off Date` among the overdue rows.
**Worked example:** A = 20-07-2026, B = 18-07-2026 → earliest =
**18-07-2026**.

**13. Commerical Clearance no of Pending**
**Formula:** among the overdue rows, `SUM(Quantity)` where
`Commercial Clearance Status` is blank or literally "Pending".
**Worked example:** A: "Pending" → counts (6). B: "Completed" → doesn't
count. Total = **6**.

---

So Kenya's printed row would read:

```
Kenya: Pending=15, OverDue=10, DaysDelay=77, NewCommitted=05-06-2026,
       ContainerExpected=15-06-2026, Vessel=18-07-2026,
       Prdn(pending=10, changes=3, overdue=4),
       Container(pending=10, changes=1, overdue=0),
       ClearancePending=6
```

Countries are listed **worst-first**, sorted by Over Due Breakup (KPI 2) —
not by Days Delay, so a country with a smaller quantity but longer delay can
still be listed below one with a bigger quantity but shorter delay.

The **Sub Total** row at the bottom only totals the "count" columns
(Pending Orders isn't shown there since it isn't in the HTML table either;
Over Due Breakup, both "No of machines" pairs, both Overdue columns, and
Clearance Pending are summed). Days Delay, the two "No of commitment
changes" columns, and every date column are left blank in Sub Total — an
oldest-date, a change count, or a date doesn't mean anything once you add it
across countries.

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

**Why is "No of machines pending" bigger than "Overdue" for the same
commitment (production or container)?**
Pending counts a broader condition (no date given yet, *or* the date is
past); Overdue only counts rows where a **revised** date has specifically
been given and has itself now passed. A row that's late on its original
date but hasn't been given a revision yet is pending, not yet overdue.
