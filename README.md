# Havacilik Kariyer Yolu Otomasyon Sistemi

Bu proje CSV veya Google Sheets kaynagindan katilimci bilgilerini okuyup:
- bolume ozel PDF rapor olusturur,
- ekiyle birlikte e-posta gonderir (batch SMTP),
- gonderilen kayitlarin durumunu toplu gunceller (`update_cells`),
- hatali gonderimleri raporlar.

## Neler Degisti (Modern Yapi)

- **Batch mailing:** Mailler varsayilan olarak 50'lik paketlerle gonderilir.
- **Rate limit korumasi:** Her paket arasinda varsayilan 10 saniye beklenir.
- **SMTP timeout korumasi:** Her paket icin SMTP baglantisi yeniden acilir/kapanir.
- **HTML email:** Duz metin + f-string ile uretilen HTML icerik birlikte gonderilir.
- **Batch status update:** Google Sheets durum kolonunda `update_cells` ile toplu guncelleme yapilir.
- **Error resilience:** Basarisiz mailler toplanir, sistem durmaz, surec sonunda rapor uretilir.

## Proje Yapisi

```text
mailgonderme/
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
   ├─ process.log
   └─ failed_emails_report.txt   # sadece hata varsa olusur
```

## Gereksinimler

- Python 3.10+
- SMTP erisimi olan e-posta hesabi (uygulama sifresi onerilir)
- (Opsiyonel) Google Service Account JSON

Kurulum:

```bash
pip install -r requirements.txt
```

## Konfigurasyon

`.env.example` dosyasini kopyalayip `.env` olusturun:

```powershell
Copy-Item .env.example .env
```

### Temel Ayarlar

```env
DATA_SOURCE=csv
CSV_PATH=data/participants.csv

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ornek@domain.com
SMTP_PASSWORD=uygulama_sifresi
FROM_EMAIL=ornek@domain.com
```

### Batch Ayarlari

```env
SMTP_BATCH_SIZE=50
SMTP_BATCH_SLEEP_SECONDS=10
```

### Guvenli Test Modu (Dry Run)

Gercek SMTP gonderimi ve veri kaynagi yazimini kapatip uctan uca akis testi yapmak icin:

```env
DRY_RUN=true
```

`DRY_RUN=true` iken:
- PDF uretimi ve kayit hazirlama adimlari calisir,
- SMTP gonderimi sadece simule edilir,
- CSV/Google Sheets durum guncellemesi yapilmaz,
- surec loglari ve ozet raporlar uretilir.

### Kademeli Canliya Gecis (Onerilen)

Canliya asamali gecis icin su bayraklari kullanabilirsin:

```env
ENABLE_SMTP_SEND=true
ENABLE_STATUS_UPDATE=false
MAX_SEND_COUNT=25
```

- `ENABLE_SMTP_SEND=false`: Mail gonderimini simule eder.
- `ENABLE_STATUS_UPDATE=false`: CSV/Google Sheets durum yazimini kapatir.
- `MAX_SEND_COUNT=25`: Sadece ilk 25 kayitla test gonderimi yapar (`0` = sinirsiz).

### Google Sheets Ayarlari (Opsiyonel)

Google Sheets kullanmak icin:

```env
DATA_SOURCE=google_sheets
GOOGLE_SERVICE_ACCOUNT_JSON=C:/path/to/service-account.json
GOOGLE_SHEET_NAME=SheetAdi
GOOGLE_WORKSHEET_NAME=Sayfa1
```

## Veri Formati

CSV veya Sheets kolon adlari su varyantlardan biri olabilir:
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

1. Kayitlar okunur ve `Gonderildi` durumundakiler atlanir.
2. Her uygun kayit icin bolume ozel PDF uretilir.
3. Her kayit icin plain text + HTML e-posta govdesi hazirlanir.
4. SMTP batch gonderim yapilir (50'lik paketler, aralarda bekleme).
5. Basarili gonderimlerin satirlari toplu olarak `Gonderildi` isaretlenir.
6. Basarisiz e-postalar raporlanir ve surec ozeti loglanir.

## Loglama ve Hata Yonetimi

- Surec loglari: `logs/process.log`
- Basarisiz gonderim raporu: `logs/failed_emails_report.txt`
- Bir e-posta hata verirse sistem tum sureci durdurmaz; diger kayitlara devam eder.

## Ozellestirme

`config.py` dosyasinda:
- `DEPARTMENT_MAP`: bolum-template-mail eslesmesi
- `text_coords`: PDF yazi koordinatlari
- `mail_subject` / `mail_body`: bolume ozel mesajlar

`main.py` dosyasinda:
- `build_html_mail_body(...)`: HTML e-posta tasarimi

## Performans Notu (500-1000 Kullanici)

Bu yapi orta-yuksek hacim icin optimize edilmistir:
- SMTP baglantisi her batch icin yeniden acilir (timeout riski azalir),
- Google Sheets tek tek degil toplu guncellenir,
- hata toleransli akis sayesinde kampanya sureci yarida kesilmez.

## Gecis Kolaylastirici Fallbackler

- `CSV_PATH` bulunamazsa proje kokundeki `participants.csv` otomatik denenir.
- Template dosyalari henuz hazir degilse `ALLOW_MISSING_TEMPLATE_FALLBACK=true` ile gecici beyaz PDF uretilir.
