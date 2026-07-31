# scm-kpi-automation

Reads an SCM export from Google Sheets, computes monthly KPIs, and (optionally)
emails a summary via Gmail — all authenticated with a Google service account.

## Setup

1. Install dependencies (uv):

   ```bash
   uv sync
   ```

2. Place your service account key at `config/service.json`
   (or point `GOOGLE_SERVICE_ACCOUNT_FILE` elsewhere).

3. Configure environment:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env`:

   | Variable                      | Purpose                                              |
   | ----------------------------- | ---------------------------------------------------- |
   | `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the service account JSON key (Sheets access)  |
   | `SHEET_ID`                    | Google Sheet ID (from its URL)                        |
   | `WORKSHEET_NAME`              | Tab name to read (default `SCM_Export`)               |
   | `SMTP_HOST` / `SMTP_PORT`     | SMTP server (default `smtp.gmail.com` / `465`)        |
   | `SMTP_USER` / `SMTP_PASSWORD` | SMTP login; for Gmail use an **App Password**         |
   | `EMAIL_SENDER`                | From address (defaults to `SMTP_USER`)                |
   | `EMAIL_RECIPIENT`             | Who receives the KPI summary                          |
   | `EMAIL_SUBJECT`               | Email subject line                                    |
   | `GEMINI_API_KEY`              | Gemini key for the AI summary (empty = skip it)       |
   | `GEMINI_MODEL`                | Gemini model (default `gemini-2.5-flash`)             |

## Access requirements

- **Sheets:** share the target sheet with the service account's
  `client_email` (viewer is enough).
- **Email (SMTP):** set `SMTP_USER` / `SMTP_PASSWORD`. For Gmail, enable
  2-Step Verification and create an **App Password**
  (Google Account > Security > App passwords) — your normal password will not
  work over SMTP.

## Quick Start (Windows)

Double-click **`start.bat`** or run manually:

```bash
uv run python -m app.main
```

This reads `HOST` / `PORT` from `.env` (default `http://0.0.0.0:8500`).

> **First time?** Run `uv sync` first to create `.venv`.

### Run in background with PM2 (no terminal needed)

1. Install PM2 globally:

   ```bash
   npm install -g pm2
   ```

2. Start the app:

   ```bash
   pm2 start ecosystem.config.js
   ```

3. Useful PM2 commands:

   ```bash
   pm2 status              # check running processes
   pm2 logs kpi-server     # view live logs
   pm2 restart kpi-server  # restart the app
   pm2 stop kpi-server     # stop the app
   pm2 delete kpi-server   # remove from PM2
   ```

4. (Optional) Auto-start on system boot:

   ```bash
   pm2 startup
   pm2 save
   ```

## Run

Run from the project root:

### CLI

```bash
uv run python main.py            # print the KPI summary
uv run python main.py --send     # print and email the summary
```

### Live web API (FastAPI)

Serve the **exact email template live** so you can eyeball the report against
real Google Sheet data in a browser before emailing it:

```bash
uv run uvicorn app.main:app --reload
```

Then open:

| Endpoint | What it does |
| --- | --- |
| `GET /` | Landing page with links |
| `GET /report` | Live HTML report from Google Sheets (the email template) |
| `GET /report?month=JULY` | Filter the breakup to a month; `&ai=false` skips the AI summary |
| `GET /report.json` | KPIs + per-country breakup as JSON |
| `POST /send` | Compute and email the report (`?recipient=...` to override) |
| `GET /docs` | Interactive Swagger UI |

## Project layout

```
main.py                     CLI entry point (argparse)
app/
  config.py                 Settings loaded from .env (single `settings` object)
  main.py                   FastAPI app factory (`uvicorn app.main:app`)
  api/
    routes.py               HTTP endpoints (/report, /report.json, /send, /health)
  core/
    kpi_engine.py           Pure KPI math over a DataFrame (no I/O)
    report.py               Render KPIs as plain text and colorful HTML
    pipeline.py             Orchestration + `build_report()` shared by CLI & API
    data_source.py          Live Google Sheet loader
  clients/
    sheets_client.py        Read the sheet via service account / delegation
    gemini_client.py        AI summary of the KPIs via Google Gemini
    email_client.py         Send the report over SMTP (HTML + text fallback)
```

## Production: daily 4pm email (Windows Task Scheduler)

Registers a Windows scheduled task that runs `main.py --send` once a day at
**16:00 (4:00 PM) India Standard Time**, using the project's own `.venv` (no
reliance on `uv`/PATH being set up in the task's environment). To change the
send time, edit `$reportHour` / `$reportMinute` at the top of
`deploy\register_task.ps1` and re-run it.

1. Make sure `.env` is filled in and `uv sync` has been run on this machine
   (i.e. `.venv\Scripts\python.exe` exists).
2. From an **elevated** (Run as Administrator) PowerShell, from the project
   root:

   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\register_task.ps1
   ```

   This creates a task named `ExportKPIDailyReport` that runs as `SYSTEM` (so
   it fires even if nobody is logged in), at 16:00 IST converted to the
   server's own local timezone — if the server isn't set to IST, the script
   computes and registers the equivalent local time for you.
3. Test it immediately (this sends a real email):

   ```powershell
   Start-ScheduledTask -TaskName "ExportKPIDailyReport"
   ```

4. Check `logs\daily_report.log` for a timestamped "sent OK" / "FAILED" line
   after each run (scheduled or manual).

Re-run `deploy\register_task.ps1` any time to update the schedule (e.g. after
moving the project folder). Remove the task with:

```powershell
Unregister-ScheduledTask -TaskName "ExportKPIDailyReport"
```

## Security

`.env` and `config/*.json` are gitignored — never commit your service account
key. If a key has been exposed, rotate it in the Google Cloud console.
