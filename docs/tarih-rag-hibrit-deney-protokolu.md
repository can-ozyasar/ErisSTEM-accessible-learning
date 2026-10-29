# Tarih RAG: kanıt kalitesi ve hibrit getirme protokolü

## Sınır

PDF, tam MEB metni, soru bankası, cevap anahtarı, öğrenci verisi ve kapalı test Kaggle'a yüklenmez. Kaggle girdisi yalnız kısa öğretmen-onaylı kanıt, bölüm, parça kimliği ve altın kanıt kimliğidir. Girdi denetleyicisi cevap anahtarı alanlarını reddeder.

## Akış

1. Öğretmen PDF kırpımını inceleyerek genel kaynak onayı verir. Checksum, sayfa, koordinat, bölüm ve OCR/görsel/yönerge uyarıları saklanır.
2. Öğretmen soru için en çok iki doğrudan, görsele bağımlı olmayan onaylı parçayı seçer. Bu kayıt olmadan öğrenci koçu ve QLoRA dışa aktarımı kaynak alamaz.
3. Kaggle'da aynı geliştirme sorularında BM25, BGE-M3 dense ve `k=60` RRF ölçülür. Qwen3-Reranker-0.6B yalnız RRF top-k üzerinde, RRF ilk kapıyı geçerse denenir.
4. Yerel hibrit yapıt PDF checksum'ı veya onay kümesi değiştiğinde geçersizdir; kabul kararı olmadan etkinleşmez.

## Kabul kapısı

BM25'e göre Recall@3 en az +0,05, MRR@3 en az +0,03 artmalı; yanlış kanıt oranı yükselmemeli ve yerel retrieval p95 1 saniyeyi geçmemelidir. Geçemeyen model raporda kalır, ürün yoluna girmez.

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
