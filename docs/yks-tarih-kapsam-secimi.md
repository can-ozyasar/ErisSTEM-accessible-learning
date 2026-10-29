# YKS Tarih kapsam seçimi

İlk üretim sürümü tek sınıf ve altı üniteyle sınırlıdır. Sınıf seçimi, 2022–2026 resmî ÖSYM TYT/AYT kitapçıklarının **yerel ve öğretmen onaylı metadata etiketleriyle** yapılır. Soru metni, şık, cevap anahtarı ve PDF bu işlemde saklanmaz ya da Kaggle'a aktarılmaz.

Her metadata kaydı yalnız soru kimliği, yıl, test, soru numarası, sınıf, ünite, kavram, ilişki türü, görsel bağımlılığı, MEB'de doğrudan kanıtlanabilirlik, erişilebilirlik ve inceleme durumunu içerir.

Puanlama sabittir: soru sıklığı %40, doğrudan MEB kanıtı %25, ilişki grafiği değeri %20 ve erişilebilirlik %15. En yüksek sınıfın en yüksek puanlı altı ünitesi seçilir. Seçim, ilgili MEB kitabı yerelde sürümlenebiliyor ve 120 yasal/onaylı soru havuzu sağlanabiliyorsa geçerlidir; aksi durumda sıradaki sınıf değerlendirilir.

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.yks_history_scope \
  --input data/private/yks-history-metadata-v1.json \
  --output data/private/yks-history-scope-report-v1.json
```

Girdi `yks-history-metadata-v1` şemasını kullanır. Komut ham soru metni veya cevap anahtarı alanı görürse başarısız olur.

## AYT Tarih-2 kaynak hazırlığı — 29 Ekim 2026

AYT Tarih-2 için sınıf seçimi kararı henüz verilmedi. Bunun yerine adayların
hangi sınıf kitabında kanıt bulabildiğini ölçmek üzere 10, 11 ve 12. sınıf
MEB ders kitaplarından private, checksum bağlı bir **inceleme corpus'u**
oluşturuldu. 12. sınıf kaynağı, PDF içindeki başlık ve yayın künyesiyle
`T.C. İnkılap Tarihi ve Atatürkçülük 12. Sınıf Ders Kitabı`, MEB Yayınları
olarak doğrulandı. 2026 baskısı kanonik kaynak oldu; aynı kitabın 2022
baskısı farklı checksum taşıdığı için kanonik corpus'a karıştırılmadı.

| Kitap | Bölüm | İnceleme adayı parça |
|---|---:|---:|
| Tarih 10 | 14 | 427 |
| Tarih 11 | 11 | 744 |
| T.C. İnkılap Tarihi ve Atatürkçülük 12 | 32 | 749 |

Corpus oluşturucusu, PDF içindekilerinde satır kırılması, ayrı metin
bloklarındaki sayfa numaraları ve farklı blok sıraları için sayfa-geometrisi
onarımı uygular. Bölüm sonundaki ölçme ve değerlendirme sayfaları aday
havuzuna alınmaz. Bu onarım yalnız kaynak koordinatı çıkarır; tarihsel iddia
üretmez ve parça onayı vermez.

Resmî AYT Sözel derlemesinden 48 soru adayı yalnız private alanda çıkarıldı.
Yakındaki yıl etiketiyle güvenilir biçimde bağlanan 15 aday için, üç MEB
kitabı üzerinde sekizer kanıt önerisi üretildi. Yılı henüz bağlanamayan 33
aday otomatik olarak engellendi. Öneri sonucu `teacher_review_required`
olup öğrenci RAG'ına, QLoRA dışa aktarımına veya çalışma zamanı indeksine
aktarılmaz. Her öneri kaynak kitap checksum'ı, sayfa ve koordinat taşır;
PDF kırpımı ve öğretmen onayı olmadan kullanılamaz.

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.build_multi_history_rag \
  --grade10 data/meb/tarih-10sinif-ders-kitabi_20261013.pdf \
  --grade11 data/meb/tarih-11sinif-ders-kitabi_20260908.pdf \
  --grade12 data/meb/inkilap-12-aday-eba.pdf \
  --output data/private/yks-ayt-source-v1/multi-history-rag-v2.json

PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.ayt_evidence_match \
  --questions data/private/yks-ayt-source-v1/ayt-tarih2-candidates-v1.json \
  --corpus data/private/yks-ayt-source-v1/multi-history-rag-v2.json \
  --output data/private/yks-ayt-source-v1/ayt-evidence-proposals-v1.json
```
