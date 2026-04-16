import logging
import os
import re
import shutil
import time
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from config import ARCHIVE_DIR, DATA_DIR, FONT_PATH, FORM_FIELD_ALIASES, LOGS_DIR, TEMP_PDF_DIR, get_department_config
from gemini_service import generate_career_advice
from mailer import send_mail_batch_with_pdf, send_mail_with_pdf
from pdf_engine import generate_participant_pdf

load_dotenv()

SMTP_BATCH_SIZE = int(os.getenv("SMTP_BATCH_SIZE", "50"))
SMTP_BATCH_SLEEP_SECONDS = int(os.getenv("SMTP_BATCH_SLEEP_SECONDS", "10"))


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


DRY_RUN = _env_flag("DRY_RUN", "false")
if DRY_RUN:
    ENABLE_SMTP_SEND = False
    ENABLE_STATUS_UPDATE = False
else:
    ENABLE_SMTP_SEND = _env_flag("ENABLE_SMTP_SEND", "true")
    ENABLE_STATUS_UPDATE = _env_flag("ENABLE_STATUS_UPDATE", "true")
MAX_SEND_COUNT = max(int(os.getenv("MAX_SEND_COUNT", "0")), 0)
ARCHIVE_SENT_PDFS = _env_flag("ARCHIVE_SENT_PDFS", "true")
LIVE_LOOP = _env_flag("LIVE_LOOP", "false")
LIVE_POLL_SECONDS = max(int(os.getenv("LIVE_POLL_SECONDS", "20")), 1)

STATUS_SENT = "Gönderildi"
STATUS_ERROR = "Hata Alındı"


def post_send_attachment_cleanup(sent_jobs: list[dict[str, Any]]) -> None:
    if not sent_jobs:
        return

    if ARCHIVE_SENT_PDFS:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for job in sent_jobs:
        attachment_path = Path(job["attachment_path"])
        if not attachment_path.exists():
            continue

        try:
            if ARCHIVE_SENT_PDFS:
                target_path = ARCHIVE_DIR / attachment_path.name
                if target_path.exists():
                    target_path = ARCHIVE_DIR / f"{attachment_path.stem}_{int(time.time())}{attachment_path.suffix}"
                shutil.move(str(attachment_path), str(target_path))
                logging.info("PDF arsive tasindi: %s", target_path)
            else:
                attachment_path.unlink()
                logging.info("PDF silindi: %s", attachment_path)
        except Exception as exc:
            logging.warning("PDF temizleme basarisiz (%s): %s", attachment_path, exc)


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "process.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"\s+", "_", cleaned.strip())


def get_first_existing_key(data: dict[str, Any], options: list[str], default: str = "") -> str:
    for key in options:
        if key in data and str(data.get(key, "")).strip():
            return str(data[key]).strip()
    return default


def is_status_pending(status_value: Any) -> bool:
    """Durum bos: Form/Sheets'te '', CSV'de pandas NaN veya bos string."""
    if status_value is None:
        return True
    s = str(status_value).strip()
    if s == "":
        return True
    if s.lower() in {"nan", "none", "null"}:
        return True
    return False


def extract_participant_name(data: dict[str, Any]) -> str:
    full_name = get_first_existing_key(data, FORM_FIELD_ALIASES["full_name"])
    if full_name:
        return full_name

    first_name = get_first_existing_key(data, FORM_FIELD_ALIASES["first_name"])
    last_name = get_first_existing_key(data, FORM_FIELD_ALIASES["last_name"])
    return " ".join(part for part in [first_name, last_name] if part).strip()


