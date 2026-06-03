# Araç Avcısı Bulut Mobil

Bu sürüm bilgisayara bağlı değildir. Bulutta çalışacak şekilde hazırlanmıştır. Telefonda, tablette ve bilgisayarda web uygulaması gibi açılır.

## Özellikler

- Mobil uyumlu PWA ekranı
- Hazır site seçimi: Sahibinden, Arabam, Letgo, Facebook Marketplace, VavaCars, Otoplus, Otokoç 2. El vb.
- Hazır marka/model seçimi
- Şehir, yıl, km, fiyat, yakıt, vites filtreleri
- İlk aramayı başlangıç listesi olarak kaydetme
- 4 saatte bir otomatik kontrol
- Yeni ilan bildirimi
- Fiyat düşüşü bildirimi
- Telegram bildirimi
- Mail bildirimi
- Kalıcı veritabanı desteği için DATA_DIR ayarı
- Render, Railway ve Docker/VPS kurulumu için hazır dosyalar

## Bulutta çalışma mantığı

Telefon sadece ekran değildir; telefondan arama oluşturabilir, kaynak/marka/model seçebilir ve sonuçları görebilirsin. Ancak 4 saatte bir kontrol işi sunucuda çalışır. Böylece bilgisayarın açık kalmaz.

## Dosyalar

- `app.py`: ana uygulama
- `templates/index.html`: mobil web ekranı
- `static/`: PWA, CSS, JS dosyaları
- `render.yaml`: Render kurulumu
- `railway.json`: Railway kurulumu
- `Dockerfile`: VPS/Docker kurulumu
- `Procfile`: PaaS start komutu
- `BULUT_KURULUM.md`: adım adım kurulum

## Hızlı kurulum

Detaylar için `BULUT_KURULUM.md` dosyasını aç.


## Kontrol sıklığı

Bu sürümde kontrol süresi sabit 4 saat değildir. Takip oluştururken **Kaç saatte bir kontrol edilsin?** alanından 1, 2, 3, 4, 6, 8, 12, 24, 48 veya 72 saat seçilebilir. Kayıtlı takiplerde bu süre sonradan **Süreyi kaydet** butonuyla değiştirilebilir.

Arka plandaki zamanlayıcı varsayılan olarak 15 dakikada bir uyanır ve süresi dolan takipleri kontrol eder. İstenirse Render Environment bölümüne `SCHEDULER_TICK_MINUTES` eklenerek bu uyanma aralığı değiştirilebilir.
