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

Grafik/tablo aday sayfaları önce private vektör/gömülü-görüntü envanterinden geçirilir:

```bash
python -m app.pipeline.pdf_vector_evidence --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 51 91 --output ../../data/derived/vector-evidence.json
```

Bu çıktı yalnız kaynak koordinatlı yönlendirme kanıtıdır; tablo veya grafik verisi değildir. `vector-geometry-available` sonucu vektör tabanlı çıkarıcı benchmark'ına, `embedded-image-needs-visual-extraction` sonucu görsel model benchmark'ına yönlenir.

Vektör geometri varsa bir sonraki aday, semantik sonuç üretmeden yalnız ızgara/eksen bölgelerini çıkarır:

```bash
python -m app.pipeline.pdf_vector_structure --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 51 91 --output ../../data/derived/vector-structure.json
```

`rectilinear-grid-candidate` ve `perpendicular-axis-candidate` sonuçları yayınlanabilir tablo/grafik değildir. Bunlar, kaynak koordinatlı karşılaştırma bölgeleridir; hücre ilişkileri ve grafik değerleri ancak ayrı şema doğrulaması ile oluşturulabilir.

Aynı sayfada vektör ve gömülü görsel bulunabilir. Bölge bazlı private yönlendirme planı, vektör adaylarını ve onlarla çakışmayan görselleri ayrı benchmark rotalarına verir:

```bash
python -m app.pipeline.pdf_structure_routing --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 51 91 --output ../../data/derived/structure-routing.json
```

`vector-geometry-benchmark` yapı çıkarıcılarını, `visual-model-benchmark` ise PaddleOCR-VL veya benchmark ile onaylanmış fallback'i aday gösterir. Her rota öğretmen denetimi ve şema doğrulaması gerektirir.

Real MEB PDFs and Gold annotations never enter Git. A private manifest holds `page`, `kind`, and human-verified `expected` values. Empty annotations block measurement; unavailable model packages are recorded as unavailable rather than treated as results.

Chart/table candidate pages first pass through the private vector/embedded-image inventory. Its output is routing evidence with source coordinates, not table or chart data. `vector-geometry-available` routes to a vector-based extractor benchmark; `embedded-image-needs-visual-extraction` routes to a visual-model benchmark.

When vector geometry is available, the next candidate extracts only grid/axis regions without producing semantic results. `rectilinear-grid-candidate` and `perpendicular-axis-candidate` are source-linked comparison regions, not publishable tables or charts. Cell relationships and chart values require separate schema validation.

A page can contain both vectors and embedded images. The private region-level routing plan sends vector candidates and non-overlapping images to separate benchmark routes. `vector-geometry-benchmark` identifies structured-extraction candidates, while `visual-model-benchmark` identifies PaddleOCR-VL or another benchmark-approved fallback. Every route still requires schema validation and teacher review.