def build_html_mail_body(*, participant_name: str, department_name: str, career_message: str) -> str:
    safe_name = escape(participant_name)
    safe_department = escape(department_name)
    safe_message = escape(career_message)
    return f"""\
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Kariyer Yol Haritasi</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6fb;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="background:#0b3d91;color:#ffffff;padding:20px 24px;">
              <h1 style="margin:0;font-size:22px;line-height:1.3;">Kariyer Yol Haritan Hazir</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;color:#1f2a44;">
              <p style="margin:0 0 14px 0;font-size:16px;">Merhaba <strong>{safe_name}</strong>,</p>
              <p style="margin:0 0 14px 0;font-size:15px;line-height:1.7;">
                <strong>{safe_department}</strong> bolumu icin hazirlanan kisisel kariyer raporun ektedir.
              </p>
              <div style="background:#f7f9ff;border:1px solid #e3e9ff;border-radius:10px;padding:16px;font-size:15px;line-height:1.7;">
                {safe_message}
              </div>
              <p style="margin:16px 0 0 0;font-size:14px;color:#4b5c83;">
                Basarilar dileriz.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class CSVDataSource:
    def __init__(self, csv_path: Path) -> None:
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV dosyasi bulunamadi: {csv_path}")

        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self.status_column = self._detect_status_column()
        if self.status_column not in self.df.columns:
            self.df[self.status_column] = ""

    def _detect_status_column(self) -> str:
        candidates = FORM_FIELD_ALIASES["status"]
        for candidate in candidates:
            if candidate in self.df.columns:
                return candidate
        return "Durum"

    def records(self) -> list[dict[str, Any]]:
        output = []
        for idx, row in self.df.iterrows():
            row_dict = row.to_dict()
            status_raw = row_dict.get(self.status_column, "")
            status_value = str(status_raw).strip()
            if not is_status_pending(status_value):
                continue

            output.append(
                {
                    "row_ref": int(idx),
                    "timestamp": get_first_existing_key(row_dict, FORM_FIELD_ALIASES["timestamp"]),
                    "name": extract_participant_name(row_dict),
                    "school": get_first_existing_key(row_dict, FORM_FIELD_ALIASES["school"]),
                    "department": get_first_existing_key(row_dict, FORM_FIELD_ALIASES["department"]),
                    "email": get_first_existing_key(row_dict, FORM_FIELD_ALIASES["email"]),
                    "status": status_value,
                }
            )
        return output

    def mark_sent(self, row_ref: int) -> None:
        self.mark_sent_batch([row_ref])

    def write_row_status_batch(self, row_refs: list[int], value: str) -> None:
        if not row_refs:
            return
        for r in sorted(set(row_refs)):
            self.df.loc[r, self.status_column] = value
        self.df.to_csv(self.csv_path, index=False)

    def write_row_status(self, row_ref: int, value: str) -> None:
        self.write_row_status_batch([row_ref], value)

    def mark_sent_batch(self, row_refs: list[int]) -> None:
        self.write_row_status_batch(row_refs, STATUS_SENT)


class GoogleSheetsDataSource:
    def __init__(self, credentials_path: Path, sheet_name: str, worksheet_name: str | None = None) -> None:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as exc:
            raise ImportError(
                "Google Sheets modu icin 'gspread' ve 'google-auth' paketleri gerekli."
            ) from exc

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
        client = gspread.authorize(credentials)
        sheet = client.open(sheet_name)
        self.worksheet = sheet.worksheet(worksheet_name) if worksheet_name else sheet.sheet1

        self.headers = self.worksheet.row_values(1)
        self.status_column = self._detect_status_column()
        self.status_col_index = self.headers.index(self.status_column) + 1

    def _detect_status_column(self) -> str:
        candidates = FORM_FIELD_ALIASES["status"]
        for candidate in candidates:
            if candidate in self.headers:
                return candidate

        self.worksheet.update_cell(1, len(self.headers) + 1, "Durum")
        self.headers.append("Durum")
        return "Durum"

    def records(self) -> list[dict[str, Any]]:
        rows = self.worksheet.get_all_records()
        output = []
        for i, row in enumerate(rows, start=2):
            status_value = get_first_existing_key(row, [self.status_column])
            if not is_status_pending(status_value):
                continue

            output.append(
                {
                    "row_ref": i,
                    "timestamp": get_first_existing_key(row, FORM_FIELD_ALIASES["timestamp"]),
                    "name": extract_participant_name(row),
                    "school": get_first_existing_key(row, FORM_FIELD_ALIASES["school"]),
                    "department": get_first_existing_key(row, FORM_FIELD_ALIASES["department"]),
                    "email": get_first_existing_key(row, FORM_FIELD_ALIASES["email"]),
                    "status": status_value,
                }
            )
        return output

    def mark_sent(self, row_ref: int) -> None:
        self.mark_sent_batch([row_ref])

    def write_row_status_batch(self, row_refs: list[int], value: str) -> None:
        if not row_refs:
            return

        import gspread

        unique_rows = sorted(set(row_refs))
        cells = [
            gspread.Cell(row=row_ref, col=self.status_col_index, value=value)
            for row_ref in unique_rows
        ]
        self.worksheet.update_cells(cells, value_input_option="USER_ENTERED")

    def write_row_status(self, row_ref: int, value: str) -> None:
        self.write_row_status_batch([row_ref], value)

    def mark_sent_batch(self, row_refs: list[int]) -> None:
        self.write_row_status_batch(row_refs, STATUS_SENT)


def build_data_source() -> CSVDataSource | GoogleSheetsDataSource:
    source_type = os.getenv("DATA_SOURCE", "csv").strip().lower()
    if source_type == "google_sheets":
        credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        sheet_name = os.getenv("GOOGLE_SHEET_NAME", "").strip()
        worksheet_name = os.getenv("GOOGLE_WORKSHEET_NAME", "").strip() or None
        if not credentials_path or not sheet_name:
            raise ValueError(
                "Google Sheets icin GOOGLE_SERVICE_ACCOUNT_JSON ve GOOGLE_SHEET_NAME gerekli."
            )
        path_obj = Path(credentials_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"GOOGLE_SERVICE_ACCOUNT_JSON bulunamadi: {path_obj}")
        return GoogleSheetsDataSource(
            credentials_path=path_obj,
            sheet_name=sheet_name,
            worksheet_name=worksheet_name,
        )

    csv_path = Path(os.getenv("CSV_PATH", str(DATA_DIR / "participants.csv")))
    if csv_path.exists():
        return CSVDataSource(csv_path=csv_path)

    fallback_candidates = [Path("participants.csv"), DATA_DIR / "participants.csv"]
    for candidate in fallback_candidates:
        if candidate.exists():
            logging.warning("CSV_PATH bulunamadi (%s). Otomatik fallback kullaniliyor: %s", csv_path, candidate)
            return CSVDataSource(csv_path=candidate)

    return CSVDataSource(csv_path=csv_path)


def process_one_record(
    data_source: CSVDataSource | GoogleSheetsDataSource,
    participant: dict[str, Any],
) -> None:
    """Tek satir: Gemini -> PDF -> mail -> Arsiv; basarida Gönderildi, hatada Hata Alindi."""
    row_ref = int(participant["row_ref"])
    display_name = participant.get("name") or "Bilinmiyor"
    logging.info(
        "Yeni kayıt yakalandı | satir=%s | ad=%s | bolum=%s | eposta=%s",
        row_ref,
        display_name,
        participant.get("department", ""),
        participant.get("email", ""),
    )
    try:
        if not all(
            [
                participant["name"],
                participant["school"],
                participant["department"],
                participant["email"],
            ]
        ):
            raise ValueError(f"Eksik katilimci bilgisi: {participant}")

        department_config = get_department_config(participant["department"])
        career_advice = generate_career_advice(
            participant_name=participant["name"],
            department_name=participant["department"],
        )
        logging.info("Gemini tavsiyesi hazır | satir=%s | ad=%s", row_ref, display_name)

        pdf_name = (
            f"{sanitize_filename(participant['name'])}_"
            f"{sanitize_filename(participant['department'])}.pdf"
        )
        pdf_output_path = TEMP_PDF_DIR / pdf_name

        generate_participant_pdf(
            template_path=Path(department_config["png_template"]),
            output_path=pdf_output_path,
            font_path=FONT_PATH,
            participant_name=participant["name"],
            school_name=participant["school"],
            department_name=participant["department"],
            career_advice=career_advice,
            text_coords=department_config["text_coords"],
        )
        logging.info("PDF hazirlandi | satir=%s | dosya=%s", row_ref, pdf_output_path)

        html_body = build_html_mail_body(
            participant_name=participant["name"],
            department_name=participant["department"],
            career_message=career_advice,
        )

        if ENABLE_SMTP_SEND:
            send_mail_with_pdf(
                recipient_email=participant["email"],
                subject=department_config["mail_subject"],
                body=career_advice,
                html_body=html_body,
                attachment_path=pdf_output_path,
            )
            logging.info("Mail uçuşa geçti | satir=%s | hedef=%s", row_ref, participant["email"])
        else:
            logging.info(
                "Mail simule edildi (SMTP kapali) | satir=%s | hedef=%s",
                row_ref,
                participant["email"],
            )

        post_send_attachment_cleanup(
            [
                {
                    "participant": participant,
                    "attachment_path": pdf_output_path,
                }
            ]
        )

        if ENABLE_STATUS_UPDATE:
            data_source.write_row_status(row_ref, STATUS_SENT)
            logging.info("Durum guncellendi | satir=%s | %s", row_ref, STATUS_SENT)
        else:
            logging.info("Durum guncellemesi kapali | satir=%s", row_ref)

    except Exception:
        logging.exception("Kayit basarisiz | satir=%s | ad=%s", row_ref, display_name)
        if ENABLE_STATUS_UPDATE:
            try:
                data_source.write_row_status(row_ref, STATUS_ERROR)
                logging.info("Durum guncellendi | satir=%s | %s", row_ref, STATUS_ERROR)
            except Exception:
                logging.exception(
                    "Durum yazilamadi | satir=%s | deger=%s",
                    row_ref,
                    STATUS_ERROR,
                )


def run_live_loop() -> None:
    """Google Sheet'i periyodik tarar; bos Durum satirlarini isler (gspread)."""
    setup_logging()
    TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)

    if os.getenv("DATA_SOURCE", "csv").strip().lower() != "google_sheets":
        raise ValueError("LIVE_LOOP icin DATA_SOURCE=google_sheets olmalidir.")

    data_source = build_data_source()
    if not isinstance(data_source, GoogleSheetsDataSource):
        raise TypeError("Canli dongu yalnizca Google Sheets ile calisir.")

    logging.info(
        "Canli dongu basladi | poll=%s sn | DRY_RUN=%s | SMTP=%s | durum_yazimi=%s",
        LIVE_POLL_SECONDS,
        DRY_RUN,
        ENABLE_SMTP_SEND,
        ENABLE_STATUS_UPDATE,
    )
    if DRY_RUN:
        logging.warning("DRY_RUN etkin: SMTP ve durum guncellemesi kapali.")
    while True:
        try:
            logging.info("Radar tarıyor...")
            participants = data_source.records()
            logging.info("Sayfa kontrol edildi | bos Durum satiri=%s", len(participants))
            for participant in participants:
                process_one_record(data_source, participant)
        except KeyboardInterrupt:
            logging.info("Canli dongu sonlandirildi (Ctrl+C).")
            break
        except Exception:
            logging.exception("Canli dongu turunda hata; %s sn sonra tekrar denenecek.", LIVE_POLL_SECONDS)
        time.sleep(LIVE_POLL_SECONDS)


