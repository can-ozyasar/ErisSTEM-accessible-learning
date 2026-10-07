# ADR 0015: Kaynak bağlı tablo öğretmen denetimi / source-bound table review

Durum: Kabul edildi.

Vektör/native tablo çıkarımı yalnız aday üretir. Öğretmenin ham OCR, model
işaretlemesi veya LaTeX görmesi hem hata ayıklama yükünü öğretmene taşır hem de
sunum güvenliğini zayıflatır. Bu nedenle öğretmen kuyruğu yalnız
`candidate-vector-native-needs-gold-and-review` durumundaki kaynak checksum'ı,
sayfa ve bbox ile bağlı taslakları kabul eder. Tarayıcıya yalnız sade hücre
metni, sayfa önizlemesi ve turuncu kaynak vurgusu gönderilir; güven skoru,
checksum, extractor/metin işaretlemesi gönderilmez.

Öğretmen hücreleri onaylar veya düzeltir; yapı değişikliği yapamaz. İkinci rol
tarafından ayrı bir yayın çağrısı yapılmadıkça öğrenci API'si tabloyu döndürmez.
Her içe alma, onay, düzeltme ve yayın denetim günlüğüne yazılır.

Status: Accepted.

Vector/native extraction produces candidates only. Showing a teacher raw OCR,
model markup, or LaTeX shifts debugging work to the teacher and weakens safe
presentation. The teacher queue therefore accepts only
`candidate-vector-native-needs-gold-and-review` drafts bound to a source
checksum, page, and bbox. The browser gets only plain cell text, a page preview,
and an orange source highlight; it does not get confidence, checksum, or
extractor/markup material.

The teacher can approve or correct cells but cannot alter table structure. The
student API returns nothing until a separate reviewer publishing action occurs.
Every import, approval, correction, and publication is written to the audit log.
