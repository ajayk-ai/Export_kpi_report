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

Everything is driven from `main.py`:

```bash
uv run python main.py            # print the KPI summary
uv run python main.py --send     # print and email it
```

## 2. Architecture / data flow

```
                 .env  ──────────────► src/config.py (Settings)
                                             │
config/service.json (Google creds) ─────────┤
                                             ▼
Google Sheet (SCM_Export tab) ──► src/sheets_client.py ──► pandas.DataFrame
                                             │
                                             ▼
                                   src/kpi_engine.py
                              (compute_all_kpis, compute_country_breakup)
                                             │
                          ┌──────────────────┼──────────────────┐
                          ▼                                     ▼
                 src/gemini_client.py                   src/report.py
              (generate_summary — optional)        (text_summary / html_report)
                          │                                     │
                          └──────────────┬──────────────────────┘
                                         ▼
                                 src/pipeline.py (run)
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                       print(summary)      src/email_client.py (--send only)
                                              (SMTP send, HTML + text)
```

`src/pipeline.py::run()` is the single orchestration point — it is the only
function that calls the other modules in sequence:

```
df = get_data_as_dataframe(...)
kpis = compute_all_kpis(df)
month = REPORT_MONTH or latest_month(df)
breakup = compute_country_breakup(df, month=month)
ai_summary = generate_summary(kpis, breakup)
text = text_summary(...)
if send: send_summary_email(html_report(...))
```

Every function in `kpi_engine.py` is a **pure function over a DataFrame** —
no I/O, no side effects — which is what makes the KPI math easy to reason
about and test independently of Sheets/SMTP/Gemini.

## 3. Module reference

| File | Responsibility |
|---|---|
| [main.py](main.py) | CLI entry point (`argparse`); prints the summary, optionally passes `--send`. |
| [src/config.py](src/config.py) | Loads `.env` once into a frozen `Settings` dataclass (`settings`). Also injects the OS trust store into `ssl` so corporate TLS-inspection proxies don't break HTTPS calls. |
| [src/sheets_client.py](src/sheets_client.py) | Authenticates with a Google service account (optionally impersonating a Workspace user via domain-wide delegation) and pulls the worksheet into a `pandas.DataFrame` via `gspread`. |
| [src/kpi_engine.py](src/kpi_engine.py) | All business logic / math. See §4 and §5 below. |
| [src/gemini_client.py](src/gemini_client.py) | Builds a prompt from the KPIs + breakup and asks Gemini for an executive summary. Fully optional — degrades to `""` silently on any error or missing API key. |
| [src/report.py](src/report.py) | Pure rendering: turns KPI/breakup dicts into a plain-text string and into a styled, inline-CSS HTML block (email-client-safe, no external CSS/JS). |
| [src/email_client.py](src/email_client.py) | Sends the report over SMTP (SSL on port 465, STARTTLS otherwise), `multipart/alternative` so clients without HTML fall back to plain text. |
| [src/pipeline.py](src/pipeline.py) | Wires the above together end-to-end; the only place that calls more than one module. |

## 4. Expected sheet shape

The source is the `SCM_Export` worksheet (configurable via `WORKSHEET_NAME`),
read with `worksheet.get_all_records()` — so **row 1 must be a header row**
and every other row is one order line. Relevant columns (see
`kpi_engine.py` constants for the exact strings — some header names are kept
as-is including a sheet typo that's intentionally tolerated):

| Column | Used for |
|---|---|
| `Month` | Which monthly bucket a row belongs to (`APRIL`, `MAY`, `JUNE`, …). |
| `Order Type (N / O)` | `"N"` = new order counted in that month's `new_order`. |
| `Quantity` | The unit count summed for every KPI/breakup metric. |
| `Loading (Dispatched) Date` | Presence of a valid `DD-MM-YYYY` date = dispatched/closed. |
| `Country` | Groups the overdue breakup. |
| `over due days` | > 0 marks a row "overdue" for the breakup section. |
| `Machine Revision Date` | Source for each country's "New Committed Date". |
| `Container Placement date`, `Container Revision Date` | Source for "Container Expected Date" (latest of the two). |
| `Vessel Cut-Off Date` | Shown as-is per country (latest among overdue rows). |
| `no of times commitment changes(prod)` *(or the sheet's misspelling `commitement`)* | Summed as "Prdn commitment changes". |
| `no of comm container changes` | Summed as "Container commitment changes". |
| `Commercial Clearance Status` | Anything other than completed/complete/cleared/done/yes counts as pending. |

Dates are parsed strictly as `DD-MM-YYYY` (`kpi_engine.DATE_FORMAT`); anything
that doesn't match (blank, `"Pending"`, other formats) parses to `NaT` and is
treated as "not a real date" — e.g. not dispatched.

## 5. KPI logic in detail

### 5.1 Monthly Opening / New / Total / Despatched / Balance

`compute_month_kpis(df, month, prev_balance)`:

```
opening_order  = prev_balance                                   # carried from previous month
new_order      = SUM(Quantity) WHERE Month == month AND Order Type == "N"
total_order    = opening_order + new_order
dispatched     = SUM(Quantity) WHERE Month == month AND Loading Date is a real date
balance        = total_order - dispatched
```

`compute_all_kpis(df)` runs this for every month in
`MONTH_ORDER = ["APRIL", "MAY", "JUNE"]` **in order**, feeding each month's
`balance` in as the next month's `opening_order` (starting at 0 for the first
month). To add a new month, extend `MONTH_ORDER` — nothing else needs to
change.

Note: only rows with `Order Type == "N"` feed `new_order`. Rows with other
order types (e.g. an `"O"` for "open"/carry-over) are not summed again here —
they're expected to already be reflected via `opening_order`/`prev_balance`.

`latest_month(df)` — used when `REPORT_MONTH` is blank — returns the last
month (per `MONTH_ORDER`) that actually appears in the sheet's `Month`
column (case/whitespace-insensitive), falling back to the last configured
month name if none match.

### 5.2 Per-country overdue breakup

`compute_country_breakup(df, month)` — restricted to the target month if
given, otherwise the whole sheet. For each `Country` group:

- **Included at all** only if the country has at least one *open* row
  (`Loading Date` not a valid date) or one *overdue* row (`over due days` >
  0). Countries with everything dispatched and never overdue are dropped.
  Blank/unlabeled country rows are also dropped.
- `over_due_breakup` = `SUM(Quantity)` over that country's overdue rows.
- `days_delay` = `MAX(over due days)` over that country's overdue rows (not a
  sum — it's "how late is the worst row").
- `new_committed_date` = latest `Machine Revision Date` among overdue rows.
- `container_expected_date` = latest of `Container Placement date` /
  `Container Revision Date` among overdue rows.
- `vessel_cutoff` = latest `Vessel Cut-Off Date` among overdue rows.
- `prdn_machines_pending` / `container_machines_pending` = `SUM(Quantity)`
  over **all open rows** for that country (not just overdue ones) — today
  these two are identical because the sheet has no separate "awaiting
  production vs. awaiting container" distinction, but they're computed
  independently so a future column split doesn't require new logic.
- `prdn_commitment_changes` = `SUM(commitment changes (prod))` over overdue
  rows. `container_commitment_changes` = `SUM(comm container changes)` over
  overdue rows.
- `clearance_pending` = `SUM(Quantity)` over **all rows** (not just overdue)
  where `Commercial Clearance Status` isn't one of
  `completed/complete/cleared/done/yes`.

Countries are sorted **descending by `over_due_breakup`** (worst first). A
"Sub Total" row is a plain column-wise sum of every numeric field across all
countries (dates are never totaled).

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
