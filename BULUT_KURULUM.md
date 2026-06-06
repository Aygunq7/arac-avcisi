# Bulut Kurulum

1. ZIP içindeki dosyaları mevcut GitHub reposuna yükle.
2. Render > Manual Deploy > Clear build cache & deploy yap.
3. Deploy sonrası `/reset-cache` aç.
4. `/health` içinde `v26-temiz-link-filtre-bildirim` gör.

Environment:
```text
DATA_DIR=data
ENABLE_SCHEDULER=1
CHECK_INTERVAL_HOURS=4
SECRET_KEY=arac-avcisi-v26
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
MAIL_FROM=...
DEFAULT_NOTIFY_EMAIL=...
```
