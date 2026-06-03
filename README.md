# Araç Avcısı v4

Bulutta çalışan mobil web/PWA ikinci el araç takip uygulaması.

## v4 yenilikleri

- Sahibinden özel mod eklendi.
- Sahibinden arama linki otomatik üretilir, kullanıcı link yazmaz.
- 429 / 403 / 400 gibi engel durumlarında kaynak bazlı bekleme sistemi çalışır.
- Sahibinden için Bing yedek arama bağlantısı ve yedek yakalama modu eklendi.
- Kayıtlı takiplerde her kaynak için “sitede aç” butonu eklendi.
- Aynı takip tekrar oluşturulmaz, kopya takip engellenir.
- Takip silme butonu eklendi.
- Kontrol sıklığı takip bazlı seçilir.

## Önemli not

Bu sürüm CAPTCHA atlatmaz, şifre saklamaz, proxy ile engel aşmaz. Engelleyen kaynaklar için bekleme ve yedek arama kullanır. Bu daha güvenli ve sürdürülebilir yoldur.

## Render güncelleme

GitHub deposuna şu dosya ve klasörleri yükle:

```text
app.py
static
static/app.js
static/app.css
templates
templates/index.html
README.md
```

Sonra Render otomatik deploy başlatır. Başlatmazsa:

```text
Manual Deploy > Deploy latest commit
```

Test:

```text
https://senin-linkin.onrender.com/health
```

`version: v4-sahibinden-ozel-mod` görürsen güncelleme gelmiş demektir.


## v5 Paket / Motor Seçimi
- Takip oluştururken artık marka ve modelden sonra hazır Paket / Motor listesi gelir.
- Örnek: Volkswagen > Tiguan > 1.4 TSI Comfortline.
- Mevcut veritabanı otomatik güncellenir; eski takipler Farketmez kabul edilir.
- Güncellemeden sonra Render üzerinde Deploy latest commit yapılması yeterlidir.
