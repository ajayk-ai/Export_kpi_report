# SCM KPI Automation — Documentation

This document explains what the project does, how the pieces fit together, and
— most importantly — the exact business logic behind every KPI and breakup
number it produces. For install/run instructions see [README.md](README.md).

## 1. What it does

A scheduled/on-demand script that:

1. Reads an SCM (Supply Chain Management) order export from a Google Sheet.
2. Computes monthly order KPIs (Opening / New / Total / Despatched / Balance)
   with balance carried forward month to month.
3. Computes a per-country "overdue orders" breakup for one month.
4. Optionally asks Gemini to write a 3–5 bullet executive summary of the above.
5. Renders everything as plain text (console) and as an HTML report styled to
   look like the source sheet's "SUMMARY" tab.
6. Optionally emails the HTML report (with plain-text fallback) over SMTP.
7. Serves the same report **live** over a FastAPI web app for browser preview.

It can be driven three ways — all share the one `build_report()` pipeline:

```bash
uv run python main.py                    # CLI: print the KPI summary
uv run python main.py --send             # CLI: print and email it
uv run uvicorn app.main:app --reload     # Web: live report at /report
```

## 2. Architecture / data flow

```
                 .env  ──────────────► app/config.py (Settings)
                                             │
config/service.json (Google creds) ─────────┤
                                             ▼
     app/core/data_source.py ── from_sheet() ─► app/clients/sheets_client.py ─┐
        │  from_local()                            (Google Sheet -> DataFrame) │
        └─► data/test_data.xlsx (offline) ─────────────────────────────────────┤
                                             ▼
                                   app/core/kpi_engine.py
                              (compute_all_kpis, compute_country_breakup)
                                             │
                          ┌──────────────────┼──────────────────┐
                          ▼                                     ▼
            app/clients/gemini_client.py              app/core/report.py
              (generate_summary — optional)        (text_summary / html_report)
                          │                                     │
                          └──────────────┬──────────────────────┘
                                         ▼
                          app/core/pipeline.py :: build_report()
                                         │
              ┌──────────────────┬───────┴───────────┬───────────────────┐
              ▼                  ▼                   ▼                   ▼
      main.py (CLI print)   run(send=True)     app/api/routes.py     /report.json
                                 │            (GET /report -> HTML)
                                 ▼
                      app/clients/email_client.py (SMTP, HTML + text)
```

`app/core/pipeline.py::build_report()` is the single orchestration point — the
CLI (`run`), the web routes, and the emailer all go through it, so console,
browser, and email always show the identical report:

```
df = data_source.load(source)              # 'sheet' (default) or 'local'
kpis = compute_all_kpis(df)
report_month = month_override or REPORT_MONTH or latest_month(df)   # summary/subject label
breakup = compute_country_breakup(df, month=month_override or REPORT_MONTH or None)
                                           # None = ALL months (see §5.2)
ai_summary = generate_summary(kpis, breakup)   # skipped when use_ai=False
-> ReportResult(report_month, kpis, breakup, ai_summary, text, html)
```

The monthly summary is per-month, but the **breakup spans all months by
default** — an order booked in a prior month can still be pending/overdue today,
so scoping it to one month would hide it. Set `REPORT_MONTH` (or pass `month=`)
only if you deliberately want a single-month breakup.

Every function in `kpi_engine.py` is a **pure function over a DataFrame** —
no I/O, no side effects — which is what makes the KPI math easy to reason
about and test independently of Sheets/SMTP/Gemini.

## 3. Module reference

