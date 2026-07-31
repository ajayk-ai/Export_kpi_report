# Export KPI Automation — Deployment Guide

Step-by-step guide for the dev team to deploy and run the app on a Windows machine.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.14+ | https://www.python.org/downloads/ |
| uv | latest | `pip install uv` |
| Node.js | 18+ | https://nodejs.org/ (needed for PM2) |
| Git | latest | https://git-scm.com/ |

## 1. Clone & Install

```bash
git clone <repo-url>
cd Export-kpi-automation
uv sync
```

This creates `.venv` with all Python dependencies.

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes | Path to service account JSON (default `config/service.json`) |
| `SHEET_ID` | Yes | Google Sheet ID from the URL |
| `WORKSHEET_NAME` | Yes | Tab name (e.g. `SCM_Export_Orders`) |
| `SMTP_HOST` / `SMTP_PORT` | Yes | Email server (default `smtp.gmail.com` / `465`) |
| `SMTP_USER` / `SMTP_PASSWORD` | Yes | SMTP credentials (Gmail: use App Password) |
| `EMAIL_SENDER` / `EMAIL_RECIPIENT` | Yes | From / To addresses |
| `EMAIL_SUBJECT` | No | Default: `Export KPI Summary` |
| `GEMINI_API_KEY` | No | Leave blank to skip AI summary |
| `HOST` / `PORT` | No | Server bind (default `0.0.0.0` / `8000`) |

Also place the Google service account key at `config/service.json`.

## 3. Verify It Works

```bash
# CLI — print KPI summary
uv run python main.py

# Web — start live server
uv run python -m app.main
# Open http://127.0.0.1:8000/report
```

## 4. Run as a Service (PM2 — No Terminal Needed)

### Install PM2

```bash
npm install -g pm2
```

### Start the app

```bash
pm2 start ecosystem.config.js
```

### Useful commands

```bash
pm2 status                  # check running processes
pm2 logs kpi-server         # live logs
pm2 restart kpi-server      # restart
pm2 stop kpi-server         # stop
pm2 delete kpi-server       # remove
```

### Auto-start on boot

```bash
pm2 startup                 # creates a Windows Service
pm2 save                    # saves current process list
```

After `pm2 startup`, PM2 will auto-restart `kpi-server` when the machine reboots.

## 5. Daily Email via Windows Task Scheduler

The project includes a PowerShell script that registers a scheduled task to send
the KPI report email once a day at **4:00 PM IST**.

### Register the task

From an **elevated** (Run as Administrator) PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\register_task.ps1
```

This creates a task named `ExportKPIDailyReport` that runs as `SYSTEM`.

### Test it

```powershell
Start-ScheduledTask -TaskName "ExportKPIDailyReport"
```

### Check logs

```
logs\daily_report.log
```

### Remove the task

```powershell
Unregister-ScheduledTask -TaskName "ExportKPIDailyReport"
```

## 6. Project Structure

```
Export-kpi-automation/
├── main.py                 CLI entry point
├── app/
│   ├── main.py             FastAPI app (HOST/PORT from .env)
│   ├── config.py           Settings from .env
│   ├── api/routes.py       HTTP endpoints
│   ├── core/
│   │   ├── kpi_engine.py   KPI math (pure functions)
│   │   ├── report.py       Text + HTML rendering
│   │   ├── pipeline.py     Orchestration (build_report)
│   │   └── data_source.py  Live Google Sheet loader
│   └── clients/
│       ├── sheets_client.py   Google Sheets reader
│       ├── gemini_client.py   AI summary (optional)
│       └── email_client.py    SMTP sender
├── config/service.json     Google service account key (gitignored)
├── .env                    Environment config (gitignored)
├── start.bat               Double-click to start the server
├── email.bat               curl POST to /send endpoint
└── deploy/
    └── register_task.ps1   Windows Task Scheduler setup
```

## 7. Web API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Landing page with links |
| `/report` | GET | Live HTML report from Google Sheets |
| `/report?month=JULY` | GET | Filter breakup to a month |
| `/report.json` | GET | KPIs as JSON |
| `/send` | POST | Compute and email the report |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |

## 8. Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `uv sync` to install dependencies |
| `SMTPAuthenticationError` | Use a Gmail **App Password**, not your login password |
| `403` from Google Sheets | Share the sheet with the service account's `client_email` |
| Port already in use | Change `PORT` in `.env` or stop the other process |
| PM2 process keeps restarting | Check logs: `pm2 logs kpi-server` |
| Scheduled task doesn't fire | Re-run `register_task.ps1` from elevated PowerShell |

## 9. Security Notes

- `.env` and `config/*.json` are **gitignored** — never commit secrets.
- If a key is exposed, rotate it immediately in the Google Cloud Console.
- For Gmail SMTP, enable 2-Step Verification and create an App Password.
