# Kaynak Bağlı AYT Veri Tamamlama Hattı

Bu hat, eksik kanıt kapsamasını rastgele soru ya da cevap anahtarıyla
tamamlamaz. Girdi yalnız onaylı bilgi grafiği düğümleri, kaynak koordinatlı
alıntılar ve onaylı ilişki kenarlarıdır.

## Soru kapsamı

Bu AYT metin koçluğu sürümünde harita, tablo, fotoğraf, resim, grafik, şema
veya başka görsel veri içeren sorular kullanılmaz. Bu kayıtlar kaynak
PDF'den çıkarılsa bile ayrı `out_of_scope_visual_question` listesine alınır;
öğrenci koçluğu, QLoRA eğitim/geliştirme/test satırları ve kalite oranlarının
paydasına girmez. Bir tarih sorusunun metninde “resim sanatı” veya “bu şekilde”
geçmesi tek başına sorunun görsel veri içerdiği anlamına gelmez. PDF kesiti
belirsizse soru otomatik kabul edilmez; görsel inceleme kuyruğunda kalır.
Bu ürün kapsamı kararı, sınav
muafiyeti hakkında genel bir hukuki iddia değildir. [2026-YKS sıkça sorulan
sorular, 68. soru](https://shgal.meb.k12.tr/meb_iys_dosyalar/58/01/965140/dosyalar/2026_03/69aa85bacc372219364007_2026_YKS_SIK%C3%87A_SORULAN_SORULAR.pdf?CHK=9e05ae56367f90deebc7de49a006b18c)
görsel veri içeren soruların **okuyucu yardımı talep eden görme engelli
adaylara** sorulmadığını belirtiyor; bu koşul bütün engelli adaylara
genellenmez.

## Akış

1. `QuestionAnalyzerAndEliminator`, soru kökündeki olumsuzluk, kronoloji ve
   yorum gereksinimini saptar. Doğrudan destek zayıfsa şık seçmek yerine
   açık çelişkileri eleyerek ilerler.
2. `HistoryTeacherValidatorAgent`, tek atomlu doğrudan desteği veya en çok
   üç atomdan oluşan, aynı şık zincirinde bağlı sınırlı çıkarımı önerir.
   Bu sonuç araştırma adayıdır; insan öğretmen onayı değildir.
3. `GraphToQuestionGenerator`, yalnız kaynak checksum'ı, sayfası,
   koordinatı ve alıntısı bulunan onaylı ilişki kenarlarından private soru
   taslağı üretir. Taslağın cevap etiketi `QuestionItem` çalışma zamanı
   şemasına aktarılmaz.
4. `ConceptBasedDataSplitter`, ortak kişi, olay, yer, dönem, kavram ya da
   ilişki taşıyan kayıtları transitif olarak aynı veri bölümünde tutar.
   Böylece eğitim, geliştirme ve kapalı test arasında kavram sızıntısı
   önlenir.

`export_autonomous_graph_qlora.py`, bu dört adımı private bir graf üzerinde
çalıştırır ve yalnız yerel inceleme kuyruğu üretir. Bu otomatik koçluk
taslakları Kaggle'a yazılmaz. Yalnız altı turu onaylanmış soru gruplarını
`export_tutor_qlora.py` train/dev olarak Kaggle'a aktarır; kapalı test yerelde
kalır.

Üretim hattı `AccessibilityAndScopeFilter` ile görsel bağımlılığını hem soru
kökünde hem şıklarda denetler; hedef bölüm/sayfa aralığı dışındaki soruları
reddeder. I/II/III öncüllü, boşluk doldurmalı ve tarih/yüzyıl odaklı metin
soruları beyaz listededir; bu biçim etiketleri tek başına dışlama nedeni
değildir. Soru havuzu sonuna kadar taranır; her reddedilen adayın nedeni
sayılır. Kaynak havuzu hedef 120 gruba yetmezse işlem sonsuz döngüye girmez ve
eksik sayıyı raporlar; eksik havuzdan Kaggle eğitim dosyası üretilmez.

`QuestionAnalyzerAndValidator`, kapsam filtresi geçtikten sonra soru türü
analizini, açık şık elemesini ve onaylı graf üzerinden doğrudan/sınırlı kanıt
denetimini tek bir izlenebilir sonuçta birleştirir. Bu programatik kararlar
öğretmen ajanı için aday niteliğindedir; tek başına pedagojik veya QLoRA
onayı sayılmaz.

Hedef kapsam v4, 12. sınıf kitabı yanında AYT konu özetindeki aynı altı üniteyi
de kaynak olarak bağlar. Özet başlıklarının 12. sınıf ünitelerine eşlemesi
açıkça tutulur; her kaynak kendi PDF checksum'ı ve sayfa aralığıyla filtrelenir.
Bu, genel tarih özeti bölümlerini yanlışlıkla AYT hedef kaynağına katmaz.

8 Kasım 2026 üretim adayı koşusu, iki kaynakta 46 soru taslağını taradı; 18
taslak mekanik kalite ve kaynak denetimini geçti. 102 grup eksik olduğu için
Kaggle'a eğitim verisi yazılmadı. Özet kaynağının eklenmesi 12'den 18'e aday
geçişi sağladı, ancak 120 hedefini karşılamadı. Ayrıntılı, içerik taşımayan
koşu özeti private `ayt-graph-candidate-production-run-v1.json` dosyasında.

Graf kenarının kaynakta bulunması tek başına yeterli değildir.
`GeneratedDraftQualityGate`, split'ten önce konuşulabilir soru kökünü
doğrular: satır sonu OCR bölünmesi, kırpılmış tarih, cümle boyunda düğüm,
bozuk beşli şık ve eksik dil bilgisi olan taslakları reddeder. PDF'deki
`ilişki- lerinde` türü satır sonları yalnız konuşma metninde deterministik
olarak birleştirilir; checksum, sayfa ve koordinat korunur ve çıkarma yöntemi
normalizasyonu belirtir. Aynı cümlede geçen her olay-yıl çifti ilişki değildir:
adlandırılmış olay-yıl kenarı ancak doğrudan eylem fiili veya bitişik tarih
kalıbı bulunduğunda üretilir.

## QLoRA kabul sırası

Otomatik adaylar önce kaynak kesiti üzerinden incelenir. İnceleme sonrası
altı koçluk durumunun tamamı bulunan soru grupları private QLoRA dışa
aktarımına girer. Kaggle paketi PDF, koordinat, cevap anahtarı, çözüm metni,
öğrenci verisi ve kapalı test içermez. `history_tutor_qwen14b_qlora.py`,
Qwen3-14B için NF4 4-bit QLoRA, completion-only loss ve grup bazlı split
doğrulamasını uygular.

## Deney kaydı ve geçerli durum

Kaggle'daki teknik QLoRA smoke testi tamamlandı: Qwen3-14B sabit sürümü,
NF4 4-bit taban, fp32 LoRA ana ağırlıkları, üç epoch, 168 eğitim ve 36
geliştirme turu. Adaptör üretildi. Bu küçük setin `eval_loss` değeri yalnız
optimizasyon sinyalidir; taban modele karşı pedagojik kalite kanıtı değildir.

İlk 180 tersine üretilmiş taslağın kalite denetimi, uzun atomların ve OCR
artıklarının konuşulamaz soru ürettiğini ortaya çıkardı. Bu bulgu sonrasında
kalite kapısı ve olay-yıl ilişki denetimi eklendi. Yeni 120+ grubun eğitimi,
kapalı testte kullanılacak grup ayrımı, kaynak bağlılık ve erken cevap ifşası
değerlendirmesi hazır olmadan başlatılmaz. Araştırma çıktısı öğrenci çalışma
zamanına alınmaz; `research_only` sınırı korunur.

Graf kaynaklı taslaklar için `audit_autonomous_graph_scope.py`, hedef kapsam
manifestindeki MEB checksum'ı ve sayfa aralıkları içinde ayrı kalite raporu
üretir. Kapsamlı son denetimde 71 taslağın 13'ü yalnız mekanik kapıyı geçti;
bu sayı pedagojik veya tarihsel onay değildir. Önceki tüm kitaplardan gelen
180 taslak, altı hedef bölümün QLoRA eğitim verisi olarak kullanılmaz.

## Eğitim verisi incelemesi ve sızıntısız bölme

80 grupluk v7 araştırma pilotundan bağımsız tarih öğretmeni ajanı 34 benzersiz
grubu ve 204 tekil koçluk turunu inceledi (ham kaynak dosyalarındaki 246 satırın
42'si aynı grupların tekrarıydı). Kanıt kararları 12 doğrudan, 18 sınırlı
çıkarım ve 4 yetersizdi; ancak **eğitime kabul edilen grup sayısı sıfırdır**.
Alıntı provenance, hedef ünite eşleşmesi ve metin-sorusu/görsel bağımsızlığı
aynı anda doğrulanamadı; bazı koçluk turları genel şablonları tekrarlıyordu.
Bu ajan kararı insan öğretmen onayı değildir. Cevap anahtarı ve çözümlü yanıt
açılmadı. İçerik güvenli inceleme özeti private
`teacher-coaching-34-groups-independent-review-v1.json` içindedir.

QLoRA readiness ve exporter artık soru kimliklerini rastgele sıralamak yerine
transitif `ConceptBasedDataSplitter` kullanır. Bölme kavramları istemci
payload'ından alınmaz: inceleme API'si bunları onaylı soru grafındaki ilişki
uçlarından üretir. Kanıt parçası kimliği provenance'tır, kavram değildir; geniş
bir paragrafın ilgisiz soruları tek kümeye bağlamasını önler. Onaylı grafik
ilişkisi yoksa kavram anahtarı oluşmaz ve QLoRA kapısı kapanır. Ortak kavramı olan soru
grupları aynı bölümde kalır; aynı grubun altı turu da birlikte taşınır. Tam
120 grup bulunsa bile üç bölüme ayrılamayan kavram bileşenlerinde readiness
kapısı kapalıdır. Bölüm sayıları tam 84/18/18 olmak zorunda değildir; sızıntı
önleme oran hedefinden önce gelir ve gerçek grup sayıları raporlanır. Kapalı
test Kaggle'a aktarılmaz.

2026-11 doğrulaması: son kodla tam API testleri 621/621, concept/readiness/route
hedef testleri 14/14 geçti. Üretim verisi halen 120 onaylı grup ve 720 tur
koşulunu karşılamıyor; QLoRA başlatma bayrağı veya Kaggle dışa aktarımı açılmadı.

Pilot v7'nin kalan 46 benzersiz grubu da cevap anahtarı ve çözümler açılmadan
incelendi; ilk 34 grupla birlikte 80/80 tamamlandı ve üretim için kabul edilen
sayı 0 kaldı. Kalan grupların 16'sı doğrudan, 24'ü sınırlı çıkarım, 6'sı
yetersiz kanıt aldı; kanıt etiketi tek başına kabul anlamına gelmedi. 46 grubun
hiçbirinde metin sorusunun görsel bağımsızlığı açıkça onaylanmamıştı; pilot
JSONL'lerinde satır bazında kaynak kimliği/kesit izi de yoktu. 33 grupta uzun
kanıt alıntısı öğrencinin denemesinden önce veriliyordu; koçluk şablonu 35
grupta tekrarlı, 25 grupta OCR/kesit kopukluğu vardı. Ayrıntı private
`teacher-coaching-v7-remaining-independent-review-v1.json` dosyasında.

Soru üreticisine olay + ilişki + yanıt tekrarlarını tekilleştiren fingerprint
kapısı eklendi. İki kaynağın altı hedef bölümündeki son koşu 39 adayı inceledi;
7 anlamsal tekrar atıldı, 13 soru mekanik ve kaynak kontrollerini geçti
(10 tarih–olay, 3 aktör–olay). Bu, öğretmen koçluk onayı değildir; aday havuzunda
107/120 grup eksik olduğu için eğitim örneği üretilmedi. Güncel içerik taşımayan
özet private `ayt-graph-candidate-production-run-v2.json` dosyasında; v1 önceki
tekilleştirme öncesi koşu olarak korunmuştur.

Bu 13 adaydan üretilen 18 koçluk taslağı bağımsız öğretmen ajanına ayrıca
inceletildi. Tekrarlar birleştirildiğinde 13 benzersiz soru grubu kaldı; 18
taslağın tamamı reddedildi, eğitim turu yazılmadı. Başlıca nedenler soru
kalitesi, görsel kesit doğrulaması ve kaynak-iddia ilişkisiydi. Alıntıların
provenance denetimi 18/18 geçti; bu, alıntının soruyu desteklediğini kanıtlamaz.
Dolayısıyla güncel üretim QLoRA verisi hâlâ 0 onaylı grup/0 turdur. Önceki
80 grupluk pilot ve bu yeni küçük aday paketi eğitim için uygun değildir. Yeni
eğitim yalnız 120 öğretmen-ajan denetimli grup, altı nitelikli tur/grup ve
sızıntısız konu bazlı ayrım kapısını geçen dışa aktarımla başlayabilir.

## 8 Kasım 2026: Dört Dörtlük kaynağını güvenli aday havuzuna alma

Resmî OGM *Dört Dörtlük AYT Tarih* PDF’si yerel private alana indirildi ve
checksum ile sabitlendi. İçindekiler tablosu 26 konu, 281 çözümlü soru, 1.325
test sorusu ve 1.606 toplam soru gösteriyor. Kaynak telif bildirimi nedeniyle
PDF ve türetilen soru metinleri yerel/private kalıyor; bu adım Kaggle yükleme
izni vermez.

Keşif hattı yalnız fiziksel PDF sayfaları 229–235 (1.3), 239–245
(2.1/2.4/2.5 adayları), 251–257 (3.1 adayı), 261–267 (3.2 adayı) sayfalarını
açıyor. Her sayfanın basılı numarası ve test başlığı doğrulanıyor. Çözümlü
soru ve cevap anahtarı sayfaları okunmuyor. İlk çıkarım 155 temiz parse, 8
düzen/metin incelemesi gerekli ve 5 görsel bağımlı dışlama üretmişti. Güncel
pakette soru kökleri ve seçenekler yeniden kırpımlarla karşılaştırıldı;
bağımsız tarih öğretmeni ajanı 163/163 metni kesitlerle tam eşleşmiş buldu.
Sayfa haritası ünite kararı olarak kullanılmadı. Sorunun ne istediğine göre
yapılan kapsam önerisi 1.3 için 15, 2.1 için 23, 2.4 için 4, 2.5 için 14,
3.1 için 31 ve 3.2 için 48 soru; toplam 135 koçluk adayıdır. 23 soru hedef
altı bölümün dışında, 5 soru belirsiz kaldı. Bu sayı agent kapsam incelemesidir;
PDF kaynak kanıtı veya öğretmen onayı değildir.

Kırpım incelemesi iki ortak çıkarım sorununu ortaya çıkardı. Ayrı PDF metin
bloklarındaki soru numarası ile kök satırının küçük y-koordinatı farkı, bir
sonraki sorunun ilk satırını önceki soruya ekleyebiliyordu. Okuma sırası aynı
görsel satırdaki blokları soldan sağa sıralayacak biçimde düzeltildi. İkinci
sorun, bitmap olmayan vektör çizimli tabloların görsel filtresini atlamasıydı.
Tablo tespiti artık aynı sütun ve soru alanında birbiriyle örtüşen büyük vektör
bölgeleri arıyor; tekil süs çizgileri ve komşu sütuna taşan çizimler tek başına
görsel bağımlılık sayılmıyor. Basılı sayfa 227’de
tablo kullanan soru kapsam dışına çıkarılırken, komşu iki metin sorusunun
kökleri ayrı kalıyor. Bu regresyon private kaynaktan yerel testle ve sentetik
satır-sıralama testiyle korunuyor. Eski tüm dersler denemesinde 29. soru crop
kontrolüyle metin sorusu olduğu doğrulanmıştı; vektör watermark'ı onu yanlış
dışlamıştı. Sınırlı vektör kuralı bu false positive'i kaldırıyor, gerçek tablo
sorusunu dışlamaya devam ediyor.

Yeni private inceleme paketi 163 soru/kırpım içeriyor. Agent raporu
`data/private/ogm-supplementary-v1/dort-dortluk-review-v1/independent-history-teacher-review-v1.json`
altındadır. Agent yalnız aday manifestini ve test sorusu kırpımlarını kullandı;
MEB kaynak PDF'lerini açmadı, cevap anahtarı veya çözümlere erişmedi. Bu yüzden
çıktı kapsam ve transkripsiyon triyajıdır. 135 adayın yedisi metni exact olsa da
çıkarım/düzen kuyruğunda kaldı; otomatik retrieval'a alınmadı. Geriye kalan 128
temiz soru için cevap anahtarsız BM25 keşfi dört MEB kaynağında 768 aday kesit
üretti. Konu havuzu bölüm başlıklarının gerçek yazımına göre daraltıldı; yine
de 425/768 kesit ilgili alt bölüm dışında kaldı ve yalnız 66/768 kartta soru
kökü terim kapsaması sinyali vardı. Bu sayılar kanıt kalitesi değil, mevcut
retrieval taban çizgisinin incelenecek sonuçlarıdır. PDF koordinat/checksum
denetimi 768 kesitin 767'sini metin benzerliğiyle doğruladı; kalan kart görsel
inceleme gerektiriyor. 128 soru ve 768 kartlık bağımsız kanıt incelemesi
başlatıldı. Şu an onaylı soru, kanıt veya eğitim örneği sayısı sıfırdır;
Kaggle, runtime ve QLoRA kapalıdır.

## 8 Kasım 2026: Kör kanıt denetimi ve bölüm eşleme düzeltmesi

İki bağımsız tarih öğretmeni ajanı, ilk retrieval sürümünün 128 sorusundaki
768 kartın tamamını ve her sorunun en fazla üç parçalı kanıt demetini cevap
anahtarı/çözüm olmadan değerlendirdi. Kart kararları 11 direct, 252 partial,
505 irrelevant; ilk demet kararları 12 direct, 94 insufficient ve 22 wrong
oldu. Bir kart/demet tutarsızlığı bulundu: p239:q3 kartı partial iken demet
direct işaretlenmişti. Ajan yeniden değerlendirmesinde bunu bounded_inference
olarak sınıflandırdı. Düzeltilmiş v1 özeti 11 direct, 1 bounded_inference, 94
insufficient ve 22 wrong gösteriyor; kart/demet tutarlılığı geçti. Bu ajan
incelemesi insan öğretmen onayı değildir; onaylı kaynak ve eğitim grubu sayısı
sıfırdır.

İnceleme ayrıca gerçek bir kapsam eşleme hatasını gösterdi. p229:q2
Anzakların hangi devletlerden toplandığını soruyor; 11. sınıf MEB kitabında
“1908–1918 Yılları Arasında Osmanlı Devleti’nde Meydana Gelen Siyasi ve Askerî
Gelişmeler” başlığı altında doğrudan “Anzaklar (Avustralya ve Yeni Zelanda
birlikleri)” bilgisi bulunmasına rağmen ilk konu filtresi bu başlığı hedef
saymıyordu. `ogm_ayt_evidence_queue.py` içine yalnız bu tarihsel bölüm için
özgül bir 11. sınıf başlık alias’ı eklendi. Aynı soru v2 kuyruğunda doğru
paragrafı top-6’ya aldı; ajan PDF kırpımını doğrudan kanıt olarak doğruladı.
Bu spot check 1/1 sonuçtur, genelleme başarısı sayılmaz.

Alias değişikliğinin etkilediği 15 sorunun 90 yeni/yeniden sıralanmış PDF
kesiti ayrı v2 inceleme paketine alındı. Tam bağımsız v2 değerlendirmesi
bekleniyor. Bu sırada eski v1 denetimi değişmeden korunuyor; alias henüz
genel retrieval kabulü veya runtime ayarı değildir. Private raporlar:
`dort-dortluk-evidence-review-v1/validation-summary-v1-amended.json`,
`dort-dortluk-meb-evidence-proposals-v2.json` ve
`dort-dortluk-evidence-review-v2/index.html`.

Sonraki aday motoru, soru kökü ve tüm şıkları eşit ayrı arama kanalları olarak
çalıştırıyor; BM25 sıralamalarını RRF ile birleştiriyor ve her öneride hangi
kanalların eşleştiğini denetlenebilir biçimde tutuyor. Doğru şık tahmini
yapılmıyor. 128×6 aday üretildi; PDF checksum/koordinat/metin denetimi
768/768 geçti. Retrieval p50 13,98 ms, p95 25,89 ms (en yavaş sorgu 81,97 ms).
İlk/son 64 soruluk iki kör inceleme sürüyor. Sonuçlar gelene kadar bu yol
araştırma adayıdır; production retrieval, öğrenci RAG ve QLoRA kapıları kapalı.

V3 ajan denetimi tamamlandı: iki ajan 128 sorudaki 768 öneriyi ve her soru
demetini değerlendirdi. Kart etiketleri 11 direct / 286 partial / 471
irrelevant; demetler 11 direct / 2 bounded inference / 86 insufficient / 29
wrong. PDF checksum/kırpım yapısı geçti ve demet tutarlılık uyarısı yok.
Önceki v2 sonucunda destekli demet 15/128, v3'te 13/128 oldu. Geçişlerde
11 destekli karar korundu, 3 önceki destekli karar yetersize döndü ve 1 yeni
sınırlı çıkarım oluştu. Bu nedenle claimwise RRF ürün retrieval'ına alınmıyor.
v2-v3 kıyası aynı soru havuzunu kullanıyor; A ajanı 260/384, B ajanı 211/384
aynı soru-kaynak çiftini önceki incelemelerden tanıdığını işaretledi. Yeni
işaretlenen 297 kart bağımsız, kapalı test performansı değildir. BM25 aday
arama p50 13,97 ms, p95 25,89 ms, en yüksek 81,97 ms; bu süreler yalnız aday
aramayı ölçer. Private doğrulama özeti:
`dort-dortluk-evidence-review-v3-claimwise/validation-summary-v3-claimwise.json`.

Kapasite kontrolü, temiz Dört Dörtlük havuzundaki 128 soruyu hedef ünitelere
şöyle dağıtıyor: 1.3: 15, 2.1: 23, 2.4: 4, 2.5: 12, 3.1: 28, 3.2: 46.
Önceki üç kaynakta 55 tekil ham aday sayılmıştı; Dört Dörtlük ile tam metin
eşleşmesi bulunan beş soru çift sayılmamalı. Sayılar kaynak/öğretmen onayı
değil. 2.4 için görünen toplam 17 aday 20'şer dengeli grup hedefinin altında;
en az üç ayrı aday daha gerekiyor ve eski 13 adayın bölüm eşleşmeleri ayrıca
doğrulanmalı. Kaynak onaylı grup ve koçluk örneği sıfır; Kaggle ve QLoRA kapısı
kapalı.

Önceki graf kaynaklı 18 taslak da bağımsız öğretmen ajanı tarafından
incelendi: 18 taslaktan 13 benzersiz grup ve 5 tekrar vardı; 18/18 kaynak
alıntısı izlenebilse de soru/kanıt/kırpım sorunları nedeniyle kabul 0, yazılan
koçluk seti 0 oldu. 2.1 kapsanmadı. Cevap etiketi, cevap anahtarı ve çözümler
kullanılmadı; bu sonuç bağımsız ajan incelemesidir, insan öğretmen onayı
değildir.

## 8 Kasım 2026: PDF metin onarımı ve konu dışı kanıt keşfi

12. sınıf MEB kitabının fiziksel 78. sayfasında, paragraf sonunda `(Görsel 2.10)` atfı bulunduğu için kısa-görsel sezgisi paragrafın tamamını görsel açıklaması gibi eliyordu. Aynı PDF metin katmanı satır sonu yumuşak tire ve boşlukla `Konfe ransı` üretiyordu; bu nedenle arama `Konferansı` terimini birleştiremiyordu. Caption sınıflandırması artık yalnız açıkça etiketlenmiş kısa görsel bloklarını ve kısa eser/müze açıklamalarını işaretliyor; paragraf içi görsel atfı tek başına engel değil. Temizleyici satır sonundaki yumuşak tire ile devam boşluğunu birlikte kaldırıyor. Fiziksel 78. sayfadaki Paris–San Remo paragrafının temiz ve özel inceleme adayı olarak indekse girdiği gerçek PDF regresyon testiyle doğrulanıyor. Parça öğrenci RAG kaynağı olarak onaylı değildir.

10., 11. ve 12. sınıf kitapları ile AYT konu özeti yeni checksum bağlı private corpus v6'ya kuruldu. Corpus v5'teki 2.505 chunk ve 5.007 kanıt atomu v6'da 2.811 chunk ve 5.256 atom oldu. Dört kaynağa göre üretilen 128×12 önerinin checksum/sayfa/koordinat ve PDF metin denetimi 1.536/1.536 geçti; düşük metin benzerliği 0. Bu provenance denetimidir, tarihsel destek onayı değildir.

Öneri kuyruğunda konu filtresi ilk 12 yuvanın tamamını tüketemiyor: sekiz aday konu içi, dört aday diğer bölümlerden seçiliyor; eksik havuzlar boş kalan yuvayı tamamlıyor. Böylece p229:q4 için Sevr kitabı 78. sayfadaki Paris/San Remo paragrafı ilk 12 öneriye girdi. Soru iki ayrı konferansın kararlarını tek kökte birleştiriyor olabilir; bu nedenle kaynak parçası soruyu çözdü veya destekledi diye işaretlenmedi, iki kör ajan incelemesine alındı. Yerel aday araması v6'da p50 95,48 ms, p95 211,00 ms, maksimum 273,83 ms ölçtü. Bu süreler kalite metriği değildir ve önceki aday havuzuyla doğrudan kalite kıyası oluşturmaz.

V4 ile aynı PDF checksum/sayfa/koordinat imzasına sahip kesitlerin önceki incelemesi korunuyor. V6'nın yeni kırpım imzaları 629 kesittir: ilk 64 soruda 312, son 64 soruda 317. İki ajan yeni kesitleri ve etkilenen sorulardaki seçenek kararlarını inceliyor. Kaynak onaylı grup/koçluk verisi henüz yok; öğrenci RAG'ı, Kaggle ve QLoRA kapalıdır.

### V3 seçenek bazlı ikincil denetim düzeltmesi

Önceki v3 özeti 13/128 demeti destekli görünüyordu; daha sonra bu 13 sorudaki her A–E şıkkı ve kök tutarlılığı ayrıca denetlendi. 8 direct, 2 bounded inference, 3 insufficient çıktı; 0 wrong. Yani önceki destekli görünen üç soru, aynı aday demetinde tek bir seçeneğe güvenle indirgenemiyordu. Rapor yalnız 13 soruluk seçilmiş altkümedir, tüm 128'in yeni değerlendirmesi değildir. PDF ve kaynak onayı/QLoRA yine kapalıdır. Private rapor: `dort-dortluk-evidence-review-v3-claimwise/independent-option-evidence-audit-b-v1.json`.

V6 kapsam kotası, V4'teki A ve B yarı-küme incelemelerinde destekli bulunan 21 sorunun eski supporting crop imzalarının 21'ini de ilk 12'de tuttu. Bu yalnız önceki adayları kaybetmediğimizi doğrular; doğru destek, doğru cevap veya genel retrieval kalitesini kanıtlamaz.

### V6 karşılaştırması ve soru kökü tutarlılık denetimi

İki V6 yarı-küme raporu, aynı 128 soruluk V4 tabanıyla karşılaştırılabilir
biçimde birleştirildi. V4'te 18 direct + 2 bounded, V6 ilk geçişinde 35
direct + 3 bounded çıktı; 18 eski `insufficient` kararı destekli göründü.
Bu artış, aynı inceleme havuzuna daha geniş/dış-bölüm kesitler eklemenin
adaylarda daha fazla ilgili kanıt gösterdiğine dair pilot bulgudur; kör,
bağımsız retrieval başarı ölçümü veya ürün kabul metriği değildir.

İkinci incelemede p229:q4'ün kökü birden çok konferans bilgisini aynı olaya
bağlıyordu. S.58 ve s.61 İzmir işgali kararını Paris Barış Konferansı'yla
ilişkilendirirken s.78 San Remo'da barış koşullarının hazırlandığını söylüyor;
İngiltere'nin sahte nüfus belgesini kabul ettiği iddiası da kaynakta
doğrulanmıyor. Bu soru `insufficient` olarak karantinaya alındı. p244:q7'de
Sakarya Muharebesi ile sonraki antlaşmalar arasındaki neden-sonuç bağı açık
cümleyle kurulmadığı için `direct` kararı `bounded_inference` seviyesine
indirildi.

V6'nın iki yarısındaki ilk destekli kararlar da ikinci agent tarafından
denetlendi. Beş karar daha `insufficient` oldu; iki `direct` karar sınırlı
çıkarıma indirildi. Güncel ara sayım 27 direct, 5 bounded, 95 insufficient ve
1 kaynak/şık uyumsuzudur; 32/128 demet desteklenebilir aday olarak kaldı.
Bunlar öğretmen onayı değildir.

Seçenek alıntısı denetimi 7 eski chunk kimliğinin corpus v6'da değiştiğini
buldu. Bu alıntılar aynı kaynak checksum'ı ve PDF sayfasında güncel chunk
metninde bulundu; yalnız bu checksum/sayfa eşleşmesiyle yeniden bağlandı.
Destek kararı verilmiş bir p262:q11 seçeneğinde alıntı yoktu; ikinci inceleme
bu grubu da insufficient'a indirdi. Denetim aracı ve private sonuç
`audit_dort_dortluk_v6_citations.py` / `option-citation-audit-v3.json`
altındadır. QLoRA dışa aktarımından önce her kaynak ID'si güncel corpus
sürümünde yeniden çözülmelidir.

Tekrarlanabilir karşılaştırma aracı
`app.pipeline.summarize_dort_dortluk_v6_review` ve testleri eklendi. Araç
V4/V6 yarı raporlarının 128 soruyu çakışmasız ve tam kapsamasını, cevap
anahtarına erişilmediğini ve QLoRA/runtime bayraklarının kapalı kaldığını
kontrol ediyor; soru bütünlüğü adjudication'larını toplamadan önce uyguluyor.
Private raporlar `dort-dortluk-evidence-review-v6-cross-section-delta/`
altında. Agent incelemeleri insan öğretmen onayı değildir; kabul edilmiş
koçluk grubu hâlâ 0'dır ve Kaggle/öğrenci RAG/QLoRA kapıları kapalıdır.

### V7 top-24 yeni kesit denetimi (tamamlandı; eğitim kapısı kapalı)

V6 adjudication'ında karara bağlanmamış 89 soru için claimwise RRF havuzu
top-12'den top-24'e genişletildi. Her soru için yalnız önceki kuyrukta olmayan
12 PDF kesiti üretildi: toplam 1.068 yeni kesit. PDF checksum, sayfa aralığı,
görüntü dosyaları ve HTML bağlantıları doğrulandı; iki paket 46/43 soruya
bölündü ve aynı sorunun kesitleri tek inceleyicide tutuldu. Yeni birleştirme
denetimi rapor kapsamını, corpus checksum'ını, cevap anahtarı bayraklarını,
görsel kontrolü, güncel chunk kimliklerini ve birebir alıntıyı doğrulayacak.
Hazırlama/alıntı/merge hedef testleri 16/16, Ruff ve `git diff --check` geçti.
Tam API test paketi de 652/652 geçti. İlk tam koşuda bulunan yumuşak tire
denetimi regresyonu düzeltildi: PDF satır kırılımından düzeltme yalnız seçili
PDF satırları mevcut indeks metninin geri kalanıyla eşleştiğinde öneriliyor;
öneri indeksi sessizce değiştirmiyor.

İki ajan tüm kesitleri cevap anahtarı ve çözüm görmeden görsel olarak inceledi.
A ajanı 46 soruda 2 direct / 44 insufficient; B ajanı 43 soruda 1 direct /
2 bounded / 40 insufficient bildirdi. Raporlar tam görsel denetim ve provenance
kapılarından geçtikten sonra V7 delta özeti 3 direct, 2 bounded, 84 insufficient
olarak üretildi; destek adayı sayısı 5'tir. Bu sınıflama öğretmen onayı değildir.
Seçili 128 sorunun tamamı, önceki soru-kırpımı kapsam denetimindeki
`text_only` kararlarıyla birebir eşleşti (128/128; eksik veya görsel-bağımlı
eşleşme yok); yeni tur görsel bağımsızlığı ayrıca yeniden kaydediyor.
İlk ikinci turdaki 32/128 destek adayı ve 95 yetersiz + 1 yanlış grubu bu
yeni aday aramasının başarı metriği sayılmıyor. V7 incelemesi bitmeden yeni
kanıt demeti oluşturulmayacak; insan öğretmen onayı, öğrenci RAG'ı, Kaggle ve
QLoRA kapalı. Kapsam dışı görsel bağımlı sorular eğitim havuzuna alınmayacak.

V7'nin beş destekli adayını ve aynı konulardan beş yetersiz adayı içeren ayrı
bir kör tekrar paketi hazırlandı. Yeni ajan 10 sorunun 120/120 kesitini görsel
olarak inceledi; cevap anahtarı ve çözümler kapalı kaldı. Önceki beş destekli
adayın tamamı tekrar desteklendi (3 direct, 2 bounded). Bu örneklem tüm V7
havuzundan seçilerek destekli adaylarla zenginleştirildiği için 5/5 sonucu
genel precision tahmini değildir. Beş yetersiz kontrolün dördü yetersiz kaldı;
bir Halkçılık sorusundaki sınırlı çıkarım kararı, alıntının soru kökündeki iki
ilke bağını kurmaması nedeniyle ihtiyatlı biçimde yetersize indirildi.
Bağımsız tekrarın son dağılımı 3 direct, 2 bounded, 5 insufficient oldu.
Denetim aracı 120 kesit kimliğini, dosya varlığını, checksum/sayfa bağlantısını
ve cevap anahtarı/runtime/QLoRA bayraklarını doğruluyor. Bu tur da öğretmen
onayı değildir. Ardından değerlendirme yönteminde yeni bir hata bulundu:
delta paketi yalnız yeni 12 kesiti gösterdiği için eski 12 kesitteki kanıtlar
tam 24'lük demet içinde tekrar tartılmıyordu. Örneğin Gümrü sorusunda kitap
sayfa 81–82'de antlaşma hükümleri bulunuyor ve bu parçalar top-24 listesinde
ilk sıralardaydı; ancak delta incelemesi bu eski kesitleri tekrar göstermedi.
Bu nedenle 5/5 bağımsız tekrar sonucu eski kararların doğruluğunu sınar, fakat
top-24 demetinin bütünsel yeterliliğini sınamaz.

Bu açığı kapatmak için 89 karara bağlanmamış soruda top-24'ün tamamını (eski
12 + yeni 12) birlikte sunan yeni kör inceleme paketi üretildi: 89 soru / 2.136
PDF kırpımı; kapsam dışı ve kaynakla çelişkili p266:q8 dahil edilmedi. Eşleşen
ilk 9 soruluk pilotta iki ajan 7/9 kararda aynı etiketi verdi; bu yalnızca
ön inceleme etiketlerinin karşılaştırmasıdır. B ajanı contact sheet'te metnin
çoğunu güvenilir biçimde okuyamadığını ve 216 kırpımın tamamını tek tek
incelemediğini bildirdiği için 7/9, güvenilir bir değerlendiriciler arası
uyum/IAA ölçümü değildir. p231:q2 ayrımı direct/bounded düzeyindeydi;
p231:q5 ayrımı ise karar gerekçesine taşınmayan bir pasajdan kaynaklanıyordu.
Üçüncü ajan p231:q5'in 24
kesitini tek tek açtı: s.39'daki Sofya ataşemiliterliği ifadesini ve s.32'deki
1915 Çanakkale kronolojisini birlikte kullanarak bounded inference verdi.
“Anafartalar'dan önce” görevini “Çanakkale'ye katılmadan önce” ile eşitlemedi.

Aynı pilot, retrieval içinde ayrı bir kusur da gösterdi: 11. sınıf kitabı
s.292'deki “Anzaklar (Avustralya ve Yeni Zelanda birlikleri)” paragrafı tüm
corpus'ta bulunuyor ve yalnız `choice:C` sorgusunda 3. sırada geliyor; eklemeli
RRF'in 24'lük listesine girmiyordu. Araştırma amaçlı
`claimwise_option_reserve` stratejisi her seçeneğin yüksek sıralı adayına eşit
yer ayırıyor. Dokuz soruluk, dört kaynak referanslı küçük retrieval ablation'ı
aday Recall'ını 3/4'ten 4/4'e çıkardı; Anzak parçası alternatif listede 2.
sıraya girdi ve kör ajan bunu doğrudan destek olarak doğruladı. Bu sayı dar ve
tanısal örnekleme aittir; corpus geneli Recall veya precision değildir.

İnceleme tasarımındaki bulgu da sonuç kadar önemli: p231:q5'te alıntı mevcut
24'lük listede 5. kesitteydi; ilk ajan kesit ID'sini kontrol edilmiş yazmasına
rağmen ilgili cümleyi kararında kaçırdı. Bundan sonra yalnız “görsel açıldı”
işareti yeterli sayılmayacak; olumlu/yetersiz kararın soru kökündeki ilişkiyi
hangi alıntının karşıladığı veya neden karşılamadığıyla eşleşmesi denetlenecek.
İlk 9 paired pilot grubunun inceleme kaydı contact-sheet seviyesinde
ön incelemedir; iki grupta (p229:q2 ve p231:q5) ayrıca bağımsız 24/24 kırpım
odaklı tekrar vardır. Sonraki 80 soru grubunun her biri için batch raporu
24 kırpımın tek tek açıldığını bildiriyor. Böylece toplam 89 soru grubunda
araştırma inceleme kaydı, 82 grupta tam 24 kırpım bireysel görsel inceleme
kaydı bulunuyor. Güncel araştırma etiketleri 17 direct, 14 bounded inference,
56 insufficient ve 2 wrong. Bu sayılar öğretmen onayı değildir; insufficient
yalnız incelenen 24'lü aday listesinin yetersizliğini belirtir, kitabın tümünde
kanıt olmadığı sonucunu vermez. İlk 10 ek batch'te üç direct, dört bounded inference, yirmi bir
insufficient ve iki wrong kararı çıktı. p234:q11'de Ermeni ve Arap gruplarına dair kısmi
bilgi vardı, ancak şıklardaki kalan toplulukları ayıran kanıt yoktu. p235:q5'te
24 Nisan genelgesi ile daha sonraki tehcir yargılamaları ayrı olaylar olarak
tutuldu. p239:q1'de Taşnaksütyun'un Ermeni cemiyeti olduğu açıkça
desteklendi. p245:q1, p245:q5 ve p240:q10'da ise listelenen iddiaları
karşılaştırmaya yetecek kuruluş tarihi, kişi bağlantısı veya antlaşma sonucu
kanıtı pakette yoktu. p241:q4 için metin bir cemiyetin İstanbul Hükûmeti’ni
desteklediğini açıkça söylediğinden, çelişen seçenek wrong olarak işaretlendi.
p243:q3 için Ankara’nın merkezî konumu, cephelere yakınlığı ve ulaşım koşulları
destekleniyor; ancak Mustafa Kemal’in vekillik görevi kaynakta verilmediğinden
cevap yalnız sınırlı çıkarımla değerlendirildi. p240:q8, Güney Cephesi ile Ankara
Antlaşması ilişkisini aynı kaynakta veriyor; sorunun geri kalanındaki kişi/karar
bağlantıları nedeniyle sonuç bounded kaldı. p245:q22 de eğitim reformu ile
siyasi/devlet reformu ayrımını sınırlı biçimde kuruyor; p245:q23 iki unvanın
aynı kişiye yanlış atandığını metinle çürütüyor.
p229:q5 için bir ajan “Yunanistan
katıldı” iddiasını wrong saymıştı; bağımsız focused inceleme, pasajın Rauf
Orbay heyeti ve İngiliz Amiral Calthorpe'u adlandırdığını ancak “yalnız onlar”
veya “Yunanistan katılmadı” demediğini doğruladı. Bu nedenle `wrong` yerine
bounded inference; yokluk yalnızca kaynakta ad geçmemesinden çıkarılmıyor.
Bu sonuç kaynak doğruluğu açısından önemli bir emniyet düzeltmesidir.

Option-reserve şimdilik yalnız private öğretmen keşif kuyruğu deneyidir; runtime,
öğrenci RAG'ı, Kaggle ve QLoRA'ya alınmadı. 89 soruluk birleşik top-24 paketin ajan incelemesi tamamlandı; eski yetersiz etiketler kesin sonuç sayılmıyor, çünkü sonuç yalnızca bu aday slate’lerini kapsıyor.

Genişletilmiş BM25 karşılaştırmasında aynı 89 soru için seçenek-korumalı kuyruk
ile klasik claimwise RRF yeniden üretildi. V8 incelemesindeki ilk ölçümde 8
soru grubundan gelen 15 alıntılı olumlu kaynak referansında RRF 14/15, seçenek
koruma 15/15 referansı top-24'e aldı. Eklenen referans Anzakların Avustralya ve
Yeni Zelanda birlikleri olduğunu belirten s.292 paragrafıydı. Top-24 araştırma
kuyruğu üretiminde per-soru p50/p95 77/161 ms'den 89/214 ms'ye çıktı; indeks
kurulumu bu süreye dahil değil ve donanım sabitlenmedi. Bu referanslar mevcut
inceleme slaytlarından seçildiği için bağımsız test değildir. Seçenek-korumalı
slate sırası seçenek kapsaması için tasarlanmıştır; sıralama kalitesi metriği
olarak yorumlanamaz. Aday kaynakların yanlış-pozitif oranı da henüz ölçülmedi.
Sonuç, öğretmen keşif kuyruğunda daha fazla kanıtı görünür kılma yönünde küçük
bir kazanım gösteriyor; öğrenci runtime'ına geçişi doğrulamıyor.

V8 kapsamı ayrıca 89 soru kimliğinin temiz transkripsiyonlar ve mevcut görsel
bağımlılık filtresiyle eşleşmesi üzerinden denetlendi: yapılandırılmış soru
metni/metadata alanlarında kapsam dışı görsel sinyali bulunmadı. Bu, soru
sayfası kırpımlarının 89'unun yeniden görsel incelemesi değildir; kaynak
inceleme ajanlarının yaptığı işlem kanıt PDF kırpımlarını değerlendirmektir.
Kapsam filtresi yeni havuz üretiminde çalışmaya devam etmelidir.

### V9 top-48 genişletme incelemesi

V8'de `insufficient` kalan 56 soru için aynı V6 corpus ve aynı soru havuzuyla
claimwise RRF top-48 kuyruğu üretildi. Her soru için önceki top-24'te olmayan
24 kaynak kesiti seçildi; toplam 1.344 PDF kırpımı iki kör inceleme koluna
ayrıldı (30 ve 26 soru). Top-48 listesinin üretim sırasında adayları yeniden
dengeleyebilmesi nedeniyle yeni kesitler yalnız 25–48 sıralarıyla sınırlı
değil; bazı yeni kesitler 17–24 aralığında da görünüyor. Delta, önceki listede
olmayan sayfa/koordinat imzasına göre oluşturuldu.

Delta paketindeki her kesit, PDF checksum'ı/sayfası ve görsel dosyasıyla
doğrulandı (56 soru, 1.344 yeni crop). Tek başına delta ile eski kısmi kanıtın
birleşimini ayırt etmek için inceleme paketi 48'li birleşik görünüme genişletildi:
her soru için eski 24 + yeni 24 kesit, toplam 2.688 crop. Ayrıca her adayın
orijinal soru PDF sayfası temiz transkripsiyonun kaynak checksum'ı eşleştirilerek
pakete eklendi (56/56 görsel). Harita, tablo veya şekle bağımlılık böylece soru
sayfasından incelenecek. Ajanlar birleşik pakette tüm kaynak kesitlerini alıntı
ve soru kökü ilişkisiyle değerlendirecek. Top-48'de görünen parça kendi başına
onaylı kaynak sayılmaz. Tam inceleme, `insufficient` sonucunu iki tanıya ayırır:
top-48'de hiçbir ilgili aday işaretlenmeyen retrieval miss ve kısmi adaylar
bulunsa da soruyu ayırmaya yetmeyen kanıt demeti. Bu iki durum da tam corpus'ta
kanıt olmadığı anlamına gelmez; genuine source gap demek için ilgili kitap
bölümlerinde ayrı kapsam taraması gerekir.

İki ajan 56/56 özgün soru sayfasını ve 2.688/2.688 kanıt kırpımını görsel
olarak inceledi. Soru sayfalarının tümü metin temelliydi; okunamayan görsel
yoktu. Birleştirilmiş ve provenance denetiminden geçmiş kararlar **5 direct,
51 insufficient, 0 bounded inference, 0 wrong** oldu; yedi önceki alıntı
uyuşmazlığı düzeltildikten sonra citation issue sayısı sıfırlandı. Bu sonuç,
V6 corpus'unda aynı sorular için üretilmiş top-48 aday demetinin tanısıdır;
kitapların tamamında kanıt bulunduğu veya bulunmadığı oranı değildir.
Yetersiz 51 grubun 30'unda ajanlar en az bir kısmen ilgili aday, 21'inde ise
top-48 içinde ilgili aday olmadığını işaretledi. Bu ayrım yalnız gözden geçirilen
aday listesine aittir; 21 kayıt full-corpus source gap olarak yorumlanamaz.

İnceleme ayrıca üç alıntı sınırının çoklu eşleştirme sorularında yapay bir
darboğaz olabileceğini gösterdi: p241:q2 dört eşleştirme ilişkisini üç benzersiz
kaynak parçasıyla destekledi; bir parça iki ilişkiyi birlikte taşıyordu. Bu
nedenle yalnız araştırma denetiminde alıntı sınırı beşe çıkarıldı. Öğrenci
runtime demeti ve QLoRA dışa aktarım sınırları değişmedi. p242:q7 ve p253:q6,
kanıtın soru içindeki tüm ayrımları desteklemediği için direct kararından
insufficient'a indirildi.

Agent kararları insan öğretmen onayı değildir. Cevap anahtarı ve çözümler
kullanılmadı; Kaggle, öğrenci runtime'ı ve QLoRA kapalıdır. Private birleşik
rapor `dort-dortluk-evidence-review-v9-top48-combined/adjudicated-summary-v1.json`
altında tutulur.

### V10 seçenek-rezervli delta denetimi

V9'da `insufficient` kalan 51 soru için aynı V6 corpus üzerinde
`claimwise_option_reserve` top-48 kuyruğu üretildi ve V9 claimwise RRF
slate'iyle sayfa/koordinat imzası üzerinden karşılaştırıldı. Önceki slaytta
olmayan aday sayısı toplam 178 oldu; 50 soruda en az bir yeni kesit bulundu,
bir sorunun 48 adayı V9 listesiyle tamamen aynı kaldı. Bu yalnız aday
çeşitliliği ölçüsüdür; kanıt doğruluğu veya retrieval başarısı değildir.

Yeni kesitler ve orijinal soru sayfaları 50 gruplu, iki kör inceleme paketine
dağıtıldı (A: 27 soru/91 kesit, B: 23 soru/87 kesit). Ajanlardan yalnız yeni
delta için `direct`/`partial`/`irrelevant`/`unreadable` sınıflaması, görsel
soru kapsamı kontrolü ve crop üzerinde birebir kısa alıntı istendi. Cevap
anahtarı, çözüm, önceki karar raporları, öğretmen onayı ve dış bilgi
kullanılmıyor. Nihai soru kararı V9'daki yetersiz gerekçesiyle yeni delta
kanıtlarını birlikte denetledikten sonra verilecek; hatalı top-48 sıralaması
başarı etiketi sayılmayacak. Paket checksum, soru PDF checksum, sayfa, crop
dosyaları ve aday imzaları kontrol edildi. Hazırlayıcı strateji kapısı bu
araştırma kuyruğunu kabul edecek biçimde genişletildi; Ruff ve hedef testler
20/20 geçti.

Kör PDF incelemesi tamamlandı: 50 soru sayfası metin-temelli bulundu; 178 yeni
kesitin 23'ü `partial`, 27'si `irrelevant`, 0'ı `direct`, 0'ı `unreadable`
olarak işaretlendi. p267:q6'da crop üzerinde görünen bir ifade indeks
metninde bulunmadığı için kaynak-metni/koordinat hizalama kusuru ayrıca
kaydedildi; bu kayıt runtime, QLoRA veya kaynak onayına giremez.

`partial` görünen 23 soru için eski ve yeni ilgili kesitler, önceki kararlar
gösterilmeden yeniden birlikte incelendi. 56 crop ve 23 soru sayfasının
tamamını kapsayan validator, 31 birebir alıntının indeks metniyle eşleştiğini
doğruladı: sonuç 1 `direct`, 2 `bounded_inference`, 20 `insufficient` oldu.
Bu altküme yalnız partial-delta vakalarından seçildiği için corpus geneli
recall, precision veya ürün başarısı olarak raporlanmaz.

V10 tanısı bir entegrasyon boşluğunu ortaya çıkardı: kısa `evidence_atoms`
indeksi üretilmesine rağmen bu review kuyruğu yalnız uzun `chunks` katmanını
taramıştı. Atom ve bağlamı birlikte kullanan V11 deneyi aynı 51 soru için
902 yeni fiziksel PDF kesiti ortaya çıkardı; bu yalnız aday çeşitliliğidir.
İki kör inceleme 51 soru sayfası ve 902 crop'u kapsadı: 3 `direct`, 34
`partial`, 14 `irrelevant`, 0 `unreadable`. Ancak 29 alıntı PDF crop'unda
göründüğü hâlde indeks metninde bulunmadı. Neden: review görüntüsü kayıtlı
bounding box'a beş puan dış boşluk ekliyor ve komşu, provenance dışı metni de
gösteriyordu. Bu yüzden V11'deki üç direct kayıt dahil hiçbir karar ürün veya
eğitim verisi olarak kullanılamaz.

Kısa atomları paragraf devamı ile güvenli birleştiren (aynı sütun, küçük
dikey boşluk, bitmemiş cümle, sonraki madde imi yok) çıkarım kuralı ve
regresyon testi eklendi. Gerçek özet kitabındaki Serbest Cumhuriyet Fırkası
örneğinde “1929 Dünya” ile bir sonraki bloktaki “Ekonomik Buhranı” artık aynı,
iki-segmentli atomda kaynak koordinatları korunarak bulunuyor. Review paketi
bundan sonra tam bbox crop'u ve ayrı indeks metnini gösteriyor; alıntı yalnız
bu metinle birebir eşleşirse kullanılabilecek. Yeni corpus checksum'ı V7'ye
çıktı; eski V11 sonuçlarıyla karşılaştırılmayacak. İnsan öğretmen onayı gelene
dek retrieval sonucu öğrenciye, Kaggle'a, runtime'a ve QLoRA'ya açılmayacaktır. Private materyal
`dort-dortluk-evidence-review-v10-option-reserve-top48-delta/` altında.

## 16 Kasım 2026: Tam checksum'lı kaynak ve koçluk pilot kapısı

Eksik olduğu sanılan 12. sınıf kaynağının resmî OGM/EBA kopyası, MEB'in
verdiği bağlantıdan private alana indirildi. `inkilap-12-aday-eba.pdf` SHA-256
değeri `64a392e28af85a936003f25840a7a792ab006ef648ebea7ba34931b9e1421847`
olup V7 corpus'taki 12. sınıf `source_checksum` ile birebir eşleşiyor. PDF 287
sayfa olarak açılıyor; private dosya Git'e eklenmedi.

Bu kaynakla AYT Tarama'dan tek bir öğretmen-agent taslağı (1 grup/6 tur)
hazırlandı. İlk denetim 2/4 erken turda dolaylı cevap ifşası, 6/6 turda aşama
etiketi uyumsuzluğu ve 4/6 turda ikiden fazla kaynak kullandığını saptadı.
Doğru checksum'lı EBA PDF'sinden dört atomun kimliği ve alıntısı V7 corpus ile
eşleştirildi; bağımsız inceleyen dört kaynak kırpımını ve soru kırpımını
görsel olarak kontrol edip sorunun metin temelli olduğunu doğruladı. Dört
kırpımın koordinatları ilk ajan tarafından yeniden oluşturulup ayrıca görsel
kontrol edildi. Koçluk taslağı kanonik altı aşama ve tur başına en fazla iki
kaynağa uyarlandı. Dışa aktarım şema kontrolünde 6/6 tur geçti; bu içerik
kalitesi veya öğretmen onayı değildir.

İkinci ajanın bağımsız pedagojik denetimi güncel revizyonu **reddetti**: üçüncü
tur, ilk dört tur kuralı içinde iki doğru olayı zafer ölçütüyle eşleştirerek
cevabı fiilen açığa çıkarıyor. Sonraki revizyon açık seçenek adı kullanmasa da
yalnız ölçütü karşılayan iki olaya ait kanıtları göstererek aynı cevabı dolaylı
biçimde belirginleştirdi ve yine reddedildi. Bu bulguya göre üçüncü tur, nötr
hatırlama sorusuna dönüştürüldü; kaynak kanıtı öğrenci denemesinden sonraki
geri bildirimde kullanılacak. Güncel prompt/durum uyumu ve sızıntı olmaması
ikinci ajan tarafından doğrulandı. Kullanıcı bu projedeki içerik onaylarını
öğretmen rolündeki ajanlara devretmiştir; üretici ajandan bağımsız ikinci ajan
incelemesi kabul kapısıdır, ayrıca insan öğretmen onayı beklenmez. Bu ajan
incelemesi, gerçek bir sınıf öğretmeninin insan değerlendirmesi olarak
raporlanmayacaktır. Bu nedenle bir grup kaynak ve koçluk incelemesini geçti;
ancak bu **1/120 adaydır**, üretim kümesi veya QLoRA-ready export değildir.
Taslak ve denetim kayıtları private
`agent-coaching-pilot-a/` ile `agent-coaching-pilot-b/` altında kalır.

Üretim verisi halen **120 grupluk hedefe ulaşmamıştır** ve Kaggle QLoRA
başlatılmamıştır. `question_derived_recall` kipi, yalnız üçüncü aşamadaki
kaynak alıntısız hatırlama sorusuna izin verir; kip kullanıldığında yeni kişi,
tarih veya olay bilgisi eklenmemesi istemde belirtilir. Kaynak bağlı açıklama
sonraki aşamalarda sürer. Bu istisna üretici ve bağımsız ajan incelemesiyle
onaylanır; diğer aşamalardaki kaynak zorunluluğunu gevşetmez.

## 17 Kasım 2026: Altı bölüm aday havuzu denetimi

Bağımsız ajan, sıkı kapsam havuzundaki 29 benzersiz metin sorusunun tamamında
soru transkripsiyonu ile PDF kırpımının eşleştiğini doğruladı. Kaynak kanıtı
kararları aday düzeyindedir: 17 doğrudan, 8 sınırlı çıkarım, 3 yetersiz ve 1
yanlış kanıt. Bölüm dağılımı 1.3: 6; 2.1: 9; 2.4: 4; 2.5: 4; 3.1: 4; 3.2: 2
sorudur. 3.2'deki iki doğrudan adayın kaynak/bölüm aralığı bayrakları vardır;
2.4'teki yanlış kanıt adayı dışlanır. Daha geniş 55 soru kapasite sayımı
görsel ve kanıt denetimini tamamlamamıştır; ayrıca 29 soru çifti yakın tekrar
olarak görsel doğrulama bekler.

Bu 29 soru eğitim veya runtime onayı değildir. Atom düzeyindeki alıntı
provenance kapısı toplu denetimde geçmedi (23 uyarı). İkinci ajan bunları 15
bölüm aralığı uyuşmazlığı (9 soru), 4 kırpım/alıntı sürekliliği ve 4 kısa
alıntının iddiayı destekleyip desteklemediğinin incelenmesi olarak ayırdı;
checksum, kimlik veya kopya kimlik uyuşmazlığı yok. Otomatik güvenli düzeltme
sayısı sıfırdır: bölüm/rol değişikliği uzman incelemesi, kırpım düzeltmesi
yeniden çıkarım ve görsel kontrol, kısa alıntı kararı anlamsal inceleme ister.
Kaynak kanıt atomlarının durumu `candidate_quote_verified_not_approved` olarak
kalır. İlk ek gruplar,
kesit/alıntı eşleşmesini ve soru-kanıt ilişkisini ayrı ayrı doğrulayarak
hazırlanacaktır. Böylece soru kırpımının doğru olması, kanıtın soruyu
desteklediği varsayımına dönüştürülmez.
