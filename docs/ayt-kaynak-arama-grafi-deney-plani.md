# AYT Tarih kaynak arama ve kanıt grafiği: ölçüme dayalı uygulama planı

4 Kasım 2026. Bu belge, `yapilacaklarUNUTMAMAKICIN` içindeki fikirleri mevcut
AYT uygulaması ve özel pilot denetimleriyle karşılaştırır. Tasarım kararı ile
ölçülmüş sonuç ayrı tutulur. OGM soruları, MEB alıntıları ve cevap anahtarları
bu belgede yer almaz.

## Bugünkü durum ve kararın sınırı

Mevcut 10–12. sınıf MEB corpus'u bir kitap/bölüm ağacı ve 1.920 aday parça
taşıyor. Bunlar onaylı kanıt sayısı değildir. OGM pilotunda 115 OCR açısından
aday soru, bağımsız metin denetimi sonrasında 70 temiz, 20 kırpımla onarılabilir
ve 25 yeniden ayrılmalı olarak sınıflandı. Kelime örtüşmesi kapısından kalan
10 adayın ikinci ajan incelemesinde 1'i olası doğrudan kanıt, 9'u yeniden arama
olarak değerlendirildi; hiçbiri öğretmen onayı almadı. Bu sayılar bir retrieval
doğruluk oranı olarak yorumlanamaz.

Mevcut OGM öneri hattı BM25'i parçaları **tek tek** vererek çalıştırıyor.
IDF bu kullanımda corpus ayırt ediciliğini ölçmüyor. İlk beş harfi aynı olan
kelimeleri eşleştirmek ve soru kökü terimlerinde `%40` örtüşme aramak da
ilişkinin doğruluğunu ölçmüyor. Bu iki davranışın düzeltilmesi, yeni grafik veya
Rust çekirdeğinden önce gelir. Ayrıca yalnız 12. sınıfa bakmak, başka MEB
kitabındaki yardımcı kanıtları kaçırabilir. `ayt_evidence_composition.py` iki
kesitli köprü öneriyor; bu henüz insan tarafından doğrulanmış ilişki değil.

## Notlardaki fikirlerin uygulama karşılığı

| Fikir | Uygulama kararı ve denenecek iddia |
| --- | --- |
| Yaklaşık 200 sayfalık kitabı klasör/ağaç gibi düzenlemek | Fiziksel ağaç `kitap → ünite → bölüm → başlık → sayfa → paragraf/kesit` olur. Başlık yalnız aramayı yönlendirir; başka bölümdeki gerekli kanıtı kesin olarak dışlamaz. PDF okuma sırası, başlık ve koordinat hataları ayrı denetlenir. |
| Düğümler arası uzaklık | Tek bir kosinüs uzaklığı ilişki anlamına gelmez. Metin benzerliği, aynı varlık, bölüm yakınlığı ve zaman uyumu ayrı sinyallerdir. Grafik geçişi yalnız kaynaklı, türü doğrulanmış kenardan yapılır. İki kenardan uzun keşif ilk deneyde açılmaz. |
| Her düğüme ağırlık | Sabit bir “tarihsel önem” sayısı verilmez. Soruya göre kişi/olay/tarih eşleşmesi, kaynak kalitesi, ilişki türü ve onay ayrı özelliklerdir. Bunların ağırlıkları yalnız geliştirme sorularında ayarlanır ve hata analiziyle açıklanır. |
| Beyindeki bilgi bağlantıları | Öğrencinin hatırlama ve ilişki kurmasına uygun kısa ilişki kartları tasarlanır. Grafiğin insan beyninin çalışma biçimini temsil ettiği iddia edilmez; pedagojik etki ayrı kullanıcı ölçümü gerektirir. |
| Aranacak yerin belirgin olması | Soru kökü ve şık iddiaları kişi, olay, tarih, yer, sıralama, neden ve karşıtlık ihtiyaçlarına ayrılır. Sistem önce bölüm/varlık/zaman adaylarını toplar, eksik iddia varsa diğer bölüm ve sınıf kitaplarına genişler; neden genişlediğini kaydeder. |
| C++/Rust arama çekirdeği | Yerel ortamda Rust araç zinciri bulunmadığı, C++ derleyicisi bulunduğu için ilk derlenmiş aday C++ oldu. Python ile aynı indeks, sorgu ve sonuç kimliklerinde karşılaştırılır. Kalite, p50/p95 süre, bellek, kurulum ve bakım maliyeti birlikte değerlendirilir; `%20` veya benzeri keyfî iyileşme şartı yoktur. Rust için aynı sözleşme daha sonra kullanılabilir. |
| Sınıflar, nesneler, JSON ve veri temsili | Python veri modelleri ve sürümlü JSON şeması insan incelemesi/manifest için korunur. Üretim indeksinde metin, ters indeks, vektör dizileri ve grafik komşulukları ihtiyacına uygun ayrı yapılar olabilir. Nesne veya JSON biçimi tek başına LLM doğruluğunu artırmaz. |
| Bilgiyi embedding ile, token token saklamak | Paragraf embedding'i aday getirme; token düzeyinde geç etkileşim, yeniden sıralama adayıdır. 1.920 adaylık havuzda BM25, dense ve token düzeyi yöntemler aynı sorularda kıyaslanır. Depolama, indeksleme ve yerel p95 dahil edilmeden yöntem seçilmez. |
| NotebookLM gibi kaynakla çalışma | Kaynağa geri dönme, alıntıyı açma ve farklı belgeler arasında gezinme deneyimi incelenir. Kamuya açık belgeler ürün davranışını anlatır; iç mimariyi bildiğimiz varsayılmaz. Açık kaynak GraphRAG yalnız deney fikri sağlar, doğruluk garantisi vermez. |
| Makale/CV değeri | Kullanılan teknoloji sayısı yerine sürümlü veri, doğru ölçüm, karşılaştırma, başarısızlık analizi ve erişilebilir çalışan ürün raporlanır. Tek ajan kararı veya küçük örneklem başarı yüzdesi olarak sunulmaz. |

