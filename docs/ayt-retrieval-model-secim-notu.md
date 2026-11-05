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

## Kaynaklar

- [BGE Reranker V2 M3 model kartı](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [BGE-M3 belgeleri](https://bge-model.com/bge/bge_m3)
- [Qwen3 Embedding 8B model kartı](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- [GTE Qwen2 7B Instruct model kartı](https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct)
- [Harrier OSS V1 27B model kartı](https://huggingface.co/microsoft/harrier-oss-v1-27b)
