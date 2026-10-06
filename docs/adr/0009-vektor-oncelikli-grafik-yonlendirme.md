# ADR 0009: Grafik/tablo için vektör kanıtı, VLM fallback'ten önce / Vector evidence before VLM fallback

Durum: Kabul edildi.

PaddleOCR-VL benchmark'ında `table-p51` görüntü/metin blokları, `chart-p91` ise tablo/görüntü blokları olarak bulundu; bu etiketler semantik tablo veya grafik doğruluğu kanıtlamaz. PDF'de çizim komutları veya gömülü görüntüler bulunabilir. Bu nedenle grafik/tablo VLM'ye doğrudan gönderilmez: önce PyMuPDF ile çizim ve gömülü görüntü bölgeleri, kaynak checksum'ı ve koordinatları çıkarılır. Vektör geometri varsa yapılandırılmış çıkarıcı benchmark'a aday olur; yalnız gömülü görüntü varsa görsel model fallback'i gerekir. Hiçbir yol, doğrulanmamış geometriden ders gerçeği üretmez.

Bu envanter semantik grafik/tablo ayrıştırıcısı veya yayın motoru değildir. Yalnız yönlendirme kanıtı üretir. VLM/çıkarıcı sonucu şema, kaynak koordinatı, güven sinyali ve Gold ölçümü olmadan öğrenciye yayımlanmaz. Qwen3-VL 4B QLoRA ancak vektör ve benchmark-adayı çıkarıcılar önceden kaydedilmiş Gold eşiklerini geçemezse değerlendirilir.

Status: Accepted.

In the PaddleOCR-VL benchmark, `table-p51` appeared as image/text blocks and `chart-p91` as table/image blocks; neither label proves semantic table or chart correctness. A PDF can contain drawing commands or embedded images. Therefore a chart/table is not sent directly to a VLM: PyMuPDF first inventories drawing and embedded-image regions with source checksum and coordinates. When vector geometry exists, a structured extractor becomes a benchmark candidate; when only embedded images exist, visual-model fallback is required. Neither route invents educational facts from unverified geometry.

This inventory is not a semantic chart/table parser or publication engine. It supplies routing evidence only. No VLM/extractor output is published to students without schema validation, source coordinates, confidence signals, and Gold measurement. Qwen3-VL 4B QLoRA is considered only after vector and benchmark-candidate extractors miss recorded Gold gates.
