# ADR 0012: Vektör + native metin tablo taslağı / Vector + native-text table draft

Durum: Kabul edildi.

P40/P46 private benchmark'ında PDF vektör çizgileri ve native metin katmanı bulunurken görsel adaylar arasında büyük doğruluk farkı görüldü. Bu durumda öğrenciye model çıktısı yayımlamak veya öğretmene tüm hücreleri elle girmek yerine, önceden seçilmiş checksum bağlı bölgede çizgi eksenlerinden hücre geometrisi çıkarılır ve kelime merkezi tek bir hücreye düştüğünde native metin bağlanır.

Birleştirilmiş hücre, satır/kolon span'i, semantik başlık ve erişilebilir açıklama çıkarıcı tarafından yorumlanmaz. Taslaklar düşük güvenlidir; Gold doğrulaması ve öğretmen denetimi zorunludur. Vektör/nativemetin eksikse sistem görsel benchmark veya denetim rotasına geri döner.

Status: Accepted.

In the P40/P46 private benchmark, PDF vector lines and the native text layer exist while visual candidates show large accuracy differences. Rather than publishing a model output or asking a teacher to enter every cell, the system extracts cell geometry from line axes in preselected checksum-bound regions and binds native text only when a word centre falls in exactly one cell.

The extractor does not interpret merged cells, row/column spans, semantic headers, or accessible explanations. Drafts are low confidence; Gold validation and teacher review remain mandatory. When vector/native text is insufficient, the system returns to visual benchmark or review routing.
