"""Configuration loaded once from environment variables (.env)."""
import os
from dataclasses import dataclass
from pathlib import Path

import truststore
from dotenv import load_dotenv

# Use the OS trust store (Windows cert store) so corporate TLS-inspection root
# CAs are trusted. Fixes "self-signed certificate in certificate chain".
truststore.inject_into_ssl()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def _resolve_path(value: str) -> str:
    """Resolve a possibly-relative path against the project root."""
    path = Path(value)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)


@dataclass(frozen=True)
class Settings:
    # Google Sheets
    service_account_file: str
    sheet_id: str
    worksheet_name: str
    delegated_user: str  # impersonate via domain-wide delegation; "" to disable
    report_month: str  # month to filter the country breakup on; "" = latest in data
    filter_webapp_url: str  # Apps Script Web App /exec URL; "" disables the links

    # Email (SMTP)
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_sender: str
    email_recipient: str
    email_subject: str

    # Gemini (AI summary)
    gemini_api_key: str
    gemini_model: str

    @classmethod
    def load(cls) -> "Settings":
        smtp_user = os.getenv("SMTP_USER", "")
        return cls(
            service_account_file=_resolve_path(
                os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "config/service.json")
            ),
            sheet_id=_require("SHEET_ID"),
            worksheet_name=os.getenv("WORKSHEET_NAME", "SCM_Export"),
            delegated_user=os.getenv("GOOGLE_DELEGATED_USER", ""),
            report_month=os.getenv("REPORT_MONTH", "").strip(),
            filter_webapp_url=os.getenv("FILTER_WEBAPP_URL", "").strip(),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            smtp_user=smtp_user,
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            email_sender=os.getenv("EMAIL_SENDER", smtp_user),
            email_recipient=os.getenv("EMAIL_RECIPIENT", ""),
            email_subject=os.getenv("EMAIL_SUBJECT", "Export KPI Report"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )


settings = Settings.load()
