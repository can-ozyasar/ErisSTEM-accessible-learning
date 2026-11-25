# AYT Tarih aday kaynak doğrulama durumu

Bu rapor, yayıma kapalı 120 özgün AYT Tarih adayının kaynak izi için teknik
durum kaydıdır. Öğretmen onayı, kullanıcı testi veya öğrenciye açılma iddiası
değildir.

| Kontrol | Sonuç |
| --- | ---: |
| Yerel MEB PDF checksum ve sayfa/bbox sınırı | 120 / 120 geçti |
| Birebir PDF metin-katmanı alıntı eşleşmesi | 79 / 120 |
| Yakın metin eşleşmesi (`>= 0.90`) | 34 / 120 |
| Düşük benzerlikli maddi uyuşmazlık adayı | 7 / 120 |
| Bu 7 kayıt için sınırlı kırpımda görsel ikinci görüş `quote_visible` | 7 / 7 |
| Runtime / QLoRA için etkinleştirilen aday | 0 / 120 |

## Yorum

79 aday için PDF'nin metin katmanında alıntı doğrudan bulundu. Kalan 41 aday
otomatik kabul edilmedi. 34 yakın eşleşme PDF biçimlendirme, noktalama veya
Unicode farkı adayıdır. Diğer 7 adayda yerel metin katmanı eşleşmesi yokken,
yalnız ilgili sayfa bağlam kırpımıyla yapılan ayrı görsel AI denetimi alıntının
görünür olduğunu bildirdi.

Bu ikincil sonuç, PDF metin-katmanı çıkarımının eksik olabileceğine dair bir
tanıdır; ne kaynak kanıtını değiştirebilir ne de insan PDF kırpımı incelemesi
yerine geçebilir. Özellikle modele soru ve alıntı da verildiğinden, görsel
sonuç tek başına doğrulama sayılmaz.

## İzlenebilir girdiler

- Aday paketi: `data/private/ayt-history-exam/original-question-candidate-pack-v2.json`
- Deterministik denetim: `candidate-pdf-crop-text-audit-v5.json`
- Yerel onarım kuyruğu: `crop-repair-review-v1/manifest.json`
- Görsel ikinci görüş: `deepseek-crop-visual-review-v1.json`

Bu dosyalar yerel/özel kalır. Görsel çağrıda tam kitap PDF'si, öğrenci verisi
ve iddia edilen doğru cevap etiketi gönderilmemiştir; yalnız seçilmiş bağlam
kırpımı ile özgün soru/şık ve aday alıntısı kullanılmıştır.

## Yayın kapısı

Paket hâlâ yayımlanamaz. Her aday için soru-şık eşdeğerliği, doğru cevabın
kaynakla gerekçesi, açıklama, sesletim ve metinle çözülebilirlik ayrı
incelemeyle tamamlanmalı; çalışma zamanı manifestinde yalnız
`human_pdf_crop_review` izli kayıtlar yer almalıdır.
