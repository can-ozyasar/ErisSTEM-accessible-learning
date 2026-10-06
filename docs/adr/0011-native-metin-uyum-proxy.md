# ADR 0011: Native metin uyumu Gold değildir / Native-text agreement is not Gold

Durum: Kabul edildi.

Görsel tablo modeli, aynı PDF'nin native metin katmanıyla token bazında karşılaştırılabilir. Bu, model ve kaynak arasında eksik/fazla metin sinyali verir ve insan Gold kontrolünün kapsamını daraltır. Ancak PDF metin katmanı da hatalı veya eksik olabileceği, token uyumu hücre yapısını kanıtlamadığı ve iki kaynak aynı hatayı paylaşabileceği için bu sonuç Gold doğruluğu değildir.

Bu nedenle native uyum raporu yalnız private, içeriksiz bir yönlendirme sinyali üretir. Yüksek uyum adayın yayınlanmasına, model seçimine veya öğretmen denetiminin atlanmasına izin vermez. Kaynak checksum, sayfa ve bbox uyuşmazlığı koşumu engeller.

Status: Accepted.

A visual-table model can be compared token by token with the same PDF's native text layer. This yields missing/extra-text signals between model and source and narrows the scope of human Gold checks. However, the PDF text layer can itself be incomplete or wrong, token agreement does not prove cell structure, and both sources can share an error; the result is therefore not Gold accuracy.

The native-agreement report consequently produces a private, content-free routing signal only. High agreement never permits publication, model selection, or bypassing teacher review. A source checksum, page, or bbox mismatch blocks the run.
