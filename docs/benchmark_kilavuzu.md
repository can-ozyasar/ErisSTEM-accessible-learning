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

Real MEB PDFs and Gold annotations never enter Git. A private manifest holds `page`, `kind`, and human-verified `expected` values. Empty annotations block measurement; unavailable model packages are recorded as unavailable rather than treated as results.

Chart/table candidate pages first pass through the private vector/embedded-image inventory. Its output is routing evidence with source coordinates, not table or chart data. `vector-geometry-available` routes to a vector-based extractor benchmark; `embedded-image-needs-visual-extraction` routes to a visual-model benchmark.

When vector geometry is available, the next candidate extracts only grid/axis regions without producing semantic results. `rectilinear-grid-candidate` and `perpendicular-axis-candidate` are source-linked comparison regions, not publishable tables or charts. Cell relationships and chart values require separate schema validation.

For grid candidates, cell geometry can be extracted before reading any cell values. These cells remain `requires-schema-validation-and-review`: they contain no header/data/merge interpretation and no student-visible value.

A native PDF text block is bound to a private grid draft only when its centre is in exactly one cell and at least 80% of the block lies within that cell. Ambiguous or spanning text is never split; it remains `unbound-needs-fallback-or-review`. This layer does not generate OCR or LLM output.

Unless at least 50% of a grid's cells are safely bound, its route cannot become `candidate-table-schema-validation`; it remains `insufficient-bound-text-needs-chart-or-visual-route`. This is a routing safeguard, not a publication threshold.

A page can contain both vectors and embedded images. The private region-level routing plan sends vector candidates and non-overlapping images to separate benchmark routes. `vector-geometry-benchmark` identifies structured-extraction candidates, while `visual-model-benchmark` identifies PaddleOCR-VL or another benchmark-approved fallback. Every route still requires schema validation and teacher review.

The visual route renders only the routed source region as a private crop; it never exports a complete PDF page or source document. Visual-model output is accepted only through strict JSON table/chart schemas. HTML, free Markdown, and direct UI rendering are rejected; every draft must match its source checksum, page, and bbox.
