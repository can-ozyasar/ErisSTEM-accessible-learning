# AYT Tarih kaynak bulma: mevcut durum ve düzeltme sırası

Bu not, kaynak bulma sonuçlarını model başarısı gibi göstermemek için tutulur.
İncelenen veri private alandadır; bu dosyada soru metni, cevap anahtarı ve PDF
alıntısı bulunmaz.

## Doğrulanmış bulgular

- Üç kitapta toplam 1.920 aday metin parçası vardır: 10. sınıf 427, 11. sınıf
  744 ve 12. sınıf 749.
- İlk otomatik AYT kuyruğu yalnız `review_for_approval` ve uyarısız 424 parçayı
  aramıştır. Bu, toplamın yaklaşık yüzde 22'sidir. `manual_review`, metnin
  değersiz olduğu anlamına gelmez; PDF bağlamının kontrol edilmesi gerektiğini
  ifade eder.
- Genişletilmiş keşif turu 1.920 parçanın tamamını yalnız private inceleme
  amacıyla aramıştır. Her soru için altı kart üretilmiştir. Bu turda ilk Gold
  incelemesinde çekimser kalan 107 sorudan 7'si için yeni doğrudan kanıt
  bulunmuştur.
- Bu yedi soruda top-3 Recall 0,8571, MRR@3 0,8333 ve p95 39,4 ms'tir. Bu
  metrikler yalnız bulunan kanıtı sıralama kalitesini anlatır; tüm kitap
  kapsamasını veya öğrenci yanıt kalitesini anlatmaz.
- BGE-M3 ile daha önce yapılan beş vakalık smoke deneyi yapay veridir. Ürün
  kararı, Türkçe AYT kanıt getirmesi veya semantik arama başarısı olarak
  kullanılamaz.

## Buradan çıkarılamayacak sonuçlar

Kalan çekimser vakalar için `kitapta bilgi yoktur`, `BM25 başarısızdır` veya
`doğrudan kanıt eşiği fazla katıdır` sonucu henüz çıkarılamaz. Altı adaylık
inceleme penceresi aşağıdaki durumları birbirinden ayıramaz:

1. Bilgi seçilen 10--12. sınıf kitaplarında gerçekten yoktur.
2. Birincil bilgi ile kişi--olay, tarih--olay ya da neden--sonuç ilişkisi iki
   ayrı parçada yer alıyordur.
3. Bilgi paragraf, sayfa veya başlık sınırında bölünmüştür.
4. Soru ile kitap aynı bilgiyi farklı sözcüklerle anlatıyordur.
5. OCR ya da PDF bloklama, adayın aranabilir metnini zayıflatmıştır.
6. Getirici doğru kaynağı ilk altı adayın altına itmiştir.

## Ürün ilkesi

Öğrenciye giden kanıt için eşik düşürülmez. Bir metnin soru sözcüklerine
benzemesi, tarihsel iddiayı desteklediğini göstermez. Buna karşılık bu katı
eşik, *keşif* indeksini daraltmak için kullanılmaz:

- `review_for_approval`: öncelikli keşif adayıdır.
- `manual_review`: private keşif adayıdır; PDF kesiti ve inceleme olmadan
  kanıt, runtime RAG veya QLoRA verisi olamaz.
- `do_not_use`: görsel açıklaması, etkinlik yönergesi veya edebî alıntı gibi
  yüksek güvenli kaynak dışı biçimlerdir; normal aramaya alınmaz.

## Kontrollü sonraki deney

İlk turda çekimser kalan sorulardan ünite başına dengeli bir kalibrasyon örneği
seçilir. Her soru için cevap anahtarı kullanılmadan şu bağımsız aday listeleri
üretilir:

1. soru kökü ve şıklarla BM25,
2. kişi, yer, tarih/dönem ve olay ipuçlarıyla yapılandırılmış BM25,
3. başlık ve komşu paragraf bağlamıyla kanıt pencereleri,
4. aynı corpus üzerinde BGE-M3 dense ve sparse arama,
5. yalnız geliştirme kümesinde RRF ve gerekiyorsa reranker.

Tarih öğretmeni ajanı PDF kesitinden her soruya tek bir teşhis etiketi verir:
`retrieval_miss`, `multi_atom_required`, `corpus_gap`,
`ocr_or_segmentation` veya `indirect_only`. Aynı ajan, doğrudan destekleyen
parçaları ayrıca işaretler. Bu etiketler olmadan hangi bileşenin değiştirileceği
varsayımla seçilmez.

Dense, sparse ve multi-vector seçeneklerini tek modelde sunabilen BGE-M3,
parafraz ve terim farkı için uygun ilk adaydır; yine de kabul, yalnız bu
kalibrasyon kümesinde ölçülen faydaya bağlıdır. Ayrıntı için
[BGE-M3 belgeleri](https://bge-model.com/bge/bge_m3) ve
[BGE-M3 makalesi](https://arxiv.org/abs/2402.03216) kullanılacaktır.
