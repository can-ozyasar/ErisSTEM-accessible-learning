# AYT Tarih kilitli retrieval baseline kaydı

Bu kayıt, 24 kayıtlı dondurulmuş retrieval splitinde yerel BM25 atom aramasının
tekrar üretilebilir başlangıç ölçümüdür. İnsan öğretmen değerlendirmesi veya
ürün kabul raporu değildir.

| Ölçüm | Sonuç |
| --- | ---: |
| Sorgu sayısı | 24 |
| Corpus atomu | 3.011 |
| Birebir yinelenen atom tekilleştirmesi | 1 |
| Kaynak-aday atomu Recall@1 / Recall@3 | 1.0000 / 1.0000 |
| MRR@3 / nDCG@3 | 1.0000 / 1.0000 |
| p50 / p95 yerel sıralama gecikmesi | 4,59 ms / 5,88 ms |
| Top-3 insan etiketsiz atom | 48 |
| Runtime veya QLoRA için etkinleştirilen kayıt | 0 |

## Geçerli yorum

Her aday soru, oluşturulurken bir kaynak atomuna bağlıydı. Bu baseline o
bağın bütün atom corpus'u içinde bulunup bulunamadığını ölçer. Soru şıkları
aynı kaynaktan üretildiği için yüksek sonuç beklenir; bu nedenle sayı, gerçek
öğrenci sorularında kanıt yeterliliği ya da pedagojik doğruluk göstergesi
değildir.

Top-3'te hedef atom dışındaki 48 sonuç için insan `wrong_evidence` veya
`relevant` etiketi yoktur. Bunlar yanlış sayılmadı; `unjudged` olarak korundu.
Bu tek başına dense, RRF veya reranker seçmek için yetersizdir.

## İzlenebilirlik

- Dondurulmuş split: `data/private/ayt-history-exam/candidate-split-v1.json`
- Baseline çıktısı: `data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json`
- Corpus checksum: `6a286b9387faefad5a3f87afe536c4cf1247589e683ee218787113d8710a4440`

Bir sonraki değerlendirme yalnız kaynak kırpımıyla doğrulanmış kanıt ve
olumsuz kanıt etiketleri eklendikten sonra, bu sabit split üzerinde aynı
metric sözleşmesiyle yapılmalıdır.

## Takip: ortak top-3 etiket havuzu

Mevcut artefaktlar ve değerlendirme kodu 25 Kasım 2026'da yeniden çalıştırılıp
aynı çıktıları üretti. Bu takip karşılaştırması, soru kırpımı doğrulaması
bekleyen 120 özgün-yazım araştırma adayını kullanır; bunlar aktif öğrenci
paketindeki 81 lisanslı/AI-kaynak-incelemeli soruyla aynı soru kümesi değildir.
Araştırma adaylarının `72 development / 24 retrieval_test / 24 system_acceptance`
splitini kullanır; 24 sorgu kimliğinin tamamı kilitli `retrieval_test` splitine
aittir. Etiket havuzu üç yöntemin top-3 PDF kartlarının birleşimidir; iki
bağımsız cevap-anahtarı-görmeyen AI incelemesi 4 etiket çelişkisini çözdü, açık
inceleme gerektiren çelişki kalmadı. Bu bir insan öğretmen onayı veya tam-corpus
relevance değerlendirmesi değildir.

Split manifesti 63 kaynak-bölüm grubu aynı splitte tutar ve farklı bölümlerde
birebir aynı normalize soru kökü bulmaz. Ayrı bir token/karakter-4-gram Jaccard
tarama 4.032 splitler-arası çiftten 99'unu gevşek advisory eşiğinde, hiçbirini
katı near-duplicate eşiğinde işaretledi. AI stem incelemesinde en yüksek skorlu
10 çiftte aynı genel “kaynağa göre” soru kalıbı, farklı hedef kavramlarla
eşleşti; belirgin aynı-soru kopyası görülmedi. 81 aktif soru ile 120 araştırma
adayı arasındaki 9.720 çiftte exact imza veya advisory eşik eşleşmesi çıkmadı.
Bu AI/lexical tarama anlamsal eşdeğerliği kanıtlamaz; soru-kalite veya insan
uzman incelemesi yerine geçmez.

