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

## v6 Liste Görünümü
- Arama veya manuel kontrol sonrası bulunan ilanlar otomatik olarak takip kartının altında açılır.
- İlanlar kaynak/site bazında gruplanır.
- Her ilan için site adı, başlık, fiyat, yıl, km, ilk/son görülme zamanı ve direkt ilan linki gösterilir.
- Link kopyalama butonu eklendi.
- Takip kartında toplam bulunan ilan ve site bazlı ilan sayıları görünür.


## v7-link-liste-duzeltme

- Site aç butonları boş sayfa yerine daha geniş marka/model sayfasına gider.
- Bütün kaynaklarda yedek arama modu var. Direkt site liste vermezse Bing site içi sonuçlarından ilan yakalamaya çalışır.
- Arabam, Sahibinden ve Otoplus için path tabanlı link üretimi düzeltildi.
- /health çıktısında version v7-link-liste-duzeltme görünmelidir.


## v8 notu
Bu sürümde site aç butonlarının ana sayfaya düşmesi azaltıldı. Sahibinden, Arabam ve Otoplus için marka/model/paket URL yapısı düzeltildi; liste yakalama parserı genişletildi. Deploy sonrası /health içinde v8-link-ve-liste-net-duzeltme görünmelidir.
