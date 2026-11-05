# AYT kanıt getirme: model seçimi ve deney sırası

Tarih koçu için model seçimi tek bir genel benchmark puanına dayanmaz. Kabul
kararı, kaynak sürümü sabit AYT geliştirme kümesinde PDF kesiti incelemesiyle
oluşan kanıt etiketleri, yanlış kanıt oranı ve gecikme birlikte incelendikten
sonra verilir.

## Araştırma sonucu

| Aday | Kullanım kararı | Gerekçe |
| --- | --- | --- |
| `BAAI/bge-m3` | Taban çizgisi ve ilk-aşama adayı | Çok dilli dense ve sparse getirmeyi aynı modelle sağlar; temiz V4 kalibrasyonunda BM25'ten iyi aday sonuç vermiştir. Henüz runtime kabulü yoktur. |
| `BAAI/bge-reranker-v2-m3` | İlk ikinci-aşama deneyi | Çok dilli cross-encoder'dır. Yalnız dense'in ilk 32 adayını yeniden sıralar; tüm kitapta çalışmaz. |
| `Qwen/Qwen3-Embedding-4B` | Seçilen kalite adayı | T4'te uçtan uca sorgu getirme p95'i hedefin altında kaldı ve kör PDF-kesiti incelemesinde BGE dense'i geçti. İngilizce görev talimatı bu corpus için seçildi; bağımsız holdout ve insan onayı olmadan runtime'a açılmaz. |
| `Qwen/Qwen3-Reranker-4B` | Runtime dışında | Top-32 ikinci aşama sıralama, bu geliştirme kümesinde kanıt kapsamını ve MRR'yi düşürdü; T4 p95'i yaklaşık dokuz saniyedir. |
| `Qwen/Qwen3-Embedding-8B` | Büyük GPU'da ayrı embedding ablasyonu | 100'den fazla dili, 32k bağlamı ve instruction-aware embedding'i destekler. Yüksek çok dilli MTEB puanı, Türkçe tarih kanıtı için kanıt değildir; aynı private geliştirme protokolünde ölçülmelidir. |
| `Alibaba-NLP/gte-Qwen2-7B-instruct` | Daha büyük GPU varsa ikinci embedding ablasyonu | Çok dilli bir adaydır; model kartındaki fp32 yük boyutu ve önerilen donanım koşulları T4 üzerinde rahat bir ilk deney için uygun değildir. |
| `microsoft/harrier-oss-v1-27b` | Şimdilik dışarıda | 27B model, T4'ün çalışma ve p95 hedefiyle uyumlu değildir. Büyük GPU ve ayrı maliyet/gecikme bütçesi olmadan adil ölçüm yapılamaz. |
| `BAAI/bge-large-en-v1.5` | Dışarıda | İngilizce odaklıdır; Türkçe AYT corpus'u için çok dilli bir modelin yerine konmaz. |

Bir model kartının MTEB puanı, bizim ölçümümüz değildir. Ayrıca model
kartındaki İngilizce instruction önerisi, Türkçe soru metnini İngilizceye
çevirme gerekçesi değildir; Qwen adayı denenirse sabit Türkçe corpus üzerinde
aynı görev talimatı için Türkçe ve İngilizce instruction ayrı ablation olarak
ölçülür.

## İlk deney: dense → cross-encoder

`ayt_relation_retrieval_benchmark.py` artık aşağıdaki beş yöntemi aynı sorgu
ve corpus üzerinde üretir:

1. BM25
2. BGE-M3 dense
3. BGE-M3 sparse
4. Reciprocal Rank Fusion
5. BGE-M3 dense ilk 32 aday → BGE Reranker V2-M3

Reranker için aday penceresi sabittir. Böylece sonucu iyileştirirse bunun dense
adayları daha iyi seçmekten değil, ikinci aşama sıralamasından geldiği
anlaşılır. Her yöntem için sorgu süresi ayrı kaydedilir. Doküman embedding
süresi de sonraki runtime benchmarkında ilk indeks kurulum maliyeti olarak
ayrı raporlanacaktır; sorgu p95 ile karıştırılmaz.

