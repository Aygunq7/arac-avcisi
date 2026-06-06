# Araç Avcısı v21

Sıfırdan yazılmış stabil mobil web uygulaması.

## Ne değişti?

- Eski yamalı kodlar kaldırıldı.
- Takip önce veritabanına kaydedilir, arama arkada çalışır.
- Sahte ilan üretmez.
- Liste alırken üç katman kullanır:
  1. Site HTML okuma
  2. Jina Reader URL okuma
  3. Jina Search site içi yedek arama
- Sahibinden, Arabam, Otoplus, Otokoç, VavaCars, Araba Sepeti, Arabalar.com, Letgo, Facebook için hazır site butonları vardır.
- Marka/model/paket/şehir/fiyat/yıl/km/vites seçimi çalışır.

## Önemli gerçek

Sahibinden, Facebook Marketplace ve bazı ilan siteleri bulut sunuculardan gelen otomatik istekleri engelleyebilir. Bu uygulama CAPTCHA/proxy/şifreli giriş atlatmaz. Engelli kaynaklarda sahte ilan üretmek yerine “liste yok” der ve siteyi aç butonunu verir.

## Render kurulum

1. Dosyaları GitHub repo köküne yükle.
2. Render Web Service ayarları:

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app
```

Environment:
```text
DATA_DIR=data
CHECK_INTERVAL_HOURS=4
ENABLE_SCHEDULER=1
SCHEDULER_TICK_MINUTES=15
SECRET_KEY=uzun-bir-sifre
```

3. Deploy sonrası kontrol:
```text
https://senin-linkin.onrender.com/health
```

`version` alanında `v21-sifirdan-stabil-jina-destekli` görünmelidir.

## Eski mobil cache temizleme

Telefondan şunu aç:
```text
https://senin-linkin.onrender.com/reset-cache
```

Sonra Safari/Chrome ile tekrar ana ekrana ekle.

## Telegram ve mail

Render Environment alanına eklenebilir:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
MAIL_FROM=...
```
