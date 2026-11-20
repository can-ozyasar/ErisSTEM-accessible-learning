# ADR-0015: Kaynak-bağlı koç için tek-sözleşmeli QLoRA deneyi

**Durum:** Kabul edildi — Kaggle ön-koşumu başlatıldı; Evren nihai koşum ve
yayın adayı olarak kalite kapısına bağlıdır.

## Karar

QLoRA, tarih bilgisini veya cevap anahtarını modele ezberletmek için
kullanılmayacaktır. RAG, her istekte doğrulanmış kanıtı seçmeye devam eder;
adaptörün görevi yalnız bu kanıtla kısa, doğal, erişilebilir ve Sokratik bir
sonraki soru üretmektir. Kanıt yoksa modelden tarihsel tahmin değil güvenli
çekimserlik beklenir.

Bu ayrım önemlidir: 120 soruluk kaynak havuzu, alan bilgisini güvenilir biçimde
öğretmek için küçük; fakat kaynak verildiğinde koçun konuşma davranışını
ölçmek için yeterli bir ilk kapalı deney setidir.

## Veri ve sızıntı sınırı

- 120 soru grubu ve her birinde altı koçluk durumu vardır (720 örnek).
- Aynı soru grubunun tüm turları aynı ayrımda kalır.
- Kaynak bölümleri train/dev/sealed-test arasında kesişmez.
- Kaggle'a yalnız train ve dev aktarılır: 71/24 soru grubu, 426/144 örnek.
  Sealed test (25 grup, 150 örnek), cevap anahtarı, PDF, koordinat ve öğrenci
  verisi yerelde kalır.
- Kaggle girdi manifesti; model revision'ı, veri checksum'ları, veri sayıları
  ve hiperparametreleri birlikte bağlar. Çalıştırıcı herhangi bir dosya
  checksum'ı değişirse başlamaz.

## Tek ön-kayıtlı koşum

Kaggle T4 yalnız ortam/doğrulama ve taban-model davranış ölçümü içindir.
Nihai tek eğitim Evren GPU üzerinde, aynı manifest değişmeden çalışır:

| Bileşen | Sabit seçim | Gerekçe |
|---|---|---|
| Taban | `Qwen/Qwen3-14B` pinli revision | Mevcut Türkçe koç baseline'ı ile aynı model ailesi |
| Quantization | 4-bit NF4 + double quantization, FP16 compute | QLoRA'nın bellek tasarrufu yöntemi; T4 BF16 desteklemez |
| Adaptör | attention `q/k/v/o`, r=16, alpha=32, dropout=.05 | Küçük veri için davranış odaklı ve sınırlı kapasite |
| Eğitim | completion-only loss, 3 epoch, LR 1e-4, batch=1×grad-accum=8, seed=42 | Sadece koç yanıtı hedeflenir; prompt/RAG kanıtı kopyalanmaz |
| Optimizasyon | `paged_adamw_8bit`, gradient checkpointing | T4/Evren bellek piklerini sınırlamak |

T4'te 14B taban için `prepare_model_for_kbit_training` doğrudan
kullanılmaz: güncel PEFT sürümü tüm quantize olmayan FP16 parametreleri FP32'ye
çıkarır ve Qwen'in büyük embedding/LM head ağırlıkları eğitim başlamadan belleği
taşırır. Bunun yerine taban parametreleri dondurulur, yalnız küçük `norm`
parametreleri FP32'ye alınır, input-gradient kancası ile gradient checkpointing
etkinleştirilir. Büyük embedding ve LM head FP16 kalır. Koşum raporu bu
hazırlama yöntemini ve FP32'ye alınan norm parametre sayısını zorunlu olarak
kayda geçirir.

Değerlendirme ve canlı çıkarımda Qwen3'ün `enable_thinking=False` anahtarı
kullanılır; bu, sesli etkileşimde görünür düşünme bloğunu ve gereksiz gecikmeyi
önler. Tek bir token limiti bütün pedagojik durumlara uygulanmaz:

| Çıktı türü | `max_new_tokens` | Temperature / sampling | Gerekçe |
|---|---:|---|---|
| Aktif denemedeki tek Sokratik tur | 128 | `temperature=.35`, `top_p=.8`, `top_k=20` | Kısa kalır, fakat Türkçe doğal ifade için gereksiz sert kesme yapılmaz. Yanıt ilk soru işaretinde ayrıca durdurulur. |
| Deneme sonrası kaynaklı kısa açıklama | 256 | `temperature=.2`, `top_p=.8`, `top_k=20` | Açıklama yarım kalmaz; düşük çeşitlilik kaynak dışına çıkma riskini azaltır. |

İlk profil QLoRA'nın ürettiği **tek soru** içindir. İkinci profil QLoRA'nın
cevap ezberlemesiyle değil, cevap anahtarı deneme sonrasında yetkilendirildiği
zaman deterministik kaynak kanıtı ve ayrı güvenlik kapısıyla çalışır. Qwen'in
non-thinking için genel önerisi `.7/.8/20` olsa da, burada `.35` ön-kayıtlı
başlangıç noktasıdır; base ve adaptör aynı kapalı dev istemlerinde bu ayarla
değerlendirilmeden canlıya alınmaz.

Bu bir hiperparametre arama planı değildir. Dev sonucu yalnız önceden kayıtlı
koşumun kabul edilip edilmemesine yarar. Model, yalnız düşük dev loss gösterdi
diye seçilemez.

