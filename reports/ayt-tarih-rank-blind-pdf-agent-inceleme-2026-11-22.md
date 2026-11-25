# AYT Tarih sıralama-kör PDF ajan incelemesi

Bu çalışma, kilitli 24 retrieval sorusunun BM25 top-3 kartını PDF kesitleriyle
birlikte kaynak-sınırlı bir tarih-kanıt ajanına inceletir. İnsan öğretmen
değerlendirmesi veya ürün kabulü değildir.

| Ölçüm | Sonuç |
| --- | ---: |
| Kilitli soru / PDF kartı | 24 / 72 |
| Ajan `relevant` / `wrong` / `insufficient` kartı | 27 / 27 / 18 |
| Ajanın `sufficient` bulduğu soru | 24 / 24 |
| Pool-limited Recall@1 / Recall@3 | 0,9375 / 1,0000 |
| Pool-limited MRR@3 / nDCG@3 | 1,0000 / 0,9967 |
| İncelenmiş sonuçlarda yanlış kanıt oranı | 0,5000 |
| Etiketsiz (`insufficient`) çekim | 18 |
| Ajan çağrısı p50 / p95 gecikmesi | 2.070,30 ms / 2.457,07 ms |
| Cevap anahtarı / çözüm / öğrenci verisi erişimi | Hayır / Hayır / Hayır |
| İnsan onayı / runtime / QLoRA etkinleştirmesi | Hayır / Hayır / Hayır |

## Tasarım ve izlenebilirlik

`deepseek-flash`, düşünme modu kapalı, sıcaklık `0` ve yapılandırılmış JSON
ile üç sekizlik partide çağrıldı. Her istek yalnız soru, şıklar, üç kartın kısa
metni ve üç yerel PDF kesiti taşıdı. Her vaka için istek, yanıt ve kesit
SHA-256 değerleri ayrı denetim dosyasında tutulur. Üç partinin candidate,
corpus ve şablon checksum'ları eşleşti.

## Geçerli yorum

PDF görüntüsüne dayalı inceleme, önceki yalnız metin tabanlı ön incelemeye
göre daha güçlü bir provenance kontrolüdür. Buna rağmen bu sonuç yalnız
BM25'nin kendi seçtiği kart havuzunu etiketler. 18 `insufficient` kartın
etiketsiz bırakılması ve incelenen kartların yarısının `wrong` olması, top-3
varlığını ürün kalitesi sanmanın yanlış olacağını gösterir.

Dense/RRF yeni kartlar getirdiğinde onlar için de aynı kör PDF incelemesi
yapılmadan karşılaştırma veya runtime seçimi yapılamaz. Bu nedenle mevcut
etiket çıktısı `metrics_ready: false` ve runtime kapalı olarak saklanır.

## Özel yapıtlar

- Parti çıktıları: `data/private/ayt-history-exam/retrieval-agent-pdf-review-v1-000.json`, `-008.json`, `-016.json`
- Birleşik inceleme: `retrieval-agent-pdf-review-v1-completed-manifest.json`
- Yapısal doğrulama: `retrieval-agent-pdf-review-v1-validation.json`
- Pool etiketi: `retrieval-agent-pdf-review-v1-pool-labels.json`
- İstek/yanıt/kesit denetimi: `retrieval-agent-pdf-review-v1-audit.json`