## Kabul düzeni

Bu deney yalnız geliştirme kalibrasyonudur. BGE-Reranker adayının ürün yoluna
alınması için:

- eşit yöntem bütçeli kör PDF kesiti incelemesinde dense'e göre Recall@3,
  MRR@3 ve kanıt kapsamı artmalı veya açık bir hata türünü azaltmalı;
- yanlış kanıt oranı yükselmemeli;
- önceden görülmemiş ayrı private holdout'ta aynı yön korunmalı;
- yerel hedef donanımda retrieval p95 `<= 1 saniye` olmalı;
- hiçbir sonuç insan/PDF onayı olmadan öğrenciye veya QLoRA eğitimine
  kaynak olarak geçmemeli.

Yüzdelik eşik, tek başına mekanik ret kuralı değildir. Örnek sayısı küçükse
etki büyüklüğü, hata türleri, belirsizlik ve p95 birlikte değerlendirilir.
Ancak doğruluk artışı gecikme ya da yanlış kanıt maliyetini haklı çıkarmıyorsa
ürün yolu değişmez.

## Deney kaydı

### V5 — BGE-M3 dense → BGE Reranker V2-M3

- Koşum: private Kaggle Tesla T4, 1.920 MEB aday parçası, 24 geliştirme
  sorgusu, dense ilk 32 adayın cross-encoder ile yeniden sıralanması.
- Gecikme: BGE-M3 dense p95 `55,26 ms`; reranker aşaması p95 `447,42 ms`.
- Kör PDF-kesiti incelemesi: üç bağımsız `history_teacher_agent_v1` kaydı,
  24 soru ve 288 kart. Cevap anahtarı/çözümlü referans kullanılmadı.
- Dense: Recall@3 `0,7353`, MRR@3 `0,8235`, yanlış kanıt oranı `0,5882`.
- Dense + reranker: Recall@3 `0,7108`, MRR@3 `0,7647`, yanlış kanıt oranı
  `0,5686`.

Karar: reranker yanlış kanıt oranını küçük miktarda düşürmesine rağmen Recall
ve MRR'yi düşürdü. Bu nedenle BGE reranker V2-M3 bu corpus için runtime
adayına alınmadı. Deney sonucu, Qwen 4B + 4B kalite meydan okuyucusunun aynı
protokolle sınanması için kaydedildi.

### Qwen kalite koşumu hazırlığı

- İlk aşama aday penceresi `32` olarak sabitlendi. Bu değer, top-3 değerlendirme
  için 15–20 aday önerisinin üzerindedir; reranker yalnız bu pencerede çalışır.
- T4 için `float16` kullanılır. T4'te BF16 Tensor Core yolu olmadığı için BF16
  kalite veya hız avantajı varsayılmaz.
- Qwen model kartı, özel instruction kullanımının çoğu retrieval görevinde
  faydalı olabildiğini; çok dilli senaryoda İngilizce instruction önerdiğini
  belirtir. İlk koşumda alan odaklı İngilizce instruction kullanılır. Türkçe
  instruction, aynı model/seed/corpus üzerinde ayrı ablation olmadan kabul
  edilmez.
- İlk V1 yüklemesi embedding modelinin GPU belleğini serbest bırakmadan
  reranker yüklemeye çalıştığı için OOM ile durdu; çıktı üretmedi ve karar
  verisinde kullanılmadı. Düzeltmede `embedding.cpu()`, çöp toplayıcı ve CUDA
  önbellek temizliği eklendi; koşum yeniden başlatıldı.
- Düzeltilmiş Qwen koşumu tamamlandı: 1.920 aday parçası ve 24 geliştirme
  sorgusu. Qwen reranker top-32 p95 süresi `8.957,76 ms` oldu. Bu nedenle
  kalite kör incelemesi tamamlanmadan da `<=1 saniye` runtime kabul kapısını
  geçemediği bilinmektedir. Qwen dense için ilk kayıttaki süre yalnız vektör
  skorlama süresiydi; sonraki koşumda sorgu embedding'i ile birlikte ölçmek
  üzere runner düzeltildi.