## Kaynak modeli ve arama sırası

1. **Belge ağacı:** PDF checksum'ı, baskı/sürüm, sayfa koordinatı, başlık yolu ve metin sırası tutulur. Soru/etkinlik/görsel açıklaması/bozuk OCR ders kanıtı adayıyla karıştırılmaz. Kısa atomun yanında ait olduğu paragraf korunur; olumsuzluk veya zamir bağlamı kaybolursa atom tek başına kullanılmaz.
2. **İddia planı:** Soru kökü ile her şıkkın sınanacak iddiaları ayrılır. Şık doğru kabul edilmez; cevap anahtarı arama sorgusuna ve öğrenci LLM'ine girmez. Her iddia için gereken ilişki ve kanıt rolü kaydedilir.
3. **Aday getirme:** Onay/kalite filtresi ayrı kalır. BM25, tüm uygun corpus üzerinden IDF hesaplar. Başlık/varlık/zaman yönlendirmesi sonuçları önceliklendirir; birinci arama boş veya yetersizse komşu bölüm ve 10–12. sınıf kitaplarına kontrollü genişler. Dense, RRF ve token düzeyi sıralama ayrı deney kollarıdır.
4. **Kaynaklı ilişki:** Kişi–olay, tarih–olay, yer–olay, kronoloji ve neden–sonuç farklı kenar türleridir. Her kenarın iki ucu, ilişki fiili, birebir alıntısı ve PDF kırpımı bulunur. Ortak isim veya aynı dönem tek başına ilişki kurmaz. Farklı sayfalardaki iki onaylı tarih üzerinden sıralama yapılabilir; sıranın nedensellik gösterdiği varsayılmaz.
5. **Kanıt demeti:** Bir sorunun tüm cevabı aynı kısa atomda aranmaz. `primary`, `relation`, `context`, `contrast` rolleri gerektiğinde birden fazla onaylı alıntıyla temsil edilir. Demet iddia kapsamasını ve eksik ilişkiyi açıkça taşır. Üst sınır model bağlamı ve öğrenci kartları için ayrıca ölçülür; kaynak sayısı tek başına kalite hedefi değildir.
6. **Yayın sınırı:** Ajan önerisi öğretmen onayı değildir. PDF kesitiyle onaylanmış alıntı/kenar ve güncel checksum olmadan öğrenci RAG'ına veya QLoRA dışa aktarımına geçilmez. Kaynak değişince ilgili indeks, kenar, demet ve embedding geçersizleşir.