| Yöntem | Recall@1 | Recall@3* | MRR@3 | nDCG@3 | Top-1 yanlış / yetersiz etiket | p50 / p95 (ms)** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0,8958 | 0,9375 | 1,0000 | 0,9516 | 0 / 0 | 28,07 / 40,73 |
| Qwen3 Embedding 4B | 0,8958 | 0,9792 | 1,0000 | 0,9839 | 0 / 0 | 130,94 / 159,00 |
| RRF (BM25 + dense) | 0,8958 | 0,9792 | 1,0000 | 0,9772 | 0 / 0 | 162,51 / 204,27*** |

\* Recall@3 burada yalnızca ortak top-3 havuzunda etiketlenmiş kanıtlar içindeki
geri-getirimi ölçer; full-corpus Recall değildir. “Yanlış/yetersiz” değerleri
AI etiket ve adjudication sonuçlarına dayanır.

\** Qwen sıralaması Tesla T4'te ölçülmüştür. BM25 ve dense sütunları kendi
ölçülen sorgu aşamalarının gecikmeleridir; bu değerler yerel ürün p95'i değildir.

\*** RRF p50/p95, her sorgudaki BM25 + dense query + fusion sürelerinin toplam
dağılımıdır. Yalnız fusion aşaması 3,56 / 4,23 ms'dir; bu tek başına RRF
uçtan-uca gecikmesi gibi sunulmaz. Corpus embedding'i önceden hesaplanmıştır.

Dense ve RRF, bu sınırlı havuzda BM25'e göre Recall@3'ü 0,0417 artırdı; Qwen
dense nDCG@3'te en yüksek değeri verdi. Ancak aktif 81 soruluk pilotun normalize
edilmiş soru kökü imzalarıyla bu ayrı 120 aday kümesi arasında birebir imza
örtüşmesi 0'dır; bu semantik yakın kopya yokluğunu kanıtlamaz. Dolayısıyla bu
sonuçlar 81 aktif soruya doğrudan retrieval başarımı değildir. Öğrenci
çalışma yolunda retrieval açılmadı; soru başına onaylı kanıt demeti ve güvenli
çekimserlik korunur.

## Takip değerlendirmesi provenance

- Bölünme manifesti: `data/private/ayt-history-exam/candidate-split-v1.json`
  SHA-256 `5f5bc278befdd6bf9a24b2ccf39828e5ff9c5d25849cdf632eaddeaada680cfd`
- Araştırma aday paketi: `data/private/ayt-history-exam/original-question-candidate-pack-v2.json`
  SHA-256 `79dc571a1bd2e6eab60c6c8d0748023cbc998a7cd3bf010e4ec067bed4e8b703`
- Calibration input: `data/private/ayt-history-exam/qwen-dense-rrf-calibration-v1/input.json`
  SHA-256 `aff327d7650bc695b6f49121ebd3783437fc0826fdb6845734cd9eb119f0f56f`
- Kaggle ranking: `data/private/kaggle-notebook-outputs/muhammedcanozyasar/eristem-ayt-history-qwen-dense-rrf-run-v1/ayt-qwen-retrieval-rankings-v1.json`
  SHA-256 `4aa7ca3c9bfeff2fd743acb99ea8a13a38d94f02c1d5b40babc5602a987de22f`
- Pooled evaluation: `data/private/ayt-history-exam/qwen-dense-rrf-calibration-v1/pooled-top3-evaluation-v1.json`
  SHA-256 `5a7c8d9553c9917c8c5e3e33238906f22a36267e774e16f8aa84dd563167dcee`
- Validation checksum: `047de6d276e31679390166f9165bf66a5d7c441ff8a8ea54f8512f642b6f7668`
- MEB corpus checksum: `6a286b9387faefad5a3f87afe536c4cf1247589e683ee218787113d8710a4440`
- Kaynak soru aday kümesi checksum: `69a9e5884deddaa2cf145022f0a1d343ef84505b4a2f16c22e391c2424d9a70a`