| File | Responsibility |
|---|---|
| [main.py](main.py) | CLI entry point (`argparse`); prints the summary, optionally passes `--send`. |
| [run_local.py](run_local.py) | Offline runner: compute from a local `.xlsx` and write an HTML preview. |
| [app/main.py](app/main.py) | FastAPI application factory; run with `uvicorn app.main:app`. |
| [app/api/routes.py](app/api/routes.py) | HTTP endpoints: `/report` (live HTML — the email template), `/report.json`, `/send`, `/health`, `/`. |
| [app/config.py](app/config.py) | Loads `.env` once into a frozen `Settings` dataclass (`settings`). Also injects the OS trust store into `ssl` so corporate TLS-inspection proxies don't break HTTPS calls. |
| [app/core/data_source.py](app/core/data_source.py) | Chooses the data source — the live Google Sheet or a local `.xlsx` — returning the same string-typed DataFrame either way. |
| [app/clients/sheets_client.py](app/clients/sheets_client.py) | Authenticates with a Google service account (optionally impersonating a Workspace user via domain-wide delegation) and pulls the worksheet into a `pandas.DataFrame` via `gspread`. |
| [app/core/kpi_engine.py](app/core/kpi_engine.py) | All business logic / math. See §4 and §5 below. |
| [app/clients/gemini_client.py](app/clients/gemini_client.py) | Builds a prompt from the KPIs + breakup and asks Gemini for an executive summary. Fully optional — degrades to `""` silently on any error or missing API key. |
| [app/core/report.py](app/core/report.py) | Pure rendering: turns KPI/breakup dicts into a plain-text string and into a styled, inline-CSS HTML block (email-client-safe, no external CSS/JS). |
| [app/clients/email_client.py](app/clients/email_client.py) | Sends the report over SMTP (SSL on port 465, STARTTLS otherwise), `multipart/alternative` so clients without HTML fall back to plain text. |
| [app/core/pipeline.py](app/core/pipeline.py) | `build_report()` wires the above together end-to-end; the only place that calls more than one module. `run()` adds the email side effect. |

## 4. Expected sheet shape

