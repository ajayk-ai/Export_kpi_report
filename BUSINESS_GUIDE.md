# SCM KPI Report — Guide for Business Users

This guide explains, in plain language, what each number in the KPI report
means, which sheet column it comes from, and walks through worked examples.
For the technical/engineering write-up, see
[DOCUMENTATION.md](DOCUMENTATION.md).

## 1. What is this report?

Every time it runs, the report answers two questions from the `SCM_Export`
sheet:

1. **"How is our order book moving, month by month?"** — the 5-number KPI
   table (Opening / New / Total / Despatched / Balance).
2. **"Which countries have late orders right now, and why?"** — the overdue
   breakup table, for one chosen month.

An optional AI-written summary sits on top, calling out the trend and the
biggest risk in a few sentences.

## 2. Sheet columns, in plain terms

| Sheet column | What it means for the business |
|---|---|
| `Month` | Which month this order line belongs to. |
| `Order Type (N / O)` | `N` = a brand-new order placed this month. Anything else is not counted as "new" again (it's already part of an earlier month's balance). |
| `Quantity` | How many machines/units are on this order line. This is the number that gets added up everywhere. |
| `Loading (Dispatched) Date` | The date the order actually left / was loaded for shipment. If this cell is blank or says "Pending", the order **has not shipped yet**. |
| `Country` | Which country/dealer's order this is — used to group the overdue table. |
| `over due days` | How many days past the original commitment this order currently is. `0` (or blank) = not overdue. |
| `Machine Revision Date` | The latest revised production commitment date for that order. Shown as "New Committed Date". |
| `Container Placement date` / `Container Revision Date` | When the container is expected — whichever of the two is later. Shown as "Container Expected Date". |
| `Vessel Cut-Off Date` | The shipping line's cut-off date for that order's vessel. |
| `no of times commitment changes(prod)` | How many times the factory has pushed back its production commitment for that order. |
| `no of comm container changes` | How many times the container commitment has changed. |
| `Commercial Clearance Status` | Whether export/customs clearance is done. Only `Completed / Complete / Cleared / Done / Yes` count as finished — everything else (blank, "Pending", anything else) counts as **still pending**. |

## 3. The monthly KPI table

Five numbers per month:

| Term | Plain-language meaning |
|---|---|
| **Opening Order** | Orders still owed to customers at the *start* of the month — i.e. whatever was left over (Balance) from the previous month. |
| **New Order** | Brand-new orders (Order Type = `N`) placed *during* this month. |
| **Total Order** | Opening Order + New Order — everything we owe customers this month. |
| **Despatched** | Orders whose Loading/Dispatched Date falls during this month — whichever month they actually shipped in, even if they were booked (or carried forward) in an earlier month. |
| **Balance** | Total Order − Despatched — what's still owed at month end. This becomes next month's Opening Order. |

### Worked example

Say `SCM_Export` has these rows (simplified — only the relevant columns
shown):

| Month | Order Type | Quantity | Loading Date |
|---|---|---|---|
| APRIL | N | 10 | 15-04-2026 |
| APRIL | N | 8  | *(blank — not shipped yet)* |
| MAY   | N | 12 | 20-05-2026 |
| MAY   | O | 8  | 05-05-2026 |
| JUNE  | N | 5  | *(blank — not shipped yet)* |

Walking through it month by month:

