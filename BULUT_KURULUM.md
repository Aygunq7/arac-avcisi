# Araç Avcısı v18

Bu sürüm eski PWA/cache sorununu temizler ve takip kaydını önce veritabanına alır. Site taraması arka planda çalışır; kaynak hata verse bile takip kaydı kaybolmaz.

Deploy sonrası önce `/reset-cache` adresini açın, sonra uygulamayı normal adresten kullanın.

Kontrol: `/health` içinde `v18-cache-temiz-takip-garantili` görünmelidir.

# Render Kurulum / Güncelleme

GitHub'a ZIP içindeki tüm dosyaları yükle ve Render'da **Deploy latest commit** yap.

Environment önerileri:

- DATA_DIR=data  (Free test için)
- DATA_DIR=/data (Starter + disk varsa)
- ENABLE_SCHEDULER=1
- CHECK_INTERVAL_HOURS=4
- SECRET_KEY=uzun-bir-sifre

Bu sürüm eski veritabanını otomatik taşır, veritabanını silmen gerekmez.