## Deney, karar ve yayın kapısı

Önce mevcut pilotun OCR ve kaynak kalite sorunları ayrı düzeltilir. Her sorunun
gerekli iddiaları, kabul edilebilir kanıt kümeleri, çelişkili/yanlış kanıtları
ve gerçekten kaynak bulunmayan durumları insan incelemesiyle etiketlenir.
Önceden yöntem ayarlamak için kullanılmış 18 örnek kapalı test sayılmaz.
Soru grupları ve yakın kopyalar bölünmez; 120 soru/720 koçluk örneği hedefindeki
84/18/18 ayrımı ancak havuz ve onay yeterliyse uygulanır.

Karşılaştırma sırası: düzeltilmiş BM25 → başlık/varlık/zaman yönlendirmesi →
dense/RRF → kaynaklı grafik genişletmesi → gerekirse token düzeyi yeniden
sıralama. Her kol aynı sorgu, kaynak sürümü ve öğretmen etiketleriyle ölçülür.
`Hit@k` (en az bir doğru kanıt), gerçek `Recall@k` (bulunan doğru kanıtların
payı), gerekli iddia kapsaması, tam demet başarısı, MRR, yanlış kanıt,
gerekli/gereksiz çekimserlik ve p50/p95 süre ayrı raporlanır. Kaynak etiketi
bilinmeyen aday “yanlış” veya “doğru” sayılmaz; ayrı belirsiz olarak gösterilir.

Karar, tek bir kazanım yüzdesiyle verilmez. Öğrenciyi yanıltan kaynak ve erken
cevap ifşası için güvenlik kapısı serttir; aday bu hataları artırırsa ürün yolu
açılmaz. Bunu geçen yöntemler için kalite artışı, güven aralığı, gecikme,
RAM/VRAM, indeks boyutu ve bakım maliyeti birlikte değerlendirilir. Örneğin
Rust ile ölçülen `%10` p95 iyileşme, gerçek kullanımda ilk ses gecikmesine
katkı sağlıyor ve bakım maliyeti makulse değerli olabilir. `%20` artış bile
sonuç sırası değişmiş veya kaynak hatası artmışsa yeterli değildir. Mevcut
Eski `+0,05 / +0,03 / ≤1 s` hibrit eşikleri v2 sözleşmesinde kaldırıldı.
Yeni kapı, yanlış kanıt ve çekimserlikte gerilememeyi, ölçülmüş yararı,
yerel gecikme incelemesini ve açık öğretmen kararını ister. Bir adayın
tek bir yüzdede üstün olması otomatik ürün kabulü değildir.

Özel sonuçlar private alanda kalır. Mimari ekranı aday, ajan incelemesi ve
insan onayını ayrı gösterir. Öğrencinin ilişki kartları klavye, ekran okuyucu
ve yerel TTS ile gezilebilir. Dönem, graf ve vektör deneyleri öğrenci yoluna
yalnız kabul edilen kaynaklardan girer. QLoRA, yeterli onaylı soru ve koçluk
örneği oluşmadan başlatılmaz.

## Uygulama önceliği

1. BM25 corpus hatasını ve retrieval ölçüm adlarını/formüllerini düzelt; önceki raporlara yeni metrik adıyla sessizce anlam yükleme.
2. 70 temiz OCR kaydından ayrılmış, insan kaynak incelemesi yapılmış küçük geliştirme kümesini oluştur. Kaynak açığı ile retrieval hatasını ayır.
3. Bölüm ağacı + iddia planı + kontrollü kitaplar arası genişleme deneyini çalıştır. Metin/kesit bağlamı kaybını PDF üzerinden denetle.
4. Kaynaklı iki kesitli ilişkileri değerlendir; gereken iddiaların tamamı doğrulanmadan demeti yayınlama. Mevcut rol başına tek kaynak şemasını sürümleyerek genişlet.
5. Dense/token düzeyi/Rust adaylarını gerçek katkıları ölçüldükçe ekle. Kabul edilen yolu koç API'sine ve erişilebilir kaynak kartlarına bağla.

