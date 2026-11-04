# Tarih RAG: kanıt kalitesi ve hibrit getirme protokolü

**Sürüm notu (4 Kasım 2026):** Aşağıdaki `+0,05 / +0,03 / ≤1 saniye`
eşikleri v1 deney politikasına aittir. Yeni ürün kabulü
[AYT kaynak arama planındaki](ayt-kaynak-arama-grafi-deney-plani.md) ve
`history-rag-hybrid-v2` sözleşmesindeki gerçek Recall@3, Hit@3, tam kanıt
kapsamı, yanlış kanıt, süre ve insan incelemesiyle değerlendirilir. Eski
raporların `recall_at_3` alanı yeni anlamıyla kullanılamaz.

## Sınır

PDF, tam MEB metni, soru bankası, cevap anahtarı, öğrenci verisi ve kapalı test Kaggle'a yüklenmez. Kaggle girdisi yalnız kısa öğretmen-onaylı kanıt, bölüm, parça kimliği ve altın kanıt kimliğidir. Girdi denetleyicisi cevap anahtarı alanlarını reddeder.

## Akış

1. Öğretmen PDF kırpımını inceleyerek genel kaynak onayı verir. Checksum, sayfa, koordinat, bölüm ve OCR/görsel/yönerge uyarıları saklanır.
2. Öğretmen soru için gerekli rollerdeki onaylı parçaları ve bunların sırasını seçer. Çalışma anındaki demet en çok dört parça taşıyabilir; QLoRA dışa aktarımında en çok iki kısa alıntı kullanılır. Bu kayıt olmadan öğrenci koçu ve QLoRA dışa aktarımı kaynak alamaz.
3. Kaggle'da aynı geliştirme sorularında BM25, BGE-M3 dense ve `k=60` RRF ölçülür. Qwen3-Reranker-0.6B yalnız RRF top-k üzerinde, RRF ilk kapıyı geçerse denenir.
4. Yerel hibrit yapıt PDF checksum'ı veya onay kümesi değiştiğinde geçersizdir; kabul kararı olmadan etkinleşmez.

## Kabul kapısı

v2 kabulü, aynı geliştirme soruları ve kaynak sürümünde gerçek Recall@3,
MRR@3 ve tam kanıt kapsamında gerileme olmamasını; yanlış kanıt sayısı/oranı
ile gereksiz cevap verme oranında artış olmamasını ister. Adayın ölçülmüş
yararı ve yerel gecikme maliyeti öğretmen incelemesiyle kaydedilir. Gecikme
artıyorsa ürün bütçesi açıkça belirtilir. Bu koşullar otomatik öğretmen
onayı yerine geçmez.

Rapor: Recall@1/@3, MRR@3, nDCG@3, kanıt kapsamı, yanlış kanıt oranı, doğru yanıtsız kalma, p50/p95, GPU/model/sürüm/seed ve hata örnekleri.

