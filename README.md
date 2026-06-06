# Araç Avcısı v25

Filtreler sunucudan basılır. JavaScript bozulsa bile seçim kutuları dolu gelir.

## Render
Build: `pip install -r requirements.txt`
Start: `gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app`

## Temizlik
- `/reset-db?key=temizle`
- `/reset-cache`
- `/health`
