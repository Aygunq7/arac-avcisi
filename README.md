# Araç Avcısı v26

Bu sürüm, önceki hatalı sonuçları temizlemek için yeniden düzenlendi.

## Ana düzeltmeler
- Letgo ve Facebook otomatik listeye alınmaz; çünkü çoğunlukla resim/CDN veya alakasız ürün linki döndürüyor. Sadece siteyi aç butonu verir.
- Listeye yalnızca gerçek ilan linkleri alınır. Sahibinden için `/ilan/`, Arabam için `/ilan/` zorunludur.
- Sahibinden aç butonu bozuk kategori yerine genel arama sayfasına gider.
- Otomatik seçiliyken başlık/link içinde manuel geçen ilanlar elenir.
- Yeni ilan ve fiyat düşüşü olaylarında ilan linki gösterilir.
- Filtreler sunucudan basıldığı için marka/model/paket kutuları boş kalmaz.

## Render
Build Command:
```bash
pip install -r requirements.txt
```
Start Command:
```bash
gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app
```

Deploy sonrası:
`/reset-cache` ve `/health` aç.
