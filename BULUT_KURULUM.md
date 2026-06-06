# Bulut Kurulum

## GitHub

ZIP içindeki dosyaları repo ana dizinine yükle. `app.py`, `requirements.txt`, `templates`, `static` repo kökünde görünmeli.

## Render Web Service

- Runtime: Python
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app`
- Health Check Path: `/health`

## Environment

Free test için:

```text
DATA_DIR=data
CHECK_INTERVAL_HOURS=4
ENABLE_SCHEDULER=1
SCHEDULER_TICK_MINUTES=15
SECRET_KEY=uzun-bir-sifre
```

Kalıcı kullanım için paid disk eklersen:

```text
DATA_DIR=/data
```

ve Render disk mount path `/data` olmalı.

## Kontrol

Deploy bitince:

```text
/health
```

sonucunda sürüm `v21-sifirdan-stabil-jina-destekli` olmalı.
