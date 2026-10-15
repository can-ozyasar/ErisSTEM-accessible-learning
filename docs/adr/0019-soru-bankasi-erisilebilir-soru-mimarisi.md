# Soru bankasında soru-merkezli erişim

## Gezinme sözleşmesi

Ekran okuyucu ve seslendirme sırayla şu ayrı odak noktalarını sunar: `Soru 5`,
`Soru metni`, varsa `Görsel/harita`, varsa `I., II., III. önermeler`, `Soru kökü`,
`Şık A` ... `Şık E`. Kullanıcı herhangi bir noktaya atlayıp yalnız o bölümü tekrar
dinleyebilir; sayfa başından yeniden okuma zorunlu değildir. Görselin açıklaması
şıkların içine veya soru köküne karıştırılmaz. Şık metinleri kendi kaynak kutularına
ve harflerine bağlıdır.

Boşluklar kaynak metindeki konumunu korur ve onaylandıktan sonra `1. boşluk`,
`2. boşluk` olarak okunur. Üç noktanın her zaman boşluk olduğu varsayılmaz;
yalnız kaynakta işaretli ve öğretmen tarafından doğrulanmış boşluklar bu okunuşu alır.
Yanıt anahtarı kaynaktan veya yetkili öğretmenden gelmedikçe doğru cevap tahmin edilmez.

## Çıkarma ve doğrulama hattı

1. PDF metin katmanı, karakter/satır koordinatları, görsel kutuları ve sayfa görüntüsü
   birlikte alınır. Soru numarası, iki sütun ve soru sınırları sayfa düzeyinde bulunur.
2. Bölge modeli soru kökü, uzun ön metin, Roma rakamlı önermeler, seçenekler, tablo,
   resim, harita ve alt yazıyı ayırır. A–E harfleri ve soru numarası yalnız başlık değil,
   yapısal bağdır. Sayfa aşan soru tespiti henüz uygulanmadı; böyle bir durum
   görüldüğünde öğretmen denetiminde kaynak bütünlüğü kontrol edilmelidir.
3. PDF metin katmanı bozuk veya tarama ise yalnız sorunlu bölgede OCR/düzen modeli
   denenir. PaddleOCR PP-StructureV3 ve Docling adaydır; seçim, bu soru bankasından
   etiketlenmiş sayfalardaki karşılaştırmalı sonuçla yapılır. Model çıktısı doğrudan
   doğru kabul edilmez.
4. Harita betimlemesinde başlık/lejand, yön ve konum ilişkileri, işaretler, renklerin
   anlamı ve soruyla ilgili gözlemlenebilir bilgi ayrı yazılır. Görsel önerisi bir
   uzman tarafından doğrulanmadan öğrenciye açıklama olarak yayımlanmaz. Betimleme
   cevap şıkkını ele vermemelidir.
5. Yapısal kontroller: seçenek harfleri eksiksiz ve tekil mi; soru sınırı komşu
   soruya taşıyor mu; görsel doğru soruya bağlı mı; boşluk sayısı ve okuma sırası
   tutarlı mı; kaynak kutuları sayfa içinde mi. Hatalı soru öğrenciye açılmaz.
6. Denetim, bütün sorulara aynı eşik uygulamaz. Görselli, çok sütunlu, boşluklu,
   seçenekleri yatay dizilmiş ve sayfa aşan sorular ayrı hata sınıflarıdır.

## Ölçülecek kabul ölçütleri

Altın örneklerde soru sınırı, kök, her şık, boşluk sayısı, görsel-soru ilişkisi ve
okuma sırası ayrı ayrı ölçülür. Ölçüt, öğretmenin bir soruyu sıfırdan yeniden yazması
gerekmeyecek bir düzeye gelmesidir; sayı ancak gerçek PDF ve etiketli örnekler geldikten
sonra belirlenir. Altın örnekler bu ekranda gösterilen 1–10. sorularla başlayıp farklı
sayfa düzenlerinden rastgele seçilen örneklerle genişletilir.

## Uygulanan temel

`question_bank_structure.py` ayrı soru bileşenlerini, kaynağa bağlı kutuları,
numaralı boşlukları ve görsel betimleme onayını doğrular. Onaylı görselli soruda
denetlenmiş betimleme yoksa yayın reddedilir. OCR başarısı yalnız gerçek
kaynakta ayrıca ölçülür; bu kitapta önce yerel PDF metin katmanı kullanıldı.

## 13 Ekim 2026: gerçek PDF pilotu

Kullanıcı `data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf` dosyasını sağladı.
Dosya 58 PDF sayfası, SHA-256:
`532d9372bd6c1804cd6efc23d5f6eae0b94befa1131ad11961fa1e723c1dd5da`.
Yerel metin katmanı üzerinde 306 soru adayı bulundu: 282 çoktan seçmeli,
20 açık uçlu, 2 doğru-yanlış, 2 boşluk doldurma. Bunlar yayın sayısı değildir.
İlk yapısal taramada 252 aday uyarısız; görsel, boşluk, yatay seçenek hücresi,
PDF kontrol karakteri veya farklı soru türü nedeniyle kalan adaylar ayrıca
inceleme istiyor. Aynı soruda birden fazla uyarı olabilir.

29. PDF sayfasındaki harita sorusunda seçenekler I–II–III sütunlarıyla,
46. sayfadaki iki görsel ise soldan sağa I–II olarak ilişkilendirildi.
Öğrenciye yalnız öğretmen onayından geçmiş sorular sunulur. Öğretmen tek soruyu
düzeltebilir veya bütün sayfayı inceleyip yalnız uyarısız soruları topluca
onaylayabilir. Yerel test ortamı bu akışın yetki ve yayın sınırını sınar.

PDF'nin telif sayfası elektronik çoğaltma/yayına ilişkin kısıt belirtir.
Kaynak ve türevleri Git dışında, localhost'a bağlı geliştirme ortamında tutulur;
üretim erişimi gerçek kimlik doğrulama ve kullanım hakkı kararı olmadan kapalıdır.

Görsel betimlemeleri, cevap anahtarı ve pedagojik açıklama henüz otomatik
onaylanmaz. Mevcut makinede GPU yoktur ve disk alanı sınırlıdır; yeni yerel
çok kipli modelin indirilmesi/yüklenmesi bu pilotta yapılmamıştır.

Sekiz görselli sorunun dokuz ayrı görseline bu PDF'nin SHA-256 kimliğine bağlı
betimleme taslakları eklendi. Bunlar yalnız öğretmen editöründe öneri olarak
görünür; harita konumları ve karşılaştırma tablosunun sayıları dâhil her ayrıntı
kaynakla doğrulanmadan `description_reviewed` işaretlenemez. Görseli kayıttan
silerek onayı atlama sunucuda reddedilir.