**APRIL** — Opening = 0 (nothing carried in, it's the first month).
New = 10 + 8 = **18** (both rows are Order Type `N` in April).
Total = 0 + 18 = **18**. Despatched = 10 (only the first row has a
real date). Balance = 18 − 10 = **8**.

**MAY** — Opening = **8** (April's Balance carries in).
New = 12 (only the `N` row counts; the `O` row is *not* added again — it's
already reflected via the Opening Order it belongs to).
Total = 8 + 12 = **20**. Despatched = 12 + 8 = **20** (both May rows have a
real Loading Date, regardless of order type). Balance = 20 − 20 = **0**.

**JUNE** — Opening = **0** (May's Balance).
New = 5. Total = 0 + 5 = **5**. Despatched = 0 (blank date). Balance =
5 − 0 = **5**.

So the printed table would read:

```
APRIL: Opening=0,  New=18, Total=18, Despatched=10, Balance=8
MAY:   Opening=8,  New=12, Total=20, Despatched=20, Balance=0
JUNE:  Opening=0,  New=5,  Total=5,  Despatched=0,  Balance=5
```

A positive Balance means we still owe customers units at month end; the
report highlights it in red when negative (we shipped more than we owed —
usually a sign old backlog finally went out) and green otherwise.

## 4. The overdue country breakup

This table only looks at **one month at a time** (whichever month is set in
`REPORT_MONTH`, or the latest month in the sheet if that's left blank), and
only lists a country if it currently has orders that are either **not yet
shipped** or **overdue**.

| Column | Plain-language meaning |
|---|---|
| **Over Due Breakup** | Total quantity of that country's orders that are currently overdue (`over due days` > 0). |
| **No of Days Delay from 1st Commitment** | The single worst delay among that country's overdue orders (the maximum, not an average). |
| **New Committed Date** | The latest revised production date given to that country's overdue orders. |
| **Container Expected Date** | The latest expected container date for those overdue orders. |
| **Prdn Commitment → No of machines pending** | Quantity of that country's orders (overdue or not) that haven't shipped yet. |
| **Prdn Commitment → No of commitment changes** | How many times the factory pushed back its commitment on that country's overdue orders, added up. |
| **Container Commitment → No of machines pending** | Same as production pending, from the container side (today these two numbers are usually identical). |
| **Container Commitment → No of commitment changes** | How many times the container date changed on that country's overdue orders, added up. |
| **Vessel Cut Off** | The latest vessel cut-off date among that country's overdue orders. |
| **Commercial Clearance Pending** | Quantity of that country's orders (overdue or not) where customs/export clearance isn't done yet. |
| **Sub Total row** | Straight column sum across every country. Dates are never summed. |

Countries are listed worst-first (highest Over Due Breakup at the top).

### Worked example

For June, suppose these are the only rows:

| Country | Quantity | over due days | Loading Date | Clearance Status |
|---|---|---|---|---|
| UAE | 6 | 12 | *(blank)* | Pending |
| UAE | 4 | 0  | 10-06-2026 | Completed |
| Kenya | 3 | 20 | *(blank)* | *(blank)* |

- **UAE**: has one overdue row (qty 6, 12 days late) and one on-time,
  shipped row. Over Due Breakup = **6**. Days Delay = **12**. Machines
  pending (both prod & container) = 6 (only the un-shipped row). Clearance
  Pending = 6 (the un-shipped row's status is "Pending"; the shipped row is
  "Completed" so it doesn't count).
- **Kenya**: one overdue, unshipped row. Over Due Breakup = **3**. Days
  Delay = **20**. Machines pending = 3. Clearance Pending = 3 (blank status
  counts as pending).

Kenya is worse on delay (20 days) but UAE has the bigger overdue quantity, so
UAE is listed first (sorted by quantity, not by days late).

## 5. What counts as "shipped" / "overdue" / "clearance done"?

- **Shipped/Despatched** = the `Loading (Dispatched) Date` cell holds an
  actual date in `DD-MM-YYYY` format. A blank cell or the word "Pending"
  both mean *not shipped*, even though they look different in the sheet.
- **Overdue** = `over due days` is a number greater than 0. `0`, blank, or
  text all mean *not overdue*.
- **Clearance done** = the status cell says (any case) one of: Completed,
  Complete, Cleared, Done, or Yes. Anything else — including a blank cell —
  counts as still pending.

## 6. The AI summary

If a Gemini API key is configured, the report includes a short AI-written
paragraph: 3–5 bullet points on the order/despatch trend and the biggest
overdue risk, plus one "Key Takeaway" line. It's generated fresh from the
same numbers shown in the tables — it doesn't add new data, just narrates
what's already there. If no key is set (or the AI call fails for any
reason), this section is simply left out and the rest of the report is
unaffected.

## 7. Common questions

**Why is April's Opening Order always 0?**
Because there's no earlier month in the report to carry a balance in from.
The very first month always starts at 0.

**A country shows 0 in "Over Due Breakup" but still appears — why?**
Because it still has un-shipped orders (they show up under "machines
pending"), even though none of them are late yet.

**Why doesn't "Balance" match what I expect from just this month's rows?**
Balance is cumulative — it carries forward everything unshipped from every
prior month, not just this month's new orders.

**An order was booked last month but only shipped this month — where does it show up?**
As Despatched *this* month, not the month it was booked in. Despatched is
based on the actual Loading/Dispatched Date, so a carry-forward order reduces
Balance in the month it really ships, instead of sitting in Balance forever.

**A row's Order Type isn't "N" — where does it show up?**
It's counted as Despatched if it ships in that month, and it feeds Balance
indirectly through Opening Order, but it is never added into "New Order" —
that column is reserved for brand-new orders only.