The source is the `SCM_Export` worksheet (configurable via `WORKSHEET_NAME`),
read with `worksheet.get_all_records()` — so **row 1 must be a header row**
and every other row is one order line. Relevant columns (see
`kpi_engine.py` constants for the exact strings — some header names are kept
as-is including a sheet typo that's intentionally tolerated):

| Column | Used for |
|---|---|
| `Month` | Which monthly bucket a row belongs to (`MAY`, `JUNE`, `JULY`, …). |
| `Quantity` | The unit count summed for every KPI/breakup metric. |
| `Loading (Dispatched) Date` | A valid `DD-MM-YYYY` date that is on/before today = dispatched, attributed to **whichever calendar month the date itself falls in** (not necessarily the order's own `Month` bucket — carry-forward orders often ship later); blank, `Pending`, or a future date = still open. Blank here is also the first check for "Over Due Breakup" — a dispatched row is never overdue. |
| `Country` | Groups the breakup; one row per unique country. |
| `revision commitment of loading date` | Latest = each country's "New Committed Date"; earlier than today also counts toward "Pending Orders". |
| `Production Commitment Date` | Among a country's overdue rows, the oldest one vs. today (in days) = "No of Days Delay from 1st Commitment". Blank, or given but superseded by an overdue `Production Commitment Revise Date`, = counted in "Prdn – No of machines" pending. Also the fallback for "Over Due Breakup" when `Production Commitment Revise Date` is blank. |
| `Production Commitment Revise Date` | Earlier than today = counted in "Production Overdue" **and**, if `Production Commitment Date` is also given, in "Prdn – No of machines" pending. For an undispatched row, earlier than today also counts toward "Over Due Breakup" — checked ahead of `Production Commitment Date`, which only applies when this cell is blank. |
| `Container Placement date` | Blank, or given but overdue with no `Container Revision Date` set yet, = counted in "Container – No of machines" pending; latest = "Container Expected Date". |
| `Container Revision Date` | Earlier than today = counted in "Container Overdue". Once set, the row stops counting toward "Container – No of machines" pending even if `Container Placement date` is overdue. |
| `Vessel Cut-Off Date` | Shown as-is per country (earliest). |
| `no of times commitment changes(prod)` *(or the sheet's misspelling `commitement`)* | Averaged as "Prdn commitment changes". |
| `no of comm container changes` | Averaged as "Container commitment changes". |
| `Commercial Clearance Status` | Literally `Pending` or blank counts as clearance pending; anything else is cleared. |
| `over due days` | Legacy column; retained but no longer drives the breakup KPIs. |

Dates are parsed strictly as `DD-MM-YYYY` (`kpi_engine.DATE_FORMAT`); anything
that doesn't match (blank, `"Pending"`, other formats) parses to `NaT` and is
treated as "not a real date" — e.g. not dispatched.

## 5. KPI logic in detail

### 5.1 Monthly Opening / New / Total / Despatched / Balance

`compute_month_kpis(df, month, prev_balance)`:

```
opening_order  = prev_balance                                   # carried from previous month
new_order      = SUM(Quantity) WHERE Month == month             # every order line booked in the month
total_order    = opening_order + new_order
dispatched     = SUM(Quantity) WHERE Loading Date is a real date, on/before today,
                                     AND falls in this calendar month
                                     # regardless of the row's own Month bucket —
                                     # a carry-forward order ships later than it was booked
balance        = total_order - dispatched                       # = open orders still pending dispatch
```

`compute_all_kpis(df)` runs this for every month in
`MONTH_ORDER = ["MAY", "JUNE", "JULY"]` **in order**, feeding each month's
`balance` in as the next month's `opening_order` (starting at 0 for the first
month). To add a new month, extend `MONTH_ORDER` — nothing else needs to
change.

An order is "open" when its `Loading (Dispatched) Date` is blank/`Pending`;
`balance` is exactly those still-open units. `Despatched` is keyed off the
Loading Date's own month, not the row's `Month` bucket, so a carry-forward
order dispatched in a later month reduces *that* month's balance rather than
sitting uncounted forever. Because dispatch is attributed by actual ship date,
`dispatched` is no longer guaranteed `<= new_order`; `balance` can dip negative
if more ships in a month than was owed (old backlog clearing out) — the report
highlights that case. There is no longer an `Order Type (N / O)` column —
every line is counted in the month it belongs to.

`latest_month(df)` — used when `REPORT_MONTH` is blank — returns the last
month (per `MONTH_ORDER`) that actually appears in the sheet's `Month`
column (case/whitespace-insensitive), falling back to the last configured
month name if none match.

### 5.2 Per-country breakup

`compute_country_breakup(df, month)` — restricted to the target month if
given, otherwise **the whole sheet (all months)**, which is how the pipeline
calls it by default so prior-month pending/overdue orders still surface.
Follows the business-logic doc
(`logic_docs/Export Kpi project.docx`) exactly: **every unique, non-blank
`Country` produces one row** (there is no "drop countries with nothing
outstanding" filter — the doc's "display all unique countries" is authoritative).

Each "count" KPI is expressed in **machines** = `SUM(Quantity)` over the rows
matching that KPI's condition; each "commitment changes" KPI is an **average**
of its change-count column across the country's rows:

| Field | Doc KPI | Logic |
|---|---|---|
| `pending_orders` | Pending Orders | `SUM(Quantity)` where `Loading (Dispatched) Date` is blank **or** `revision commitment of loading date` is earlier than today. |
| `over_due_breakup` | Overdue Breakup | `SUM(Quantity)` where `Loading (Dispatched) Date` is blank **and** the effective production commitment is earlier than today — `Production Commitment Revise Date` if it's given, else `Production Commitment Date`. |
| `days_delay` | Days Delay from 1st Commitment | Among the country's overdue rows (`over_due_breakup` mask), the oldest `Production Commitment Date` vs. today, in days — the single worst delay, not an average. 0 if none of those rows has a real date. |
| `new_committed_date` | New Committed Date | latest `revision commitment of loading date`. |
| `container_expected_date` | Container Expected Date | latest `Container Placement date`. |
| `prdn_machines_pending` | Prdn – No of machines | `SUM(Quantity)` where `Production Commitment Date` is blank **or** `Production Commitment Revise Date` is earlier than today (same blank-or-revised-is-late shape as `pending_orders`). |
| `prdn_commitment_changes` | Prdn – Commitment Changes | `AVG(no of times commitment changes(prod))`. |
| `prdn_overdue` | Production Overdue | `SUM(Quantity)` where `Production Commitment Revise Date` is earlier than today. |
| `container_machines_pending` | Container – No of machines | `SUM(Quantity)` where `Container Placement date` is blank, **or** it's overdue and `Container Revision Date` is still blank (once a revision date is set, the row is tracked via `container_overdue` instead). |
| `container_commitment_changes` | Container – Commitment Changes | `AVG(no of comm container changes)`. |
| `container_overdue` | Container Overdue | `SUM(Quantity)` where `Container Revision Date` is earlier than today. |
| `vessel_cutoff` | Vessel Cut-Off | earliest `Vessel Cut-Off Date`. |
| `clearance_pending` | Commercial Clearance no of Pending | `SUM(Quantity)` where `Commercial Clearance Status` is literally `Pending` or blank. |

Countries are sorted **descending by `over_due_breakup`** (worst first). The
"Sub Total" row totals the count columns only (`_SUM_KEYS`); average and date
columns are left blank because summing an average or a date isn't meaningful.

Missing columns don't raise — `_col()` substitutes an all-blank column, so a
country/date field contributes 0/"" rather than crashing the whole report if
a sheet tab is missing one of the A–T columns.

## 6. AI summary (optional)

`generate_summary(kpis, breakup)` is skipped entirely (returns `""`) if
`GEMINI_API_KEY` is blank, and also degrades to `""` on any exception (no
network, blocked endpoint, bad key, etc.) so a Gemini outage never breaks the
KPI report. When it runs, the prompt includes every month's KPI line plus the
top 3 overdue countries (only those with `over_due_breakup > 0`), and asks
for 3–5 bullet points plus a `Key Takeaway:` line. `report.py` then
specifically parses lines starting with `-`/`•`/`*` as bullets and the
`Key Takeaway:` line for special styling in the HTML email.

## 7. Rendering

- `text_summary()` — used for both console output and the email's plain-text
  fallback part. One line per month, optionally prefixed with the AI summary
  and suffixed with the country breakup (with a computed subtotal row).
- `html_report()` — a single self-contained `<div>` with inline styles only
  (required since email clients strip `<style>`/external CSS). The breakup
  table intentionally mirrors the source Google Sheet's look: a yellow date
  banner + pink "Commitment not Given" banner over a 3-row header. Zero
  values in breakup cells are rendered blank (`_num()`) to match the sheet's
  visual convention of not writing "0" everywhere.

## 8. Email delivery

`send_summary_email()` requires `SMTP_USER`/`SMTP_PASSWORD` (raises if
either is missing). Builds a `multipart/alternative` message (text + HTML)
and sends via SSL on port 465 or STARTTLS otherwise. `pipeline.run()` also
stamps the subject with the report month and a `DD-MMM-YYYY HH:MM:SS`
timestamp so that repeated/looped sends don't collapse into a single Gmail
thread.

## 9. Configuration reference

All settings load once, at import time, into the frozen `src.config.settings`
object — see [.env.example](.env.example) for the full list and defaults.
Required: `SHEET_ID`. Everything else has a default or is optional
(`REPORT_MONTH`, `GOOGLE_DELEGATED_USER`, `GEMINI_API_KEY` may be left
blank). `EMAIL_RECIPIENT` is only required when running with `--send`.

## 10. Extending

- **New month**: add it to `MONTH_ORDER` in `kpi_engine.py`.
- **New/renamed sheet column**: update the matching `COL_*` constant (or add
  an alternate spelling as a tuple, like `COL_PRDN_CHANGES`).
- **New breakup metric**: add it to the `results.append({...})` dict in
  `compute_country_breakup`, then add it to `_SUM_KEYS` in `report.py` if it
  should appear in the subtotal, plus a cell in `_breakup_rows_html` /
  `_breakup_text`.