İlgili teknik durum: [kaynak bağlı mimari](kaynak-bagli-bilgi-grafi-mimarisi.md),
[kanıt demeti sözleşmesi](kanit-demeti-ve-iliski-grafi.md),
[hibrit deney protokolü](tarih-rag-hibrit-deney-protokolu.md).
Yöntemleri incelemek için birincil kaynaklar: [ColBERT token düzeyinde geç
etkileşim](https://arxiv.org/abs/2004.12832), [Microsoft GraphRAG yerel
arama belgeleri](https://github.com/microsoft/graphrag/blob/main/docs/query/local_search.md)
ve [Google'ın NotebookLM kaynak deneyimi açıklaması](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-discover-sources/).

## 4 Kasım uygulama ve ölçüm kaydı

- OGM özel arama v3, uygun 10–12. sınıf parçalarını tek BM25 corpus'unda
  puanlıyor; kitap ve bölüm önceliği sonrası gerektiğinde genişliyor. Beş
  harf/%40 örtüşme artık onay veya eleme kapısı değil, inceleme sinyali.
- 70 temiz OCR sorusunun hepsinde öneri var; 14'ü bölüm dışına genişledi.
  Bu, 70 soruya doğru kanıt bulunduğu anlamına gelmiyor. Önceki 18 sorunun
  bağımsız ajan denetiminde doğrudan Hit@3 sayısı 2'den 3'e çıktı; 54 kartın
  4'ü doğrudan, 20'si kısmi, 30'u ilgisiz. Sınıflar arası genişlemede bu
  örneklem için doğrudan kazanım yok. Kaynak onayı sıfır.
- Hazırlanmış Python BM25 indeksi ve yalnız seçilen kesitlerde tanı sinyali
  hesaplama, aynı 70 sorguda ilk üç sıralamayı birebir korudu. Yerel kuyruk
  p50/p95 süresi yaklaşık 121/223 ms'den 4,5/7,2 ms'ye indi. Bu ölçüm
  yalnız aday önerme süresidir; PDF, LLM ve TTS dahil değildir.
- Deneysel C++ puanlayıcı, 424 uygun parça ve 70 sorguda Python ilk üç
  sırasıyla 70/70 eşleşti. Saf puanlama p95: hazırlanmış Python yaklaşık
  1,17 ms, C++ yaklaşık 0,83 ms. C++ derleme, aktarım ve işletim
  maliyetleri bu saf süreye dahil değil; bu sonuç ürün kullanım kararı değil.
- 70 soru için private PDF kesit paketi ve insanın dolduracağı Gold şablonu
  hazır. Gold incelemesi 0/70 olduğundan değerlendirme aracı bilinçli olarak
  bir doğruluk yüzdesi üretmiyor. Kısa cümlede kişi/ilişki ipucu için yapılan
  basit deneme 54 denetlenen kartta doğrudanı ayıramadı; sıralamaya alınmadı.
- Hibrit metrik sözleşmesi v2'de Hit@3 ile gerçek Recall@3 ayrıldı.
  Aynı role birden fazla öğretmen onaylı kaynak bağlanabilir; koç onaylı
  demetteki kaynak sırasını korur. Hibrit/QLoRA öğrenci yoluna açılmadı.

İnceleme paketi yalnız yerelde
`data/private/ogm-ayt-tarih-v1/teacher-review-pack-global-v3/index.html`
adresindedir. Altın şablon
`data/private/ogm-ayt-tarih-v1/pilot-retrieval-gold-template-v1.json`
dosyasında soru başına PDF kesiti kontrolü, kaynak kararı, kapsam taraması ve
inceleyen kişi bekler. Agent ön incelemesi bu alanları otomatik onaylamaz.
Şablon gerçekten doldurulduğunda sürüm ve kanıt kontrolleri şu komutla yapılır:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.ogm_ayt_retrieval_gold evaluate \
  --queue data/private/ogm-ayt-tarih-v1/pilot-evidence-queue-global-v3.json \
  --gold data/private/ogm-ayt-tarih-v1/pilot-retrieval-gold-template-v1.json \
  --corpus data/private/yks-ayt-source-v1/multi-history-rag-v2.json \
  --output data/private/ogm-ayt-tarih-v1/pilot-retrieval-eval-reviewed-v1.json
```

Bu yalnız private değerlendirme üretir; kaynak onayı, öğrenciye açma veya
QLoRA eğitimi başlatma işlemi değildir.
