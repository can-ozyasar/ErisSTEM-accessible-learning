# ADR 0003: PDF metin katmanı, kontrollü worker'ın ilk yolu / Text layer first

Durum: Kabul edildi.

Yerel ve yetkili MEB PDF kaynakları `data/meb/` altında tutulabilir; bu yol ve ondan türetilen çıktılar Git'e girmez. İlk worker, PDF magic-byte, boyut, izinli kök dizin, şifreleme ve sayfa sınırlarını doğrular. PyMuPDF ile yalnız metin katmanı blokları ve kaynak koordinatları çıkarılır.

Metin katmanı boşsa worker bilgi uydurmaz ve OCR sonucu üretmez. Sonraki iş, Docling/PaddleOCR-VL benchmark kararına bağlı fallback kuyruğudur. Üretimde bu komut, ağ erişimi kapalı ve CPU/RAM/zaman limiti olan ayrı bir container içinde çalıştırılacaktır.

Status: Accepted.

Authorised local MEB PDFs may live under `data/meb/`; that path and all derived output stay out of Git. The first worker validates magic bytes, size, the allow-listed root, encryption, and page count. It extracts only text-layer blocks and source coordinates through PyMuPDF.

If a text layer is empty, the worker does not invent information or run OCR. A future fallback queue depends on the Docling/PaddleOCR-VL benchmark. In production this command must run in a separate network-disabled container with CPU, memory, and time limits.
