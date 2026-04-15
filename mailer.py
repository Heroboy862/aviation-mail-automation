import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

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


def _build_message(
    *,
    from_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    html_body: str | None,
    attachment_path: Path,
) -> MIMEMultipart:
    if not attachment_path.exists():
        raise FileNotFoundError(f"Eklenecek PDF bulunamadi: {attachment_path}")

    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        message.attach(MIMEText(html_body, "html", "utf-8"))

    with attachment_path.open("rb") as file:
        attachment = MIMEApplication(file.read(), _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=attachment_path.name)
    message.attach(attachment)
    return message


def _open_smtp_server(smtp: dict[str, Any]) -> smtplib.SMTP:
    server = smtplib.SMTP(smtp["host"], smtp["port"])
    server.starttls()
    server.login(smtp["user"], smtp["password"])
    return server


def send_mail_batch_with_pdf(
    jobs: list[dict[str, Any]],
    *,
    batch_size: int = 50,
    sleep_seconds: int = 10,
) -> tuple[list[int], list[dict[str, Any]]]:
    if batch_size <= 0:
        raise ValueError("batch_size sifirdan buyuk olmali.")

    smtp = _get_smtp_config()
    sent_indices: list[int] = []
    failures: list[dict[str, Any]] = []

    for batch_start in range(0, len(jobs), batch_size):
        batch_end = min(batch_start + batch_size, len(jobs))
        batch_jobs = jobs[batch_start:batch_end]

        with _open_smtp_server(smtp) as server:
            for index, job in enumerate(batch_jobs, start=batch_start):
                try:
                    message = _build_message(
                        from_email=smtp["from_email"],
                        recipient_email=job["recipient_email"],
                        subject=job["subject"],
                        body=job["body"],
                        html_body=job.get("html_body"),
                        attachment_path=job["attachment_path"],
                    )
                    server.sendmail(
                        from_addr=smtp["from_email"],
                        to_addrs=[job["recipient_email"]],
                        msg=message.as_string(),
                    )
                    sent_indices.append(index)
                except Exception as exc:
                    failures.append(
                        {
                            "index": index,
                            "recipient_email": job.get("recipient_email", ""),
                            "error": str(exc),
                        }
                    )

        if batch_end < len(jobs):
            time.sleep(sleep_seconds)

    return sent_indices, failures


def send_mail_with_pdf(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    attachment_path: Path,
) -> None:
    smtp = _get_smtp_config()
    message = _build_message(
        from_email=smtp["from_email"],
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        html_body=html_body,
        attachment_path=attachment_path,
    )

    with smtplib.SMTP(smtp["host"], smtp["port"]) as server:
        server.starttls()
        server.login(smtp["user"], smtp["password"])
        server.sendmail(
            from_addr=smtp["from_email"],
            to_addrs=[recipient_email],
            msg=message.as_string(),
        )
