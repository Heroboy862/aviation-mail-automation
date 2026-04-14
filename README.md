# Havacılık Kariyer Yolu Otomasyon Sistemi

Google Sheets veya CSV'den gelen katilimci verilerine gore:
- bolume ozel PNG template secer,
- katilimciya ozel PDF uretir,
- PDF'i e-posta eki olarak gonderir,
- kaydin durumunu `Gonderildi` olarak isaretler.

## Proje Yapisi

```text
mailgönderme/
├─ config.py
├─ pdf_engine.py
├─ mailer.py
├─ main.py
├─ requirements.txt
├─ .env.example
├─ data/
│  └─ participants.csv
├─ assets/
│  ├─ font.ttf
│  └─ templates/
│     ├─ havacilik_yonetimi.png
│     ├─ pilotaj.png
│     └─ ucak_teknolojisi.png
├─ generated_pdfs/
└─ logs/
```

## Gereksinimler

- Python 3.10+
- SMTP erisimi olan bir e-posta hesabi
- (Opsiyonel) Google Service Account JSON dosyasi

Kurulum:

```bash
pip install -r requirements.txt
```

## Konfigurasyon

`.env.example` dosyasini kopyalayip `.env` olusturun:

```bash
cp .env.example .env
```

Windows PowerShell icin:

```powershell
Copy-Item .env.example .env
```

`.env` icine SMTP bilgilerini girin:

```env
DATA_SOURCE=csv
CSV_PATH=data/participants.csv

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ornek@domain.com
SMTP_PASSWORD=uygulama_sifresi
FROM_EMAIL=ornek@domain.com
```

### Google Sheets Kullanimi (Opsiyonel)

`DATA_SOURCE=google_sheets` yapin ve su alanlari doldurun:

```env
GOOGLE_SERVICE_ACCOUNT_JSON=C:/path/to/service-account.json
GOOGLE_SHEET_NAME=SheetAdi
GOOGLE_WORKSHEET_NAME=Sayfa1
```

## Veri Formati

CSV icin `data/participants.csv` basliklari asagidaki varyantlardan biri olabilir:
- Ad: `Ad Soyad`, `AdSoyad`, `name`
- Okul: `Okul`, `school`
- Bolum: `Bolum`, `Bölüm`, `department`
- E-posta: `Eposta`, `E-posta`, `email`
- Durum: `Durum`, `Status` (opsiyonel)

Ornek:

```csv
Ad Soyad,Okul,Bölüm,E-posta,Durum
Ornek Kullanici,Anadolu Universitesi,Pilotaj,ornek@mail.com,
```

## Calistirma

```bash
python main.py
```

## Is Akisi

Her kayit icin:
1. Bolum bilgisi normalize edilir ve `config.py` mapping'inden bulunur.
2. Ilgili PNG template acilir.
3. `assets/font.ttf` ile ad/okul/bolum bilgileri koordinatlara yazilir.
4. PDF `generated_pdfs/` klasorune kaydedilir.
5. PDF e-posta eki olarak gonderilir.
6. Durum `Gonderildi` olarak isaretlenir.

## Hata Yonetimi ve Loglama

- Bir kayit hata verirse sistem durmaz, sonraki kayda gecer.
- Tum hatalar ve islem bilgileri `logs/process.log` dosyasina yazilir.

## Ozellestirme

`config.py` dosyasinda:
- `DEPARTMENT_MAP` ile bolum-template-mail eslesmelerini,
- `text_coords` ile yazi konumlarini,
- `mail_subject` ve `mail_body` ile bolume ozel e-posta metinlerini degistirebilirsiniz.