## Evren'de nihai eğitim, yayın ve dağıtım kapısı

Evren, nihai eğitim ve kontrollü model yayını için **aday** platformdur;
Kaggle koşumu ise kredili ortamda hata ayıklamak yerine, aynı sözleşmenin
çalışabilirliğini ve taban modele göre değerini ölçen ön-kapıdır. Bu nedenle
mevcut Kaggle deneyi durdurulmaz ya da Evren'de yeniden denenerek kredi
harcanmaz. Evren'e yalnız aşağıdaki karar kaydı tamamlanınca gidilir:

1. Kaggle dev kapısı geçilir: bütün kritik güvenlik ihlalleri sıfır, kaynak
   checksum uyumu yüzde 100 ve pedagojik rubrikte taban modelden gerileme
   yoktur. Sonuç; hata örnekleri, gecikme, maliyet/VRAM ve adapter manifestiyle
   kayda alınır.
2. Evren'e yalnız tam olarak aynı, hash'i doğrulanmış `train/dev` deney paketi
   ve bu ADR'deki tek hiperparametre sözleşmesi taşınır. Yeni veri, yeni
   prompt, yeni epoch veya deneme-yanılma tabanlı tarama yapılmaz. Sealed test,
   cevap anahtarı, öğrenci verisi ve ham MEB PDF'leri varsayılan olarak
   taşınmaz.
3. Evren koşumu bitince adapter/tokenizer/checkpoint manifesti, commit, model
   revision'ı, seed, donanım, paket sürümleri, eğitim eğrileri, süre, VRAM ve
   gecikme raporu bütünlük kontrolüyle saklanır. Sealed değerlendirme yalnız
   seçilen tek adapter için, kontrollü ve bir kez yapılır.
4. Evren'e model **yayınlama** kararı, yalnız sealed kapısı da geçilirse verilir:
   erken cevap ifşası `0`, kaynak dışı iddia `0`, yanlış kaynak atfı `0`,
   checksum uyuşmazlığında güvenli ret `%100`, ayrıca erişilebilir deneme
   akışındaki p95 bütçeleri sağlanmalıdır. Kapı geçmezse ürün deterministik
   koçla kalır; adapter yayınlanmaz.

Yayın üç ayrı varlık olarak yönetilir; bunlar tek paket sayılmaz:

| Varlık | Varsayılan görünürlük | Yayın ön koşulu |
|---|---|---|
| Kod, deney sözleşmesi, ölçüm şeması ve sentetik örnekler | Açık kaynak olabilir | Gizli anahtar, öğrenci verisi, cevap anahtarı, kitap metni veya sayfa görseli içermez. |
| Eğitim verisi ve kanıt atomları | Özel / yayımlanmaz | Kaynak sahibinin açık yeniden-dağıtım izni ve ayrıca veri incelemesi gerekir. |
| QLoRA adapteri / Evren model kaydı | Önce özel veya erişim-kısıtlı | Yukarıdaki kalite kapısı, model kartı, kullanım sınırı ve kaynak lisansı incelemesi tamamlanır. |

Bu ayrım CV için de daha güçlü ve doğru bir iddia üretir: “kaynak-bağlı,
ölçülmüş ve güvenlik kapılı erişilebilir eğitim koçu”; “öğretmen eşdeğeri” ya
da telifli MEB içeriğini açıkça yeniden yayımlayan bir model iddia edilmez.
Evren'in güncel kullanım, gizlilik ve model-yayın koşulları nihai yüklemeden
önce platform hesabı üzerinden ayrıca doğrulanır; bu ADR, henüz doğrulanmamış
bir kamusal yayın izni varsaymaz.

## Değerlendirme ve kabul

1. Aynı dev istemlerinde base model ile adaptör karşılaştırılır.
2. Dev davranış kapısı: erken cevap ifşası `0`, kaynak dışı iddia `0`, tam
   kaynak checksum uyumu `100%`; doğal Türkçe, aşama uyumu ve pedagojik
   yararlılık taban modelden gerilemez.
3. Bu kapı geçerse seçilen adaptör sealed testte **yalnız bir kez** çalışır.
4. Sealed testte aynı üç kritik güvenlik koşulu sıfır/100% olmalı; aksi halde
   adaptör runtime'a alınmaz ve deterministik koç korunur.
5. Rapor; commit, girdi/output checksum, GPU, paket sürümleri, seed, adapter
   parametre sayısı, VRAM tepe değeri, süre, tokens/s, p50/p95 ilk-token ve
   tam-yanıt gecikmesini taşır.

AI yargıcı yalnız ölçüm yardımcısıdır; sonuçlar "öğretmen eşdeğeri" diye
sunulmaz. Bu iddia için bağımsız alan uzmanı ve erişilebilirlik katılımcı
çalışması gerekir.

## Dayanak

QLoRA'nın NF4, double quantization ve paged optimizer yöntemi için
[orijinal çalışma](https://arxiv.org/abs/2305.14314); 4-bit PEFT kullanımı için
[Transformers dokümantasyonu](https://huggingface.co/docs/transformers/quantization/finetune);
completion-only loss ve packing davranışı için
[TRL SFTTrainer dokümantasyonu](https://huggingface.co/docs/trl/en/sft_trainer)
kullanılmıştır. Bu kaynaklar bellek/eğitim mekanizmasını açıklar; pedagojik
kalite iddiasını tek başına desteklemez.
