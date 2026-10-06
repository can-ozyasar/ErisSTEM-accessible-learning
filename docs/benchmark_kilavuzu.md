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

Izgara adayları için hücre değerleri okunmadan önce yalnız hücre geometrisi çıkarılabilir:

```bash
python -m app.pipeline.pdf_vector_grid --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 91 --output ../../data/derived/vector-grid.json
```

Bu hücreler `requires-schema-validation-and-review` durumundadır; başlık, veri hücresi, birleştirme veya öğrenciye gösterilecek değer taşımaz.

Yerel PDF metin katmanındaki blok, merkezi tek bir hücredeyse ve bloğun en az %80'i hücre içindeyse private taslağa bağlanır:

```bash
python -m app.pipeline.pdf_grid_text_binding --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 91 --output ../../data/derived/grid-text-draft.json
```

Belirsiz veya hücreler arasında taşan metin hiç bölünmez; `unbound-needs-fallback-or-review` olarak kalır. Bu katman OCR/LLM sonucu üretmez.

Bir ızgaradaki hücrelerin en az %50'si güvenle bağlanmadıkça rota `candidate-table-schema-validation` olmaz; `insufficient-bound-text-needs-chart-or-visual-route` olarak kalır. Bu eşik yayın eşiği değil, semantik tablo şemasına erken geçmeyi engelleyen yönlendirme korumasıdır.

Komşu düşük-bağlama ızgaraları aynı tablo bandını oluşturuyorsa, yalnız birleşik bölge private görsel fallback crop'ı olur:

```bash
python -m app.pipeline.pdf_grid_visual_fallback --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 46 --output-dir ../../data/derived/grid-visual-regions --manifest ../../data/derived/grid-visual-regions.json
```

Bu birleşim geometriye dayanır; hücre/başlık/değer yorumu değildir. Tam sayfa dışa aktarılmaz.

Aynı sayfada vektör ve gömülü görsel bulunabilir. Bölge bazlı private yönlendirme planı, vektör adaylarını ve onlarla çakışmayan görselleri ayrı benchmark rotalarına verir:

```bash
python -m app.pipeline.pdf_structure_routing --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 51 91 --output ../../data/derived/structure-routing.json
```

`vector-geometry-benchmark` yapı çıkarıcılarını, `visual-model-benchmark` ise PaddleOCR-VL veya benchmark ile onaylanmış fallback'i aday gösterir. Her rota öğretmen denetimi ve şema doğrulaması gerektirir.

Görsel rota yalnız kaynak bölgesini private crop olarak render eder; tam PDF sayfası veya kaynak belge export edilmez:

```bash
python -m app.pipeline.pdf_visual_regions --input ../../data/meb/kitap.pdf --source-root ../../data/meb --pages 51 --output-dir ../../data/derived/visual-regions --manifest ../../data/derived/visual-regions.json
```

Görsel model sonucu yalnız sıkı JSON tablo/grafik şemasına doğrulanarak kabul edilir. HTML, serbest Markdown veya doğrudan UI render'ı kabul edilmez; her taslak `source_checksum`, sayfa ve bbox ile eşleşmelidir.

Bir model tablo işaretlemesi döndürürse bu işaretleme yalnız private adaptörde veri olarak ayrıştırılır; `td/th` metinleri sıkı JSON hücre şemasına geçirilir. Model HTML'si asla tarayıcıya veya öğrenci API'sine verilmez. Ayrıştırılamayan, kapanmamış veya tablo olmayan işaretleme reddedilir.

P46 görsel tablo deneyi, yalnız biçim/şema hattının çalıştığını gösterir; tek örnek model onayı değildir. Private Gold tablo manifesti `visual-table-gold-v1` şemasında kaynak bölgesi (`region_id`, checksum, sayfa, bbox) ve insan doğrulamalı hücreleri tutar. Taslak ile Gold kaynakları birebir eşleşmeden metrik hesaplanmaz. Üçten az Gold tablo örneği otomatik olarak `blocked_insufficient_gold_samples` sonucunu üretir; yeterli örnekte de her hücre, rol ve metin tam eşleşmeden aday üretim için onaylanmaz. Başarılı benchmark öğretmen denetimini kaldırmaz.

```bash
python -m app.pipeline.visual_table_benchmark \
  --drafts ../../data/private/paddle/table_drafts.json \
  --gold ../../data/private/gold/visual-table-gold-v1.json \
  --output ../../data/private/paddle/table-gold-report.json
```

Real MEB PDFs and Gold annotations never enter Git. A private manifest holds `page`, `kind`, and human-verified `expected` values. Empty annotations block measurement; unavailable model packages are recorded as unavailable rather than treated as results.

Chart/table candidate pages first pass through the private vector/embedded-image inventory. Its output is routing evidence with source coordinates, not table or chart data. `vector-geometry-available` routes to a vector-based extractor benchmark; `embedded-image-needs-visual-extraction` routes to a visual-model benchmark.

When vector geometry is available, the next candidate extracts only grid/axis regions without producing semantic results. `rectilinear-grid-candidate` and `perpendicular-axis-candidate` are source-linked comparison regions, not publishable tables or charts. Cell relationships and chart values require separate schema validation.

For grid candidates, cell geometry can be extracted before reading any cell values. These cells remain `requires-schema-validation-and-review`: they contain no header/data/merge interpretation and no student-visible value.

A native PDF text block is bound to a private grid draft only when its centre is in exactly one cell and at least 80% of the block lies within that cell. Ambiguous or spanning text is never split; it remains `unbound-needs-fallback-or-review`. This layer does not generate OCR or LLM output.

Unless at least 50% of a grid's cells are safely bound, its route cannot become `candidate-table-schema-validation`; it remains `insufficient-bound-text-needs-chart-or-visual-route`. This is a routing safeguard, not a publication threshold.

When adjacent low-binding grids form the same table band, only their merged region becomes a private visual-fallback crop. The merge is geometric only; it does not interpret cells, headers, or values, and never exports a full page.

A page can contain both vectors and embedded images. The private region-level routing plan sends vector candidates and non-overlapping images to separate benchmark routes. `vector-geometry-benchmark` identifies structured-extraction candidates, while `visual-model-benchmark` identifies PaddleOCR-VL or another benchmark-approved fallback. Every route still requires schema validation and teacher review.

The visual route renders only the routed source region as a private crop; it never exports a complete PDF page or source document. Visual-model output is accepted only through strict JSON table/chart schemas. HTML, free Markdown, and direct UI rendering are rejected; every draft must match its source checksum, page, and bbox.

If a model returns table markup, the private adapter parses it only as data and moves td/th text into the strict JSON cell schema. Model HTML is never sent to a browser or student API. Non-table, malformed, or unclosed markup is rejected.

The P46 visual-table run proves only that the formatting/schema path works; one sample never approves a model. A private `visual-table-gold-v1` manifest holds the source region (`region_id`, checksum, page and bbox) and human-verified cells. Metrics are not calculated unless draft and Gold sources match exactly. Fewer than three Gold table samples automatically produce `blocked_insufficient_gold_samples`; with enough samples, every cell, role and text must match exactly before a candidate can be approved for production use. A successful benchmark never removes teacher review.
