from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
FONT_PATH = ASSETS_DIR / "font.ttf"
OUTPUT_DIR = BASE_DIR / "generated_pdfs"
TEMP_PDF_DIR = BASE_DIR / "temp_pdf"
ARCHIVE_DIR = BASE_DIR / "Arsiv"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

DEFAULT_TEXT_COORDS = {
    "name": (300, 520),
    "school": (300, 580),
    "department": (300, 640),
    "career_advice": (300, 780),
}

FORM_FIELD_ALIASES = {
    "timestamp": ["Zaman Damgası", "Zaman Damgasi", "Timestamp"],
    "first_name": ["Adınız", "Adiniz", "Ad", "First Name"],
    "last_name": ["Soyadınız", "Soyadiniz", "Soyad", "Last Name"],
    "full_name": ["Adınız Soyadınız", "Adiniz Soyadiniz", "Ad Soyad", "AdSoyad", "name"],
    "email": ["E-posta Adresiniz", "Eposta Adresiniz", "E-posta", "Eposta", "Email", "email", "Mail", "mail"],
    "school": ["Okulunuz", "Okul", "okul", "School", "school"],
    "department": ["Bölümünüz", "Bolumunuz", "Bölüm", "Bolum", "department", "Department"],
    "status": ["Durum", "durum", "Status", "status"],
}

DEPARTMENT_MAP = {
    "HAVACILIK YONETIMI": {
        "png_template": TEMPLATES_DIR / "havacilik_yonetimi.png",
        "mail_subject": "Havacılık Yönetimi Kariyer Yol Haritan Hazır",
        "mail_body": (
            "Havacılık yönetimi alanında liderlik ve stratejik gelişim odaklı "
            "kariyer yolculuğun için kişisel raporun ektedir. Geleceğini bugünden planla."
        ),
        "text_coords": DEFAULT_TEXT_COORDS,
    },
    "PILOTAJ": {
        "png_template": TEMPLATES_DIR / "pilotaj.png",
        "mail_subject": "Pilotaj Kariyer Yol Haritan Hazır",
        "mail_body": (
            "Gökyüzüne uzanan kariyer yolculuğunda seni bir adım ileri taşıyacak "
            "kişiselleştirilmiş pilotaj raporun ektedir."
        ),
        "text_coords": DEFAULT_TEXT_COORDS,
    },
    "UCAK TEKNOLOJISI": {
        "png_template": TEMPLATES_DIR / "ucak_teknolojisi.png",
        "mail_subject": "Uçak Teknolojisi Kariyer Yol Haritan Hazır",
        "mail_body": (
            "Teknik uzmanlığını güçlendirecek adımları içeren Uçak Teknolojisi "
            "kariyer yol haritan senin için hazırlandı."
        ),
        "text_coords": DEFAULT_TEXT_COORDS,
    },
}

DEFAULT_DEPARTMENT_CONFIG = {
    "png_template": TEMPLATES_DIR / "genel_kariyer.png",
    "mail_subject": "Kariyer Yol Haritan Hazır",
    "mail_body": (
        "Ilgi alanlarina gore genel kariyer yol haritan hazirlandi. "
        "Ekteki raporla bir sonraki adimini guvenle planlayabilirsin."
    ),
    "text_coords": DEFAULT_TEXT_COORDS,
}

DEPARTMENT_ALIASES = {
    "HAVACILIK YONETIMI": "HAVACILIK YONETIMI",
    "HAVACILIK YÖNETIMI": "HAVACILIK YONETIMI",
    "HAVACILIK YÖNETİMİ": "HAVACILIK YONETIMI",
    "PILOTAJ": "PILOTAJ",
    "UCAK TEKNOLOJISI": "UCAK TEKNOLOJISI",
    "UÇAK TEKNOLOJISI": "UCAK TEKNOLOJISI",
    "UÇAK TEKNOLOJİSİ": "UCAK TEKNOLOJISI",
}


def normalize_department(value: str) -> str:
    return " ".join(value.strip().upper().split())


def get_department_config(department_name: str) -> dict:
    normalized = normalize_department(department_name)
    canonical = DEPARTMENT_ALIASES.get(normalized, normalized)
    return DEPARTMENT_MAP.get(canonical, DEFAULT_DEPARTMENT_CONFIG)
