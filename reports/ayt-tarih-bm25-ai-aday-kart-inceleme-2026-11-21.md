# AYT Tarih BM25 cevap-körü AI aday-kart incelemesi

Bu kayıt, dondurulmuş 24 retrieval sorusunda BM25'in getirdiği top-3 kaynak
atomunun ayrı bir kaynak-metin AI incelemesidir. İnsan öğretmen değerlendirmesi,
PDF kırpımı doğrulaması veya ürün kabul raporu değildir.

| Ölçüm | Sonuç |
| --- | ---: |
| Kilitli soru | 24 |
| Her sorudaki incelenen atom | 3 |
| Doğrudan kanıt tanısı | 24 / 24 |
| AI top-1 destek oranı | 1,0000 |
| AI top-3'te en az bir destek oranı | 1,0000 |
| Top-3 başına ortalama destek atomu | 1,1250 |
| Anahtar / çözüm / öğrenci verisi erişimi | Hayır / Hayır / Hayır |
| Runtime veya QLoRA için etkinleştirilen kayıt | 0 |

## İşlem sınırı

Dış incelemeye yalnız soru kökü, beş şık ve BM25'in seçtiği üç kısa atom
gönderildi. Referans atom kimliği, doğru seçenek ve açıklama gönderilmedi.
İstek, JSON sınıflandırması için düşünme modu kapalı ve sıcaklık `0` olacak
biçimde yapılandırıldı. İnceleme yalnız `support` / `wrong` kaynak-kart
etiketleri üretti; bu etiketler insan onayı olarak sunulamaz.

## Geçerli yorum

Sonuç, bu 24 soruda BM25'in kendi ilk üç adayında en az bir açık destek kartı
olduğunu gösteren olumlu bir araştırma sinyalidir. Ancak aday havuzu BM25 ile
seçildiği için bu sayı dense, RRF veya reranker'a karşı bağımsız bir kalite
karşılaştırması değildir. Ayrıca kaynak adaylarının insan PDF kırpım doğrulaması
tamamlanmadığından hiçbir kayıt öğrenci koçuna veya çalışma zamanı RAG yoluna
aktarılmamıştır.

Bir sonraki gerçek retrieval kapısı; aynı kilitli sorularda yöntemlerin aday
birleşimini, insan/PDF ile `relevant`, `wrong` ve `insufficient` olarak
etiketlemek; ardından Recall@1/@3, MRR@3, nDCG@3, tam iddia kapsamı, yanlış
kanıt ve çekimserliği karşılaştırmaktır.

## İzlenebilirlik

- BM25 baseline: `data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json`
- Cevap-körü kuyruk ve kalibrasyon: `retrieval-bm25-ai-review-queue-v1.json`, `retrieval-bm25-ai-review-calibration-v1.json` (özel)
- Parti çıktıları: `retrieval-bm25-ai-review-v1-000.json`, `-008.json`, `-016.json` (özel)
- Birleşik değerlendirme: `data/private/ayt-history-exam/retrieval-bm25-ai-assessment-v1.json`
- Candidate checksum: `69a9e5884deddaa2cf145022f0a1d343ef84505b4a2f16c22e391c2424d9a70a`
- Corpus checksum: `6a286b9387faefad5a3f87afe536c4cf1247589e683ee218787113d8710a4440`
