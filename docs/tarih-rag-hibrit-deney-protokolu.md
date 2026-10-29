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