def process_participants() -> None:
    setup_logging()
    TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)

    data_source = build_data_source()
    participants = data_source.records()

    logging.info("Toplam yeni kayit (Durum bos): %s", len(participants))
    if DRY_RUN:
        logging.warning("DRY_RUN etkin: SMTP gonderimi ve durum guncellemesi yapilmayacak.")
    if not ENABLE_SMTP_SEND:
        logging.warning("SMTP gonderimi kapali: mailler simule edilecek.")
    if not ENABLE_STATUS_UPDATE:
        logging.warning("Durum guncellemesi kapali: veri kaynagi yazimi yapilmayacak.")
    prepared_jobs: list[dict[str, Any]] = []

    for participant in participants:
        try:
            if not all(
                [
                    participant["name"],
                    participant["school"],
                    participant["department"],
                    participant["email"],
                ]
            ):
                raise ValueError(f"Eksik katilimci bilgisi: {participant}")

            department_config = get_department_config(participant["department"])
            career_advice = generate_career_advice(
                participant_name=participant["name"],
                department_name=participant["department"],
            )

            pdf_name = (
                f"{sanitize_filename(participant['name'])}_"
                f"{sanitize_filename(participant['department'])}.pdf"
            )
            pdf_output_path = TEMP_PDF_DIR / pdf_name

            generate_participant_pdf(
                template_path=Path(department_config["png_template"]),
                output_path=pdf_output_path,
                font_path=FONT_PATH,
                participant_name=participant["name"],
                school_name=participant["school"],
                department_name=participant["department"],
                career_advice=career_advice,
                text_coords=department_config["text_coords"],
            )

            prepared_jobs.append(
                {
                    "participant": participant,
                    "recipient_email": participant["email"],
                    "subject": department_config["mail_subject"],
                    "body": career_advice,
                    "html_body": build_html_mail_body(
                        participant_name=participant["name"],
                        department_name=participant["department"],
                        career_message=career_advice,
                    ),
                    "attachment_path": pdf_output_path,
                }
            )

        except Exception as exc:
            logging.exception(
                "Kayit islenemedi (%s): %s",
                participant.get("name", "Bilinmiyor"),
                exc,
            )
            if ENABLE_STATUS_UPDATE:
                try:
                    data_source.write_row_status(int(participant["row_ref"]), STATUS_ERROR)
                    logging.info(
                        "Durum guncellendi | satir=%s | %s",
                        participant["row_ref"],
                        STATUS_ERROR,
                    )
                except Exception:
                    logging.exception(
                        "Durum yazilamadi | satir=%s",
                        participant.get("row_ref"),
                    )
            continue

    if not prepared_jobs:
        logging.info("Gonderilecek yeni kayit bulunamadi.")
        return

    if MAX_SEND_COUNT and len(prepared_jobs) > MAX_SEND_COUNT:
        logging.warning(
            "Kademeli gecis limiti etkin: %s kayit icinden ilk %s kayit gonderilecek.",
            len(prepared_jobs),
            MAX_SEND_COUNT,
        )
        prepared_jobs = prepared_jobs[:MAX_SEND_COUNT]

    if not ENABLE_SMTP_SEND:
        sent_indices = list(range(len(prepared_jobs)))
        failures: list[dict[str, Any]] = []
        logging.info("SMTP simule edildi: %s e-posta gonderimi yapilmadi.", len(prepared_jobs))
    else:
        logging.info("Toplu SMTP gonderimi basliyor: %s kayit", len(prepared_jobs))
        sent_indices, failures = send_mail_batch_with_pdf(
            prepared_jobs,
            batch_size=SMTP_BATCH_SIZE,
            sleep_seconds=SMTP_BATCH_SLEEP_SECONDS,
        )

    sent_row_refs: list[int] = []
    sent_jobs: list[dict[str, Any]] = []
    for sent_index in sent_indices:
        job = prepared_jobs[sent_index]
        participant = job["participant"]
        sent_row_refs.append(participant["row_ref"])
        sent_jobs.append(job)
        logging.info("Gonderildi: %s -> %s", participant["name"], participant["email"])

    failed_mail_report: list[dict[str, str]] = []
    for failure in failures:
        failed_index = int(failure["index"])
        participant = prepared_jobs[failed_index]["participant"]
        failed_mail_report.append(
            {
                "name": participant.get("name", "Bilinmiyor"),
                "email": failure.get("recipient_email", participant.get("email", "")),
                "error": failure.get("error", "Bilinmeyen hata"),
            }
        )
        logging.error(
            "Mail gonderilemedi (%s - %s): %s",
            participant.get("name", "Bilinmiyor"),
            failure.get("recipient_email", participant.get("email", "")),
            failure.get("error", "Bilinmeyen hata"),
        )
        if ENABLE_STATUS_UPDATE:
            try:
                data_source.write_row_status(int(participant["row_ref"]), STATUS_ERROR)
                logging.info(
                    "Durum guncellendi | satir=%s | %s",
                    participant["row_ref"],
                    STATUS_ERROR,
                )
            except Exception:
                logging.exception("Durum yazilamadi | satir=%s", participant.get("row_ref"))

    if sent_row_refs and ENABLE_STATUS_UPDATE:
        data_source.mark_sent_batch(sent_row_refs)
        logging.info("Durumlar toplu guncellendi: %s satir", len(set(sent_row_refs)))
    elif sent_row_refs and not ENABLE_STATUS_UPDATE:
        logging.info("Durum guncellemesi simule edildi: %s satir yazilmadi.", len(set(sent_row_refs)))

    post_send_attachment_cleanup(sent_jobs)

    if failed_mail_report:
        report_path = LOGS_DIR / "failed_emails_report.txt"
        lines = [
            f"Toplam denenen: {len(prepared_jobs)}",
            f"Basarili: {len(sent_indices)}",
            f"Basarisiz: {len(failed_mail_report)}",
            "",
            "Basarisiz e-posta listesi:",
        ]
        lines.extend(
            [
                f"- {item['name']} | {item['email']} | {item['error']}"
                for item in failed_mail_report
            ]
        )
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.warning("Basarisiz gonderimler raporlandi: %s", report_path)

    logging.info(
        "Gonderim ozeti -> Hazirlanan: %s | Basarili: %s | Basarisiz: %s",
        len(prepared_jobs),
        len(sent_indices),
        len(failed_mail_report),
    )


if __name__ == "__main__":
    if LIVE_LOOP:
        run_live_loop()
    else:
        process_participants()
