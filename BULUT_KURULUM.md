# Render Bulut Kurulum ve Güncelleme

## İlk kurulum

1. ZIP'i bilgisayarda ayıkla.
2. GitHub'da `arac-avcisi` deposuna dosyaları yükle.
3. Render'da Web Service oluştur.
4. Ayarlar:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app
```

## Environment Variables

Free test için:

```text
DATA_DIR=data
CHECK_INTERVAL_HOURS=4
ENABLE_SCHEDULER=1
SECRET_KEY=arac-avcisi-123456789-gizli
```

Kalıcı gerçek kullanım için:

```text
Starter plan + Disk mount path: /data
DATA_DIR=/data
```

## v4 güncellemesi

GitHub'a şu dosya ve klasörleri yeniden yükle:

```text
app.py
static
templates
README.md
BULUT_KURULUM.md
```

Commit sonrası Render otomatik deploy eder. Etmezse:

```text
Manual Deploy > Deploy latest commit
```

## v4 kontrol

Tarayıcıdan aç:

```text
/health
```

Cevap içinde şunu görmelisin:

```text
version: v4-sahibinden-ozel-mod
```

## Sahibinden özel mod nasıl çalışır?

- Uygulama, seçtiğin marka/model/şehir/fiyat/yıl bilgilerine göre Sahibinden arama adresini kendi üretir.
- Sahibinden 429 veya 403 verirse sürekli zorlamaz.
- Kaynak bazlı beklemeye alır.
- Sahibinden için yedek Bing arama bağlantısı gösterir.
- Kayıtlı takip kartında “Sahibinden'de aç” butonu görünür.

Bu sistem şifre saklamaz ve CAPTCHA atlatmaz.


## v5 Paket / Motor Seçimi
- Takip oluştururken artık marka ve modelden sonra hazır Paket / Motor listesi gelir.
- Örnek: Volkswagen > Tiguan > 1.4 TSI Comfortline.
- Mevcut veritabanı otomatik güncellenir; eski takipler Farketmez kabul edilir.
- Güncellemeden sonra Render üzerinde Deploy latest commit yapılması yeterlidir.
