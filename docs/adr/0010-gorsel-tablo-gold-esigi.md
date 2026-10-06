# ADR 0010: Görsel tablo için kaynak bağlı Gold eşiği / Source-bound Gold gate for visual tables

Durum: Kabul edildi.

P46 deneyi PaddleOCR-VL'nin bir tablo işaretlemesini sıkı şemaya dönüştürebildiğini gösterir; bu, hücrelerin doğru okunduğu veya adayın üretime uygun olduğu anlamına gelmez. Görsel tablo adayları, private `visual-table-gold-v1` referansındaki bölge kimliği, kaynak checksum'ı, sayfa ve bbox ile birebir eşleşmek zorundadır. Ardından hücre koordinatları, rolü ve normalize edilmiş metni tam eşleşmelidir. Tek bir doğru örnek model seçimi için istatistiksel kanıt değildir; üçten az Gold tablo örneği `blocked_insufficient_gold_samples` sonucunu üretir.

Bu ölçüm yalnız model/adaptör seçimi içindir. Başarılı benchmark öğrenci yayını yapmaz ve öğretmen denetimini kaldırmaz. Gold referansları ile MEB'den türetilmiş model taslakları private kalır; repoda yalnız şema, metrik kodu ve sentetik testler bulunur.

Status: Accepted.

The P46 run shows that PaddleOCR-VL can turn one table markup into the strict schema; it does not prove correct cell extraction or production fitness. Visual-table candidates must exactly match the private `visual-table-gold-v1` reference's region identifier, source checksum, page and bbox. Their cell coordinates, roles and normalized text must then match exactly. One correct sample is not evidence for model selection; fewer than three Gold table samples yield `blocked_insufficient_gold_samples`.

This measurement selects a model/adapter only. A successful benchmark neither publishes to students nor removes teacher oversight. Gold references and MEB-derived model drafts remain private; the repository contains only schemas, metric code and synthetic tests.
