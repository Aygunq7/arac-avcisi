# Render Kurulum

1. GitHub reposundaki eski dosyaları mümkünse temizle.
2. Bu paketin içindeki dosyaları repo köküne yükle:
   - app.py
   - templates
   - static
   - requirements.txt
   - render.yaml
   - Procfile
   - Dockerfile
   - README.md
3. Render > Manual Deploy > Clear build cache & deploy.
4. Deploy bitince `/health` aç.
5. Telefon için önce `/reset-cache` aç, sonra ana ekrana tekrar ekle.

## Eski verileri silmek için
Tarayıcıdan aç:

```text
https://SENIN-RENDER-LINKIN.onrender.com/reset-db?key=temizle
```

## Telegram
Render Environment içine:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Mail
Render Environment içine:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mail_adresin
SMTP_PASS=gmail_uygulama_sifren
MAIL_FROM=mail_adresin
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
