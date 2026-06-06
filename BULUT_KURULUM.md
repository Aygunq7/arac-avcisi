# Bulut Kurulum

1. Yeni GitHub repo aç.
2. Bu klasördeki dosyaları repo köküne yükle.
3. Render > New Web Service > GitHub repo seç.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app`
6. Environment:
   - DATA_DIR=data
   - ENABLE_SCHEDULER=1
   - CHECK_INTERVAL_HOURS=4
   - SECRET_KEY=arac-avcisi
   - TELEGRAM_BOT_TOKEN=...
   - TELEGRAM_CHAT_ID=...
7. Deploy sonrası `/health` kontrol et.
