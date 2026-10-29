# YKS Tarih kapsam seçimi

İlk üretim sürümü tek sınıf ve altı üniteyle sınırlıdır. Sınıf seçimi, 2022–2026 resmî ÖSYM TYT/AYT kitapçıklarının **yerel ve öğretmen onaylı metadata etiketleriyle** yapılır. Soru metni, şık, cevap anahtarı ve PDF bu işlemde saklanmaz ya da Kaggle'a aktarılmaz.

Her metadata kaydı yalnız soru kimliği, yıl, test, soru numarası, sınıf, ünite, kavram, ilişki türü, görsel bağımlılığı, MEB'de doğrudan kanıtlanabilirlik, erişilebilirlik ve inceleme durumunu içerir.

Puanlama sabittir: soru sıklığı %40, doğrudan MEB kanıtı %25, ilişki grafiği değeri %20 ve erişilebilirlik %15. En yüksek sınıfın en yüksek puanlı altı ünitesi seçilir. Seçim, ilgili MEB kitabı yerelde sürümlenebiliyor ve 120 yasal/onaylı soru havuzu sağlanabiliyorsa geçerlidir; aksi durumda sıradaki sınıf değerlendirilir.

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.yks_history_scope \
  --input data/private/yks-history-metadata-v1.json \
  --output data/private/yks-history-scope-report-v1.json
```

Girdi `yks-history-metadata-v1` şemasını kullanır. Komut ham soru metni veya cevap anahtarı alanı görürse başarısız olur.
