# Türkçe soru rehberi: model seçimi ve Kaggle kararı

25 Ekim 2026. Bu belge araştırmaya dayalı başlangıç kararıdır; proje üzerinde eğitim, hız veya kalite ölçümü değildir. [Önceki deney tasarımı](turkce-rag-arastirma-ve-deney-tasarimi.md) içerisindeki 4B merkezli model önerisinin yerine geçer. Diğer veri, güvenilirlik ve değerlendirme ilkeleri geçerlidir.

## Karar

Ana deney adayı **Qwen/Qwen3.5-9B**; güçlü metin alternatifi **Qwen/Qwen3-14B**; Türkçeye odaklı karşılaştırma **Trendyol/Trendyol-LLM-Asure-12B**. 4B yalnız maliyet ve kalite alt sınırı için isteğe bağlıdır. Kalite tavanını anlamak için kaynak erişimi varsa **Qwen3.5-27B** üzerinde eğitim yapmadan ayrı referans değerlendirme yapılır. Nihai model, aynı örneklerde öğretmen incelemesi ve donanım ölçümünden sonra seçilir. Kaggle'da 9B eğitimi başarılı sayılmadan çalışma garantisi verilmez.

Gerekçe: 9B, küçük model sınırına sıkışmadan Kaggle GPU'sunda 4-bit QLoRA denemesi için makul bir ilk hipotezdir. Qwen3.5-9B Apache-2.0 lisanslıdır ve çok modlu bir mimariye sahiptir; burada ilk deney metin odaklıdır ([model kartı](https://huggingface.co/Qwen/Qwen3.5-9B)). Qwen3-14B de Apache-2.0 ve metin odaklıdır ([model kartı](https://huggingface.co/Qwen/Qwen3-14B)). Trendyol 12B Türkçe odaklıdır, Gemma şartları geçerlidir ([model kartı](https://huggingface.co/Trendyol/Trendyol-LLM-Asure-12B)); kullanım ve dağıtım koşulları ürün amaçlarına göre incelenmelidir. Qwen3.5-27B Apache-2.0'dır ([model kartı](https://huggingface.co/Qwen/Qwen3.5-27B)).

Türkçeye özel model olması tek başına üstünlük garantisi değildir: [Cetvel](https://aclanthology.org/2026.eacl-long.46/) çeşitli Türkçe görevlerde incelediği Türkçe odaklı modellerin genel olarak güçlü çok dilli modellere geride kaldığını bildirmiştir. Bu sonuç yukarıdaki özel modellerin ürünümüzdeki sıralamasını belirlemez. Model kartlarındaki genel benchmarklar ve üretici iddiaları tarih rehberliği, erken cevap ifşası veya TTS anlaşılabilirliği için yeterli kanıt değildir.

## Boyut ve donanım gerçekleri

Aşağıdaki değerler sadece parametre sayısı × 4 bit hesabıdır, gerçek VRAM ölçümü veya sığma garantisi değildir. Embedding/vision bileşenleri, quantization metadata, yüksek hassasiyetli katmanlar, aktivasyonlar, LoRA, optimizer, KV cache, CUDA ve framework belleği eklenir:

| Boyut | İdeal 4-bit ham ağırlık | Yaklaşık GiB | Karar |
|---|---:|---:|---|
| 9B | 4.5 GB | 4.2 | Tek 16 GB sınıfı GPU'da QLoRA denemesi; gerçek tepe bellek ve süre ölçülecek. |
| 12B | 6 GB | 5.6 | Karşılaştırmalı inference; eğitim yalnız kaynak ve deney gerekçesi uygunsa. |
| 14B | 7 GB | 6.5 | Alternatif inference ve koşullu QLoRA denemesi; OOM olası. |
| 27B | 13.5 GB | 12.6 | 16 GB'ta eğitim hedefi gerçekçi varsayılmamalı; daha büyük GPU veya özel çoklu GPU denemesi gerekir. |

Kaggle'ın sağladığı GPU türü, kullanılabilirlik ve kota zamanla değişir. [Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) GPU kotasına işaret eder; oturumda `nvidia-smi`, CUDA, GPU sayısı ve boş bellek kaydedilir. İki T4 varsa her birinin belleği ayrıdır. DDP model kopyalarını tutar ve 2×16 GB'ı otomatik 32 GB model belleğine dönüştürmez; model bölme/FSDP/CPU offload ayrı mühendislik ve hız maliyeti getirir. [bitsandbytes donanım tablosu](https://huggingface.co/docs/bitsandbytes/main/en/installation) NF4 için compute capability 6.0+ belirtir; dağıtılan CUDA paketinin P100 sm60 desteği sürüme göre değişir. T4 ve P100'de fp16 kullanımı ve kütüphane/kernel uyumluluğu oturumda doğrulanmalıdır. Qwen3.5 çok modlu/hybrid mimarinin QLoRA, dikkat kernel'i ve model yükleyici desteği sürüm sabitleyerek özellikle denenmelidir; Qwen3-4B betiğinin model ID'sini değiştirmek yeterli değildir.

İlk smoke test: 9B 4-bit yükle; gerçek tokenizasyon ve eğitim örneğiyle tek forward/backward/optimizer adımı yap; adaptörü kaydet, tekrar yükle ve bir örnek üret. VRAM tepe noktası, saniye/adım, sürümler ve hata kaydı al. Sonra 20–50 adımlık kısa koşu; tam eğitim sadece veri ve bellek kontrolünden sonra. Batch 1, gradient accumulation, gradient checkpointing, kısa 1024–2048 token sınırı başlangıç hipotezleri; model şablonu ve cevap tokenlarının kesilmemesi test edilmeli. OOM'da önce bağlam uzunluğu ve gereksiz bileşenleri incele, sonra destekli offload veya daha büyük GPU değerlendir; sonuçsuz mikro optimizasyonlara takılma. Hiçbiri çalışmazsa Qwen3-14B metin modeli veya 9B inference-only kullanılarak alternatif GPU seçeneği değerlendirilir.

## Kaliteli ürün nasıl çalışacak?

Öğretmen onaylı soru → sunucu kontrollü oturum/aşama → checksum ve onay filtresi → BM25 + dense arama → RRF → gerekirse reranking → kanıt yeterliliği kontrolü → model → şema/ifşa kontrolleri → kaynak bağlantılı kısa yanıt ve TTS. Konu eşleşmeyen, kanıtsız veya görsele bağlı sorular uygun geri dönüşe gider. Model, cevap anahtarını ve yetkisiz parçaları görmez; öğrenci metni ve kaynak içerikleri güvenilmeyen veri olarak ayrılır. Nihai kaynak referansları modelden değil sunucudan gelir.

Aramada ilk adaylar [BGE-M3](https://huggingface.co/BAAI/bge-m3) ve [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B); bunlar cevap üreten 9B modelle aynı iş değildir. [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) ancak Recall/MRR ve uçtan uca gecikme katkısı ölçülürse eklenir. Yerel indeks 13 bölüm ve 348 aday içeriyor; bunlar otomatik onaylı veya eğitim için hazır değildir. Küçük havuzda karmaşık vektör veritabanı varsayma; önce basit indeks ve gerçek ölçüm kullan.

Öğrencinin doğrudan soru çözümü ile rehberlik beklentileri ayrılmalı: başlangıçta rehberlik, daha sonra sunucuda tutulan aşama ve açık kullanıcı eylemiyle adım adım açıklama. Doğrulanmış cevap anahtarı yoksa kesin doğru/yanlış iddiası yapılmaz. Açık uçlu metin, tarih, matematik ve görsel soruların doğrulama ihtiyaçları farklıdır; ilk kapsam tarih metin sorularıdır. Model çok modlu diye görsel doğruluğu varsayılmaz.

## Deney planı ve seçim kapıları

1. **Veri:** onaylı parça ve soru sayıları, cevap anahtarı doğrulaması, öğretmen yazımı diyaloglar, izinler ve bölüm dağılımını envanterle. Kaynak veya cevap etiketleri eksikse önce etiketle. Gerçek öğrenci verisi ve telifli belgeler için kullanım ve private Kaggle erişimi doğrulanır.
2. **Kapalı değerlendirme:** soru grubu ve yakın kopyalar ayrılarak train/dev/test oluştur; mümkünse bölüm dışında da test et. Sorulara dayalı ilgili kanıtı, kanıtsız/çelişkili durumları, erken ifşa ve uzman tarafından beklenen davranışı etiketle. Testi seçim için kullanma. İlk pilot sayıları veri erişimine bağlıdır; 200/40 satır kalite garantisi değildir.
3. **Eğitimsiz seçim:** aynı kanıtlarla 9B, 14B, 12B; mümkünse 27B referansı karşılaştır. Öğretmen kör puanlaması: kaynakla desteklenen olgu, soruya özgü pedagojik yardım, erken ifşa, Türkçe, cevapsızlık ve okunabilirlik. Kritik hataların sayısı ve paydası ayrı gösterilir. Her modelin prompt, thinking modu, çıktı token bütçesi, quantization ve örnekleme ayarları kaydedilir; gizli düşünme tokenları gecikme ve bütçeye dahildir. Önce dev setinde ayar yap.
4. **Arama:** BM25, dense, hibrit ve gerekirse reranker karşılaştır; Recall@k, MRR, kanıt yeterliliği ve yanlış kanıtı raporla. Öğretmen onayları dışında arama yok. Testte kaynakların erişilebilir olması doğal RAG koşuludur, fakat ilgili kaynaklar train ve testte ortaksa ezber ihtimali yorumlanır; bölüm dışı test ayrı sunulur.
5. **QLoRA:** 9B ve gerekirse en güçlü uygulanabilir diğer aday üzerinde öğretmen onaylı verilerle ayrı adaptör eğit. Dev setinde en iyi checkpoint seç; eğitimsiz aynı model ve aynı kanıtla karşılaştır. Prompt/completion biçiminde yalnız completion loss kullanımı için [TRL belgeleri](https://huggingface.co/docs/trl/sft_trainer) esas alınır. Eğitim ve değerlendirme şablonunu doğrula; `eval_loss` ürün başarısı değildir. Artış yoksa adaptör kullanılmaz.
6. **Dağıtım:** Kaggle eğitimden bağımsız bir inference sunucusu gerekir. Yerel donanım veya kiralık GPU, ağ gecikmesi, token/s ve p50/p95, RAM/VRAM ve eşzamanlılık ölçülür. İstenen hız için nihai donanım henüz bilinmiyor. Öğrenciler için açmadan önce öğretmen incelemesi, geri dönüş ve sürümleme tamamlanır.

Karar sırası: önce kritik yanlış bilgi ve ifşa oranı, ardından pedagojik yararlılık ve Türkçe kalite; bunları karşılayanlar arasında gecikme/bellek/maliyet. Kesin eşikler öğretmenlerle dev kümesinde belirlenir, testten önce sabitlenir. Küçük testte belirsizlik ve başarısız kategoriler ayrıca raporlanır; 27B zayıf çıkarsa sırf büyük diye seçilmez.

## CV ve yayınlanabilir çıktı

Tekrarlanabilir özel Türkçe eğitim benchmarkı, veri kartı ve kaynak lisansı; en az üç açık ağırlıklı modelin aynı sorularda karşılaştırması; retrieval ve QLoRA katkılarını ayıran ablasyonlar; uzman kör inceleme ve hata analizi; ölçülmüş yerel/servis gecikmesi; erişilebilir çalışan demo. Başka modellerden sentetik veri üretilebilir, ancak kaynak/lisans ve öğretmen onayı gerekir; yapay etiketleri doğrudan altın kabul etme. Sonuç çıkmadan doğruluk yüzdesi veya hız iddia edilmez.

## 25 Ekim deney sonrası düzeltme

Qwen3.5-9B'nin tek T4 ve fp16 ağırlıklarla uygulanan QLoRA smoke testi çok adımda sonlu olmayan gradyan üretti; bu modelin Kaggle'da eğitim için uygulanabilirliği gösterilmemiştir. [PyTorch hassasiyet rehberi](https://docs.pytorch.org/blog/what-every-user-should-know-about-mixed-precision-training-in-pytorch/) bf16 ile eğitilmiş modellerin fp16'da aralık sorunlarına girebileceğini açıklıyor; bu, bu projedeki hatanın kesin nedeni olarak kabul edilmemelidir. Ayrıca [Unsloth Qwen3.5 rehberi](https://unsloth.ai/docs/models/qwen3.5/fine-tune) bu ailede artan quantization farkları nedeniyle 4-bit QLoRA önermiyor. Bu uyarı bağımsız bir ürün ölçümü değildir, ancak deney kararında dikkate alınmalıdır. BF16/LoRA imkânı sunan donanım ve daha önce belirlenen Qwen3-14B veya başka bir model ayrı adaydır. 4-bit ile daha yüksek hassasiyetli inference arasındaki kalite farkı gerçek Türkçe kapalı değerlendirmede ayrıca ölçülmeden QLoRA tercih edilmemelidir.

Tek T4 üzerinde sentetik üç adımlı kontrolde Qwen3-14B NF4/fp16 sonlu gradyanlar ve adaptörün geri yüklenmesiyle çalıştı; Qwen3.5-9B fp16 denemeleri sonlu olmayan gradyanlarda durdu, BF16 denemesi yüklemede OOM verdi. Bu nedenle Kaggle üzerinde ilk eğitim hattı için Qwen3-14B şu an teknik olarak daha güçlü adaydır. Bu sonuç gerçek rehberlik kalitesinde model sıralaması veya uzun bağlamda eğitim garantisi değildir.
