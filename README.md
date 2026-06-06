# Araç Avcısı v24

Sıfırdan temiz yazılmış mobil web/PWA ikinci el araç takip paneli.

## Mantık
- Takip önce kaydedilir.
- Site taraması arka planda veya `Şimdi kontrol et` ile yapılır.
- Gerçek ilan linki bulunursa listelenir.
- Sahte kategori/filtre sayfaları ilan sayılmaz.
- Yeni ilan ve fiyat düşüşü olaylarında ilan linki kaydedilir.

## Önemli gerçek
Sahibinden, Facebook, Letgo gibi siteler otomatik listelemeyi engelleyebilir. Uygulama bu engelleri aşmaya çalışmaz, yanlış ilan üretmez. Gerçek ilan linki bulduğunda listeler.

## Render
Start command:

```bash
gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:APP
```

Health:

```text
/health
```

Cache temizleme:

```text
/reset-cache
```

Veri sıfırlama:

```text
/reset-db?key=temizle
```


## Bildirim ayarları

Telegram için Render Environment içine şunları ekle:

```text
TELEGRAM_BOT_TOKEN=BotFather tokeni
TELEGRAM_CHAT_ID=senin chat id
```

Mail için Gmail uygulama şifresiyle şunları ekle:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mail_adresin@gmail.com
SMTP_PASS=gmail_uygulama_sifren
MAIL_FROM=mail_adresin@gmail.com
DEFAULT_NOTIFY_EMAIL=bildirim_alacak_mail
```

Uygulamada önce **Bildirim testi** bölümünden test gönder. Test geçmeden yeni ilan bildirimi bekleme.
