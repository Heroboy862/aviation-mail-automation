import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_smtp_config() -> dict:
    config = {
        "host": os.getenv("SMTP_HOST"),
        "port": os.getenv("SMTP_PORT"),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_email": os.getenv("FROM_EMAIL") or os.getenv("SMTP_USER"),
    }
    if not all([config["host"], config["port"], config["user"], config["password"]]):
        raise ValueError("SMTP ayarlari eksik. .env dosyasini kontrol edin.")
    config["port"] = int(config["port"])
    return config


def send_mail_with_pdf(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: Path,
) -> None:
    if not attachment_path.exists():
        raise FileNotFoundError(f"Eklenecek PDF bulunamadi: {attachment_path}")

    smtp = _get_smtp_config()

    message = MIMEMultipart()
    message["From"] = smtp["from_email"]
    message["To"] = recipient_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    with attachment_path.open("rb") as file:
        attachment = MIMEApplication(file.read(), _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=attachment_path.name)
    message.attach(attachment)

    with smtplib.SMTP(smtp["host"], smtp["port"]) as server:
        server.starttls()
        server.login(smtp["user"], smtp["password"])
        server.sendmail(
            from_addr=smtp["from_email"],
            to_addrs=[recipient_email],
            msg=message.as_string(),
        )
