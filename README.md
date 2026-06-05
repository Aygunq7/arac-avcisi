# Araç Avcısı v16 Temiz Çalışan Sürüm

Bu sürüm önceki yamaların tamamı temizlenerek sıfırdan düzenlendi. Amaç: uygulamanın çökmeden çalışması, seçim kutularının dolması, linklerin doğru üretilmesi ve listeye yalnızca gerçek ilanların düşmesi.

## Özellikler

- Mobil uyumlu web/PWA panel
- Hazır marka, model, paket/motor, şehir ve kaynak seçimi
- Fiyat, yıl, km, yakıt, vites filtresi
- Kullanıcı seçimli kontrol sıklığı
- Yeni ilan ve fiyat düşüşü takibi
- Telegram ve e-posta bildirim desteği
- Sahibinden için direkt deneme + Jina Reader yedek okuma
- Arabam ve Otoplus için daha temiz ilan ayrıştırma
- Sahte sonuç filtresi: “Filtrele”, “arama”, “anasayfa” gibi metinler ilan sayılmaz

## Render kurulumu

1. ZIP içeriğini GitHub reposunun köküne yükle.
2. Render servisinde `Manual Deploy > Deploy latest commit` yap.
3. Environment kısmında en az şunlar olsun:

```text
DATA_DIR=data
CHECK_INTERVAL_HOURS=4
ENABLE_SCHEDULER=1
ENABLE_READER=1
SECRET_KEY=arac-avcisi-gizli
```

Free planda `DATA_DIR=data` kullan. Starter + Disk kullanırsan `DATA_DIR=/data` yap.

## Bildirimler

Telegram:

```text
TELEGRAM_BOT_TOKEN=bot token
TELEGRAM_CHAT_ID=chat id
```

Mail:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mail@gmail.com
SMTP_PASS=gmail uygulama şifresi
MAIL_FROM=mail@gmail.com
MAIL_TO=mail@gmail.com
```

## Önemli not

Bazı siteler otomatik liste okumayı engelleyebilir. Bu sürüm bu engelleri aşmaya çalışmaz, hesap şifresi istemez, CAPTCHA atlatmaz. Engel varsa liste boş kalabilir ama doğru site linki “...’de aç” butonuyla verilir. Sahte ilan üretmez.
