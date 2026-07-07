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

## Run

Run from the project root:

```bash
uv run python main.py            # print the KPI summary
uv run python main.py --send     # print and email the summary
```

## Project layout

```
main.py                 CLI entry point (argparse)
src/
  config.py             Settings loaded from .env (single `settings` object)
  sheets_client.py      Read the sheet via service account / delegation
  kpi_engine.py         Pure KPI math over a DataFrame (no I/O)
  gemini_client.py      AI summary of the KPIs via Google Gemini
  report.py             Render KPIs as plain text and colorful HTML
  email_client.py       Send the report over SMTP (HTML + text fallback)
  pipeline.py           Orchestration: fetch -> compute -> AI -> format -> send
```

## Security

`.env` and `config/*.json` are gitignored — never commit your service account
key. If a key has been exposed, rotate it in the Google Cloud console.
