"""Send email over SMTP (SSL on port 465, otherwise STARTTLS)."""
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings


def _parse_recipients(to: str | list[str]) -> list[str]:
    """Split a comma/semicolon-separated string (or pass through a list) into
    trimmed, non-empty addresses. Lets EMAIL_RECIPIENT hold multiple people,
    e.g. ``a@x.com, b@x.com``.
    """
    raw = re.split(r"[,;]", to) if isinstance(to, str) else to
    return [addr.strip() for addr in raw if addr.strip()]


def send_summary_email(
    to_email: str | list[str], subject: str, text_body: str, html_body: str | None = None
) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError(
            "SMTP_USER / SMTP_PASSWORD are not set. Set them in .env "
            "(for Gmail, use an App Password)."
        )

    recipients = _parse_recipients(to_email)
    if not recipients:
        raise RuntimeError("No valid recipient email address provided.")

    # multipart/alternative: clients show HTML, fall back to text if unsupported.
    message = MIMEMultipart("alternative")
    message["From"] = settings.email_sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.attach(MIMEText(text_body, "plain"))
    if html_body:
        message.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_sender, recipients, message.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_sender, recipients, message.as_string())
