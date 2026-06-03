# Araç Avcısı Bulut Mobil Kurulum

Bu paket bilgisayarda açık kalmak zorunda değildir. Bir bulut sunucuda çalışır; telefondan, tabletten ve bilgisayardan web uygulaması gibi açılır.

## En temiz yapı

- Telefon: mobil web/PWA ekranı
- Bulut sunucu: 4 saatte bir ilan kontrol motoru
- Kalıcı disk/veritabanı: aramalar, eski fiyatlar ve görülen ilanlar
- Telegram + mail: yeni ilan ve fiyat düşüşü bildirimi

## Render ile kurulum

1. Bu klasörü GitHub reposuna yükle.
2. Render hesabında **New > Blueprint** seç.
3. GitHub reposunu bağla.
4. Render, `render.yaml` dosyasını okuyarak servisi kurar.
5. Ortam değişkenlerini gir:

```env
TELEGRAM_BOT_TOKEN=telegram_bot_token
TELEGRAM_CHAT_ID=varsayilan_chat_id
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mail_adresin@gmail.com
SMTP_PASS=gmail_uygulama_sifresi
MAIL_FROM=mail_adresin@gmail.com
```

6. Deploy bitince sana `https://...onrender.com` tarzı bir adres verir.
7. Bu adresi telefonda Safari/Chrome ile aç.
8. Telefonda **Ana Ekrana Ekle** yap.

`render.yaml` içinde `/data` kalıcı disk olarak ayarlı. Uygulamanın SQLite veritabanı burada saklanır.

## Railway ile kurulum

1. Bu klasörü GitHub reposuna yükle.
2. Railway üzerinde yeni proje oluştur ve GitHub reposunu bağla.
3. Ortam değişkenlerini gir:

```env
DATA_DIR=/app/data
CHECK_INTERVAL_HOURS=4
ENABLE_SCHEDULER=1
TELEGRAM_BOT_TOKEN=telegram_bot_token
TELEGRAM_CHAT_ID=varsayilan_chat_id
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=mail_adresin@gmail.com
SMTP_PASS=gmail_uygulama_sifresi
MAIL_FROM=mail_adresin@gmail.com
```

4. Railway'de kalıcı Volume ekle ve mount path olarak `/app/data` kullan.
5. Deploy bitince verilen web adresini telefondan aç.

## VPS / Docker ile kurulum

Sunucuda Docker varsa:

```bash
docker build -t arac-avcisi .
docker run -d --name arac-avcisi \
  -p 5050:5050 \
  -v arac_avcisi_data:/data \
  -e DATA_DIR=/data \
  -e CHECK_INTERVAL_HOURS=4 \
  -e ENABLE_SCHEDULER=1 \
  -e TELEGRAM_BOT_TOKEN="TOKEN" \
  -e TELEGRAM_CHAT_ID="CHAT_ID" \
  -e SMTP_HOST="smtp.gmail.com" \
  -e SMTP_PORT="587" \
  -e SMTP_USER="MAIL" \
  -e SMTP_PASS="UYGULAMA_SIFRESI" \
  -e MAIL_FROM="MAIL" \
  arac-avcisi
```

Sonra alan adı veya sunucu IP adresiyle açılır.

## Telefona uygulama gibi ekleme

### iPhone
Safari > paylaş butonu > Ana Ekrana Ekle

### Android
Chrome > üç nokta > Ana ekrana ekle / Uygulamayı yükle

## Notlar

- Site linki yazmazsın; kaynaklar hazır gelir.
- Marka/model elle yazmazsın; listeden seçersin.
- İlk arama başlangıç kaydıdır; sonraki kontroller yeni ilan ve fiyat düşüşü bildirir.
- Bazı siteler bot erişimini kısıtlayabilir. Bu durumda o site için özel adaptör veya resmi veri kaynağı gerekir.
- Facebook Marketplace giriş ve erişim kısıtları nedeniyle her bulut ortamında otomatik okunmayabilir.


## Kontrol sıklığı

Bu sürümde kontrol süresi sabit 4 saat değildir. Takip oluştururken **Kaç saatte bir kontrol edilsin?** alanından 1, 2, 3, 4, 6, 8, 12, 24, 48 veya 72 saat seçilebilir. Kayıtlı takiplerde bu süre sonradan **Süreyi kaydet** butonuyla değiştirilebilir.

Arka plandaki zamanlayıcı varsayılan olarak 15 dakikada bir uyanır ve süresi dolan takipleri kontrol eder. İstenirse Render Environment bölümüne `SCHEDULER_TICK_MINUTES` eklenerek bu uyanma aralığı değiştirilebilir.
