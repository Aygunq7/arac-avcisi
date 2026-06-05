# Bulut Kurulum

## GitHub

ZIP’i ayıkla. Şu dosyaları repo köküne yükle:

```text
app.py
templates
static
requirements.txt
render.yaml
Procfile
Dockerfile
README.md
BULUT_KURULUM.md
```

## Render

### Web Service ayarları

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app
Health Check Path: /health
```

### Free plan

```text
DATA_DIR=data
ENABLE_SCHEDULER=1
ENABLE_READER=1
CHECK_INTERVAL_HOURS=4
```

### Starter + Disk

Disk:

```text
Mount Path: /data
Size: 1 GB
```

Environment:

```text
DATA_DIR=/data
ENABLE_SCHEDULER=1
ENABLE_READER=1
CHECK_INTERVAL_HOURS=4
```

## Kontrol

Deploy sonrası aç:

```text
https://senin-linkin.onrender.com/health
```

`version: v16-temiz-calisan` görünmeli.