Kaynaklar: [BGE-M3 belgeleri](https://github.com/FlagOpen/FlagEmbedding/blob/master/docs/source/bge/bge_m3.rst), [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [RAG değerlendirme derlemesi](https://link.springer.com/article/10.1007/s42979-026-05134-x).

## AYT Tarih-2 kontrollü pilot — 29 Ekim 2026

Bu pilot, ürün kalitesi veya model başarısı sonucu değildir. 2022–2026'ya
koordinatla bağlanmış 27 resmi AYT Tarih-2 sorusunda, aynı checksum bağlı
10–12. sınıf corpus'undan BM25 önerilerinin ilk üçü bağımsız bir tarih
öğretmeni rolündeki agent tarafından incelendi. Cevap anahtarı okunmadı.
Agent, öğretmen onayının yerine geçmez; bu nedenle sonuçlar yalnız öncelik
kuyruğu olarak `data/private/yks-ayt-source-v1/ayt-agent-pre-review-v1.json`
dosyasında tutulur.

| İlk üç öneri içindeki ön inceleme sonucu | Soru sayısı |
|---|---:|
| En az bir `primary` kanıt adayı | 9 |
| Yalnız `context` / `relation` / `contrast` | 8 |
| Yetersiz | 10 |

Bu dağılım, mevcut BM25 önerilerinin ürün ya da QLoRA verisi olarak kabul
edilemeyeceğini gösterir. Özellikle tarih metodolojisi ve ilk Türkler
sorularında 10–12. sınıf corpus'unda kapsam deliği vardır; hedefli yeniden
getirme yapılmadan önce 9. sınıf kitabının ayrı checksum sürümü eklenmeli ya
da bu sorular ilk ürün kapsamından çıkarılmalıdır.

### 9. sınıf kapsama deneyi — 29 Ekim 2026

Bu boşluğu sınamak için 9. sınıf kitabı, çalışmakta olan 10–12. sınıf
corpus'una eklenmedi. Aynı 27 bağlı soru için yalnız inceleme amaçlı ikinci
bir corpus üretildi: temel corpus checksum'ı
`6581a0ecc45b10801dae723b6580f90de801cd0eb910939d440750f3c1ff33ce`,
deney corpus checksum'ı
`df9704f4fdefb52f4c9c0c65b0e1c31503bf7afffd421234c2d2e0d8ce94fa67`.

| Karşılaştırma sonucu | Soru sayısı |
|---|---:|
| İncelenen bağlı soru | 27 |
| İlk önerisi değişen | 1 |
| İlk üçte 9. sınıf adayı alan | 2 |

Bu sayılar doğruluk veya kalite sonucu değildir. İki değişikliğin altılı PDF
kırpım paketi private alanda oluşturuldu; her aday için kaynak rolü ve
PDF-görünüm doğrulaması yapılmadan 9. sınıf parçası öğrenci RAG'ına, altın
değerlendirme kümesine veya QLoRA verisine giremez. Deney sonucu, 9. sınıfı
tüm corpus'a koşulsuz katmak için yeterli kanıt oluşturmaz.

Bu iki karttaki bağımsız ön incelemede `primary=0`, `context=2` ve
`insufficient=4` bulundu. Bu sonuç öğretmen onayı değildir; ancak geniş
sorgunun bağlam getirdiğini, zorunlu kişi–olay ve kavram ilişkilerini
kanıtlamadığını gösterir. Bu nedenle bir sonraki deneyde bütün soru için tek
BM25 sırası yerine öğretmen denetimli zorunlu ilişki maddeleri kullanıldı.
Her maddeyi karşılayan bir PDF parçası bulunamazsa araç
`insufficient_evidence` döndürür.

Kaynak PDF taramasında kimi gerekli kavramların kitapta bulunup mevcut
inceleme dizinine girmediği görüldü: kitap içi tırnaklı kaynak alıntıları
eski filtreden önce eleniyordu. Çıkarım politikası `source-type-v3` olarak
sürümlendi. Bu bloklar artık yalnız `manual_review` statüsüyle private PDF
kırpım keşfine girebilir; varsayılan retrieval, öğrenci RAG'ı ve QLoRA yolu
onları hâlâ dışarıda tutar. Ayrıca çoklu kitap corpus checksum'ı artık yalnız
PDF checksum'ından değil, kaynak indeksinin tamamından da üretilir. Böylece
çıkarım politikası değiştiğinde eski retrieval veya embedding yapıtı geçerli
sayılmaz.

İlk zorunlu-kısıt deneyi, eski Türk devlet/toplum kavramı için tüm maddeleri
karşılayan sekiz *manual-review* alıntı adayı buldu; bunlar için sekizli PDF
kırpım paketi üretildi. Türgiş–Karluk–Talas ilişkisi için gerekli üç maddeyi
birlikte karşılayan aday bulunmadı ve sistem çekimser kaldı. İlk bulgu ürün
kalitesi sonucu değildir: yalnız insan PDF incelemesinin hangi kaynakları
kontrol edeceğini daraltır.

Ham-PDF geri dönüşünün bağımsız ön incelemesi, 9. sınıf s.198'deki alıntının
`hatun → kağanın eşi / devlet işlerinde rol` ilişkisini; aynı sayfadaki başka
alıntının da `otağ → hükümdarlık sembolü` ilişkisini doğrudan taşıdığını
buldu. Kurultay, kut ve kurgan için de ayrı doğrudan adaylar var. Ancak hiçbir
incelenen parça `otağ = hükümdarın çadırı` eş anlamını açıkça vermiyor.
Koç bu nedenle öğrenciyi hükümdarlık ilişkisini fark etmeye yöneltebilir;
bu eş anlamı kaynaklı kesin bilgi veya cevap olarak söyleyemez. Alıntıların
hepsi `source_type=quoted_source` ve `manual_review` olarak kalır; insan
öğretmen PDF kırpımı onayı olmadan allowlist, altın veri, öğrenci RAG'ı ya da
QLoRA için kullanılamaz.

Bir sonraki geçerli ölçüm akışı şöyledir:

1. Her kart, PDF kırpımı üzerinden insan öğretmen tarafından `primary`,
   `context`, `relation`, `contrast` veya `insufficient` diye işaretlenir.
2. İnsan onaylı kartlar, `ayt-retrieval-gold-v1` şablonuna yazılır. `primary`
   olmadan veya PDF kırpımı kontrol edilmeden değerlendirmeye alınmaz.
3. İlk 18 dengeli aday, model seçmeden önce öğretmen tarafından konu ve
   ilişki türü sızıntısı denetlenerek geliştirme ve kapalı test olarak
   ayrılır. Bu küçük pilotun sonucu ürün kabulü ya da genellenebilir istatistik
   olarak sunulmaz.
4. BM25, ardından dense/RRF/reranker adayları aynı kapalı kaynak kimliklerinde
   ayrı ayrı `Recall@3`, `MRR@3`, `nDCG@3`, top-1 yanlış kanıt oranı,
   çekimser kalma ve p50/p95 gecikme ile raporlanır. Bu metrikler tek skorda
   birleştirilmez.

`Recall` kanıtın gelmesini, `MRR` ilk doğru kanıtın sırasını, `nDCG` ise
birden fazla rolün sıralı yararını ayırır. Ancak RAG'da üst sıradaki ilgisiz
kanıtın üretimi bozabilmesi nedeniyle top-1 yanlış kanıt oranı ayrıca
izlenir. Bu ayrım, [dense retrieval değerlendirme derlemesindeki](https://doi.org/10.1145/3637870)
coverage/ranking ölçütleriyle ve [RAG retrieval değerlendirmesinin klasik
metrik sınırlılıklarına ilişkin çalışmayla](https://aclanthology.org/2026.eacl-long.391/)
uyumludur.

Şablon ve taban çizgi komutları:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.ayt_retrieval_eval template \
  --questions data/private/yks-ayt-source-v1/ayt-tarih2-candidates-v2.json \
  --proposals data/private/yks-ayt-source-v1/ayt-evidence-proposals-v2.json \
  --output data/private/yks-ayt-source-v1/ayt-retrieval-gold-template-v1.json

# Yalnız PDF kırpımı kontrol edilmiş, insan öğretmen kararları yazıldıktan sonra:
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.ayt_retrieval_eval evaluate-bm25 \
  --gold data/private/yks-ayt-source-v1/ayt-retrieval-gold-reviewed-v1.json \
  --questions data/private/yks-ayt-source-v1/ayt-tarih2-candidates-v2.json \
  --proposals data/private/yks-ayt-source-v1/ayt-evidence-proposals-v2.json \
  --corpus data/private/yks-ayt-source-v1/multi-history-rag-v2.json \
  --output data/private/yks-ayt-source-v1/ayt-retrieval-bm25-v1.json
```
