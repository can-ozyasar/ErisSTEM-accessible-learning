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
