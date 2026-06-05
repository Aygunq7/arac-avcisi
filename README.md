# Araç Avcısı v18

Bu sürüm eski PWA/cache sorununu temizler ve takip kaydını önce veritabanına alır. Site taraması arka planda çalışır; kaynak hata verse bile takip kaydı kaybolmaz.

Deploy sonrası önce `/reset-cache` adresini açın, sonra uygulamayı normal adresten kullanın.

Kontrol: `/health` içinde `v18-cache-temiz-takip-garantili` görünmelidir.

# Araç Avcısı v17 - Kayıt ve Migration Düzeltildi

Bu sürümde takip oluştururken çıkan **İşlem başarısız** hatası için iki ana düzeltme yapıldı:

1. Eski Render veritabanı tabloları otomatik yeni şemaya taşınır.
2. Takip oluşturma artık dış sitelerin cevap vermesini beklemez; takip hemen kaydedilir, başlangıç araması arka planda başlar.

Yüklenecek dosyalar: app.py, templates, static, requirements.txt, render.yaml, Procfile, Dockerfile.

Deploy sonrası kontrol: `/health` içinde `v17-kayit-ve-migration-duzeltildi` görünmeli.