Çıktıların doğrulama/evaluation scriptleriyle birebir tekrar üretimi doğrulandı;
runtime ve QLoRA kapalıdır.

## Aktif 81 soruluk pakette BM25 tanı ölçümü

25 Kasım 2026'da mevcut 81 soruluk paket için hem PDF-kırpım metin denetimi hem
retrieval temsilleri yeniden ölçüldü. PDF denetiminde 165 kanıt parçasının
hiçbiri token eşleşme eşiğinin (%90) altında kalmadı; minimum 0,9167 ve medyan
1,0'dır. Bu, kaynak metni/bbox eşleşme kontrolüdür; tarihsel doğruluk veya
öğretmen onayı değildir.

BM25 tanı testi, aynı dört MEB kitabının 2.991 bağlam parçası ve 3.012 kanıt
atomuyla çalıştı. “Gold” etiketi, aktif paketteki primary kanıtın aynı kaynak
ve sayfada bbox alanının en az %80'ini örten adaydır; insan relevance etiketi
değildir. Metrikler tüm 81 soruyu payda alır; bbox ile eşleşmeyen kanıt
retrieval başarısızlığı sayılır.

| Tek indeks / sorgu | N | Eşleşebilir kanıt | R@1 | R@3 | MRR@3 | p50 / p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bağlam parçası, yalnız kök | 81 | 77 | 0,2469 | 0,4444 | 0,3374 | 5,96 / 8,67 |
| Bağlam parçası, kök + şıklar | 81 | 77 | 0,3951 | 0,6667 | 0,5103 | 6,53 / 8,83 |
| Kanıt atomu, kök + şıklar | 81 | 55 | 0,3333 | 0,4938 | 0,4012 | 4,89 / 6,28 |

Şıkları sorguya katmak geri-getirimi artırdı; konu alanını eklemek ek fayda
sağlamadı. Bu aktif pakette atom indeksi tek başına daha az kanıt bbox'ıyla
eşleşti. Bununla birlikte birincil kanıtlardan bir örnekte atom indeksi kaynağın
ilgili bölgesini kapsarken bağlam parçası kapsamadı. Kaynak-kırpım denetiminin
geçmesi ve farklı indeks kapsaması, sorunun kaynak alıntısı hatalı demek için
yeterli kanıt olmadığını gösteriyor.

| Sabit top-3 bütçeli birleşim | Havuz | R@1 | R@3 | MRR@3 | p50 / p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bağlam-parçası baseline | 2.991 | 0,3951 | 0,6667 | 0,5103 | 6,53 / 8,83 |
| Atom + bağlam, ham | 6.003 | 0,4198 | 0,5679 | 0,4815 | 12,36 / 16,48 |
| Atom + bağlam, tam metin tekilleştirme | 4.197 | 0,4198 | 0,6296 | 0,5123 | 8,42 / 11,59 |
| RRF, indeks başına top-20 → top-3 | 6.003 | 0,2840 | 0,4198 | 0,3416 | 12,24 / 16,53 |

Birleşik, deduplikasyonlu veya RRF düzenlerinden hiçbiri bağlam parçası
baseline'ını geçmedi; bu nedenle hiçbiri öğrenci ürün yoluna alınmamalı. Öğrenci
akışında soru başına sürümlenmiş, denetlenmiş kanıt demeti ve kanıt yetersizse
çekimserlik korunur. Bu ölçüm aktif paket üzerinde kör olmayan bir tanıdır;
BM25'in tüm kapsamlı MEB corpus'undaki insan relevance başarımı değildir.
Gecikmeler yerel AMD Ryzen 7 5700U, Python 3.12.3 makinesinde ölçüldü; kullanıcı
cihazı veya servis p95'i olarak yorumlanamaz.

Tekrarlanabilir evaluator:
apps/api/app/pipeline/diagnose_active_ayt_pack_retrieval.py
Özel veri girdisi: data/private/ayt-history-exam/ogm-ai-reviewed-local-pilot-v2.json
Kaynak corpus: data/private/ayt-history-exam/multi-history-rag-v3.json
Rapor: data/private/ayt-history-exam/active-pack-bm25-diagnostic-v1.json
