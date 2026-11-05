# AYT ek kaynak kapsama deneyi

## Karar

MEBİ AYT Tarih konu özetleri, ana ders kitabının yerine geçirilmedi. Önceki
derin incelemede `candidate_set_insufficient` kalan 23 cevap içermeyen soru
üzerinde ayrı bir kapsama deneyi için `supplementary_candidate` olarak
indekslendi.

Bu ayrım, çözümlü deneme ve tarama kitaplarının cevap veya çözüm bilgisini
öğrenci RAG'ına karıştırmamak içindir. Bu belgeler soru havuzu kapsamı ve
değerlendirme için saklanır; öğrenciye kanıt kaynağı değildir.

## Kaynak ve korumalar

- Kaynak: MEBİ AYT Konu Özetleri Tarih, 244 PDF sayfası.
- İndeks: 73 içerik başlığı ve 287 kısa aday parça.
- Kaynak checksum'ı ve indeks checksum'ı private corpus içinde tutulur.
- Aday parçaların `student_runtime_eligible` ve `qlora_eligible` alanları
  başlangıçta `false` değerindedir.
- PDF kesiti ve öğretmen onayı olmadan hiçbir aday runtime kanıt demetine veya
  QLoRA satırına aktarılamaz.

## Teknik düzeltme

Bu PDF'nin basılı konu sayfaları, fiziksel PDF sayfalarından iki sayfa
geridedir. İndeksleyici sabit ofset kullanmaz: ilk gerçek başlığı PDF'de
bulur, sayfa farkını hesaplar ve tüm konu başlangıçlarını buna göre eşler.
Bu kontrol, içindekiler sayfasının yanlışlıkla kanıt olarak indekslenmesini
engeller. Düzensiz kaynaklarda düz, numaralı konu özeti tablosu ancak en az
on başlıkla görülürse kabul edilir; tekil "ünite ölçme" satırları yeni bölüm
tipi sayılmaz.

## Açık deney

Kaggle private koşusu `Eristem Ayt Supplementary Coverage V2` yalnız 23
önceki kanıt boşluğunu ve 287 özet adayını kullanır. BM25 ve seçili
Qwen3-Embedding-4B İngilizce instruction yolu karşılaştırılır. Çıktı,
yalnız aday sıralaması ve gecikme içerir; cevap anahtarı, ham PDF ve çözüm
metni içermez.

Bir kaynağın işe yaradığı, ancak PDF kesiti üzerinden yapılan sonraki tarih
öğretmeni incelemesiyle anlaşılır. Bu nedenle koşu sonucu tek başına ürün
kabulü değildir.
