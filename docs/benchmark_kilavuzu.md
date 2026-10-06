# Çıkarıcı benchmark kılavuzu / Extractor benchmark guide

Gerçek MEB PDF'leri ve Gold anotasyonları Git'e eklenmez. Private manifestte her örnek için `page`, `kind` (`text`, `formula`, `table`, `chart`) ve insan tarafından doğrulanmış `expected` alanı bulunur. Formül için beklenen değer konuşma dilindeki erişilebilir okunuş ve yapılandırılmış MathML doğrulamasıyla ayrı tutulacaktır.

Örnek private manifest oluşturulup yalnız yerelde doldurulur:

```json
{"version":"gold-v1","items":[{"id":"formula-p22","page":22,"kind":"formula","expected":""}]}
```

Çalıştırma:

```bash
python -m app.pipeline.benchmark --manifest ../../data/derived/gold.json --input ../../data/meb/kitap.pdf --source-root ../../data/meb --output ../../data/derived/benchmark-result.json
```

Boş `expected` alanları sonucu `blocked_missing_gold_annotations` yapar; bu, ölçüm yokken model seçilmesini engeller. Docling veya PaddleOCR-VL kurulu değilse sonuç `unavailable` olarak kayda geçer. Model yalnız Gold metrikleri yayın eşiğini geçerse iş hattına alınır.

Real MEB PDFs and Gold annotations never enter Git. A private manifest holds `page`, `kind`, and human-verified `expected` values. Empty annotations block measurement; unavailable model packages are recorded as unavailable rather than treated as results.