### Adil BGE–Qwen karşılaştırması

İki ayrı aday havuzunun etiketini karşılaştırmak yerine, tüm yöntemlerin
top-3 kaynaklarının birleşiminden 24 soru × 21 kartlık (504 kesit) tek kör
inceleme paketi üretildi. Üç bağımsız agent dilimi, aynı PDF kesitleri üzerinde
etiketlendi. Böylece her yöntem aynı altın destek/yanlış kaynak kümesinde
skorlandı.

| Yöntem | Recall@3 | MRR@3 | nDCG@3 | Yanlış kanıt oranı |
| --- | ---: | ---: | ---: | ---: |
| BGE-M3 dense | 0,6461 | 0,8235 | 0,6981 | 0,5882 |
| BGE dense + reranker | 0,6431 | 0,7647 | 0,6885 | 0,5686 |
| Qwen3-Embedding-4B dense | 0,6811 | 0,8824 | 0,7611 | 0,5294 |
| Qwen dense + Qwen reranker | 0,6399 | 0,8137 | 0,7293 | 0,5098 |

Qwen dense, BGE dense'e göre Recall@3'te `+0,0350`, MRR@3'te `+0,0589`
artış ve yanlış kanıt oranında `-0,0588` fark gösterdi. Reranker iki modelde
de kapsamı ve MRR'yi düşürdü; Qwen reranker ayrıca T4'te top-32 için yaklaşık
9 saniye p95 sürdü. Karar: Qwen dense sonraki holdout ve instruction ablation
adayıdır; hiçbir reranker runtime yoluna alınmaz.

### V1 — Qwen3-Embedding-4B instruction ablation

- Koşum: private Kaggle Tesla T4, sabit 1.920 MEB aday parçası ve 24
  geliştirme sorgusu. Doküman embedding'i bir kez üretildi; ölçüm her sorguda
  instruction ile sorgu embedding'i ve cosine aramayı birlikte içerir. p95,
  24 ham sorgu süresinin nearest-rank yüzdelik hesabıdır.
- Kör inceleme: üç bağımsız agent, yöntemlerin top-12 birleşiminden oluşan
  24 soru × 12 PDF kesitini değerlendirdi. Cevap anahtarı ve çözümlü kaynak
  hiçbir inceleme paketine verilmedi.

| Yöntem | Recall@3 | MRR@3 | nDCG@3 | Kanıt kapsamı@3 | Yanlış kanıt oranı | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0,5245 | 0,7255 | 0,5685 | 0,3529 | 0,7059 | 41,58 ms |
| Qwen dense, İngilizce instruction | **0,7500** | 0,8824 | 0,7749 | **0,5294** | **0,5294** | **171,97 ms** |
| Qwen dense, Türkçe instruction | 0,7255 | **0,9118** | **0,7786** | 0,4706 | 0,5490 | 219,87 ms |

Karar: İngilizce instruction seçildi. Türkçe instruction'ın MRR ve nDCG
farkı çok küçüktür; buna karşılık İngilizce talimat Recall@3 ve kanıt
kapsamında daha yüksek, yanlış kanıt oranında daha düşüktür ve p95'i de
biraz daha kısadır. Bu sonuç, 24 soruluk geliştirme kümesine özgüdür;
istatistiksel kesinlik veya genel başarı iddiası değildir. Sonraki adım,
aynı kararın daha önce görülmemiş private holdout'ta korunup korunmadığını
ölçmek ve yalnız PDF kesitiyle insan onayı verilmiş parçalar için runtime
allowlist oluşturmaktır.

## Kaynaklar

- [BGE Reranker V2 M3 model kartı](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [BGE-M3 belgeleri](https://bge-model.com/bge/bge_m3)
- [Qwen3 Embedding 8B model kartı](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- [GTE Qwen2 7B Instruct model kartı](https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct)
- [Harrier OSS V1 27B model kartı](https://huggingface.co/microsoft/harrier-oss-v1-27b)
