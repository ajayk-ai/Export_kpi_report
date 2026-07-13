"""Send email over SMTP (SSL on port 465, otherwise STARTTLS)."""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings


def send_summary_email(
    to_email: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError(
            "SMTP_USER / SMTP_PASSWORD are not set. Set them in .env "
            "(for Gmail, use an App Password)."
        )

    # multipart/alternative: clients show HTML, fall back to text if unsupported.
    message = MIMEMultipart("alternative")
    message["From"] = settings.email_sender
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(text_body, "plain"))
    if html_body:
        message.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_sender, [to_email], message.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_sender, [to_email], message.as_string())
