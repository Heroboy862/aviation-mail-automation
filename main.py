import logging
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from config import DATA_DIR, FONT_PATH, LOGS_DIR, OUTPUT_DIR, get_department_config
from mailer import send_mail_with_pdf
from pdf_engine import generate_participant_pdf

load_dotenv()

STATUS_VALUES_SENT = {"gonderildi", "gönderildi", "sent"}


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
        candidates = ["Durum", "durum", "Status", "status"]
        for candidate in candidates:
            if candidate in self.df.columns:
                return candidate
        return "Durum"

    def records(self) -> list[dict[str, Any]]:
        output = []
        for idx, row in self.df.iterrows():
            row_dict = row.to_dict()
            output.append(
                {
                    "row_ref": int(idx),
                    "name": get_first_existing_key(row_dict, ["Ad Soyad", "AdSoyad", "ad_soyad", "name"]),
                    "school": get_first_existing_key(row_dict, ["Okul", "okul", "School", "school"]),
                    "department": get_first_existing_key(
                        row_dict,
                        ["Bolum", "Bölüm", "bolum", "bölüm", "Department", "department"],
                    ),
                    "email": get_first_existing_key(
                        row_dict,
                        ["Eposta", "E-posta", "Email", "email", "Mail", "mail"],
                    ),
                    "status": str(row_dict.get(self.status_column, "")).strip(),
                }
            )
        return output

    def mark_sent(self, row_ref: int) -> None:
        self.df.at[row_ref, self.status_column] = "Gönderildi"
        self.df.to_csv(self.csv_path, index=False)


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
        candidates = ["Durum", "durum", "Status", "status"]
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
            output.append(
                {
                    "row_ref": i,
                    "name": get_first_existing_key(row, ["Ad Soyad", "AdSoyad", "ad_soyad", "name"]),
                    "school": get_first_existing_key(row, ["Okul", "okul", "School", "school"]),
                    "department": get_first_existing_key(
                        row,
                        ["Bolum", "Bölüm", "bolum", "bölüm", "Department", "department"],
                    ),
                    "email": get_first_existing_key(
                        row,
                        ["Eposta", "E-posta", "Email", "email", "Mail", "mail"],
                    ),
                    "status": get_first_existing_key(row, [self.status_column]),
                }
            )
        return output

    def mark_sent(self, row_ref: int) -> None:
        self.worksheet.update_cell(row_ref, self.status_col_index, "Gönderildi")


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
        return GoogleSheetsDataSource(
            credentials_path=Path(credentials_path),
            sheet_name=sheet_name,
            worksheet_name=worksheet_name,
        )

    csv_path = Path(os.getenv("CSV_PATH", str(DATA_DIR / "participants.csv")))
    return CSVDataSource(csv_path=csv_path)


def process_participants() -> None:
    setup_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data_source = build_data_source()
    participants = data_source.records()

    logging.info("Toplam kayit: %s", len(participants))
    for participant in participants:
        try:
            status = participant["status"].strip().lower()
            if status in STATUS_VALUES_SENT:
                logging.info("Atlandi (zaten gonderildi): %s", participant["name"])
                continue

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

            pdf_name = (
                f"{sanitize_filename(participant['name'])}_"
                f"{sanitize_filename(participant['department'])}.pdf"
            )
            pdf_output_path = OUTPUT_DIR / pdf_name

            generate_participant_pdf(
                template_path=Path(department_config["png_template"]),
                output_path=pdf_output_path,
                font_path=FONT_PATH,
                participant_name=participant["name"],
                school_name=participant["school"],
                department_name=participant["department"],
                text_coords=department_config["text_coords"],
            )

            send_mail_with_pdf(
                recipient_email=participant["email"],
                subject=department_config["mail_subject"],
                body=department_config["mail_body"],
                attachment_path=pdf_output_path,
            )

            data_source.mark_sent(participant["row_ref"])
            logging.info("Gonderildi: %s -> %s", participant["name"], participant["email"])

        except Exception as exc:
            logging.error("Kayit islenemedi (%s): %s", participant.get("name", "Bilinmiyor"), exc)
            continue


if __name__ == "__main__":
    process_participants()
