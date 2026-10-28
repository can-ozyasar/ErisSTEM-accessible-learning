# Türkçe kaynaklı soru rehberi: araştırma ve deney tasarımı

Model seçimi bu ilk araştırmadan sonra güncellendi: [Kapsamlı model ve Kaggle kararı](turkce-rag-model-secimi-kaggle-karari.md) güncel öneridir.

Tarih: 25 Ekim 2026. Durum: araştırma ve deney önerisi; model eğitimi, benchmark ve ürün entegrasyonu tamamlanmış değildir.

## Projedeki başlangıç noktası

Tarih soru rehberi `apps/api/app/question_bank_routes.py` içinde çalışır. `history_rag.py`, kaynak PDF checksum'ına bağlı, öğretmen onaylı parçaları konu başlığına göre filtreleyip BM25 ile sıralar. Yanıtlar sabit şablonlardır; bu akışta harici LLM API çağrısı bulunmaz. Kaynak bulunamazsa soru köküne döner. Cevap anahtarı öğrenciye ve bu akışa verilmez. Kanıtın bulunması, üretilen şablonun o kanıtla öğrencinin sorusunu gerçekten yanıtladığı anlamına gelmez. Konu eşleştirme hatası ve Türkçe ekler yüzünden sözcüksel eşleşme kaçırılması ölçülmelidir. Kullanıcıdan gelen tur sayısı sunucu tarafından doğrulanan bir oturum değildir.

`experiments/kaggle/history_tutor_sft.py` Qwen3-4B için bir QLoRA taslağıdır. En az 200 eğitim ve 40 değerlendirme turu ister, soru kimliği kesişmesini kontrol eder ve eval loss kaydeder. Bu sayılar kalite güvencesi veya yeterli örneklem kanıtı değildir; eval loss da pedagojik kaliteyi ve kaynak sadakatini ölçmez. Kaynak kimliğinin varlığını doğrulamaz; metin ve kaynak benzerliği ile bölüm düzeyinde veri sızıntısını kontrol etmez; cevapsız örneklerde kaynak ID'sini zorunlu kılması önerilen değerlendirmeyle çelişir. Betik eğitim başarısı veya Kaggle uyumluluğu test edilmiş kabul edilmemelidir. Önce veri sözleşmesi ve değerlendirme düzeltilmelidir.

## Önerilen ürün

Önce 9. sınıf tarih metin sorularına odaklanan, öğrencinin düşünmesini destekleyen, kısa ve sesli okumaya uygun Türkçe rehber. Her turda öğrencinin soru kökü, mesajı ve seçtiği şık değerlendirilir; öğretmen onaylı ilgili kaynaklar bulunur; kanıt yeterli değilse sistem bunu söyler. İlk turda cevabı açığa çıkarmaz; öğrencinin gerekçesini ister ve kaynakla ilişkilendiren özgül bir ipucu sunar. Görsel, tablo veya doğrulanmamış OCR gerektiren sorular desteklenmediği açıkça belirtilerek uygun geri dönüşe yönlendirilir. Sesli kullanımda kaynak ve öğrenci mesajlarının okunabilirliği ayrıca değerlendirilir.

Önerilen işlem sırası:

1. Sunucu öğrenciye gösterilmesine izin verilen soruyu ve konu bilgisini doğrular; cevap anahtarını model girdisine koymaz. Oturum adımları sunucuda tutulur; istemcinin tur sayısına güvenilmez.
2. PDF checksum'ı ve öğretmen onayına göre filtrele, sonra konu eşleştir. Konu eşleşmesi kesin değilse veya görsel bilgi eksikse güvenli geri dönüş yap. Onaysız veya eski sürüm parça hiçbir aşamada aday olamaz.
3. Onaylı adaylarda BM25 ve çok dilli dense arama yürüt; sıralamaları reciprocal rank fusion (RRF) ile birleştir. Örn. `sum(1/(60 + rank))`; aday ve son kanıt sayısını geliştirme kümesinde seç. Reranker yalnız deneyde kalite/gecikme katkısı gösterirse eklenir.
4. Kanıt yeterliliğini geliştirme kümesinde kalibre et; salt sıralama skorunu doğruluk olasılığı gibi sunma. Eksik ve çelişkili kanıtta modelden kesin açıklama isteme. Skorlar farklı indeks veya modele taşındığında yeniden kalibre edilir.
5. Modele yalnız soru, mevcut öğrenci turu, pedagojik aşama ve seçilmiş kanıtı ver. Kısa yapılandırılmış bir öneri üret; uygulama kaynak ID ve sayfa bilgisini kendi kayıtlarından ekler. Kaynak metni ve öğrenci girdisini talimat olarak görmemesi için ayrıştır.
6. Şema ve uzunluk doğrulaması, kaynak ID üyeliği ve açık cevap ifşası kontrolleri çalıştır; bu kontroller anlamsal doğruluğu garanti etmez. Hatalı, zaman aşımına uğrayan veya kanıtsız yanıtta mevcut deterministik akışa dön. Üretim öncesinde uzman incelemesi ve kapalı test şarttır.

Modelin cevap anahtarını görmemesi tek başına cevabı tahmin etmesini veya ifşa etmesini engellemez. Bunu gerçek değerlendirmede ölçmek gerekir. Kaynak adresinin geçerli olması da açıklamadaki iddiaların kaynak tarafından desteklendiğini kanıtlamaz.

## Model seçimi ve uygulanabilirlik

- **İlk üretici adayı:** [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), Apache-2.0, metin ve non-thinking; mevcut betikle uyumlu bir başlangıç. Türkçe rehberlik kalitesi projede henüz ölçülmedi.
- **Karşılaştırma adayı:** [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Apache-2.0, görsel-dil mimarisi. Daha güncel olması bu veri ve Kaggle ortamında daha iyi veya daha hızlı olduğunu kanıtlamaz; önce yalnız metin üzerinde inference, bellek ve eğitim uyumluluğu ölçülmeli. Görsel soru desteği ayrı veri, doğrulama ve deney ister.
- **Arama adayları:** [BGE-M3](https://huggingface.co/BAAI/bge-m3) çok dilli dense/sparse seçenekleri sağlar; [Qwen3-Embedding-0.6B ailesi](https://github.com/QwenLM/Qwen3-Embedding) ve Türkçe retrieval adayı [TurkEmbed4Retrieval](https://arxiv.org/abs/2511.07595) karşılaştırılabilir. Her modelin tam kartı, lisansı, sorgu biçimi, kaynak boyu ve dağıtım şartları kullanılmadan önce doğrulanmalıdır. Genel liderlik tablosu 9. sınıf tarih sorularında üstünlüğü garanti etmez.
- **Eğitim:** [QLoRA](https://arxiv.org/abs/2305.14314) 4-bit taban model üzerinde düşük bellekli adaptör eğitimi sağlar. İlk koşu tek GPU, kısa bağlam, fp16 ve küçük batch ile yapılmalı; bellek, süre ve yazılım sürümleri kaydedilmeli. 2 T4 belleği otomatik olarak tek GPU belleği gibi birleşmez; çoklu GPU ayrı yapılandırma gerektirir. Kaggle donanımı ve kota değişebilir; [Kaggle GPU bilgisi](https://www.kaggle.com/docs/efficient-gpu-usage) ve oturumdaki `nvidia-smi` ile teyit et. Eğitim ortamı canlı servis değildir.

## Veri ve deney protokolü

Önce veri envanteri: onaylı soru, cevap anahtarı, kanıt parçası, bölüm ve öğretmen yazımı örnek sayıları; kaynak sürümleri, lisans ve kullanım izni kaydedilir. Telifli kitap metnini, öğrenci bilgisini ve adaptörü paylaşmadan önce hak ve gizlilik koşulları kontrol edilir. Private Kaggle erişimi ve hesap ayarları doğrulanır; private olması kullanım hakkı sağlamaz. Gerçek öğrenci konuşmaları için uygun izin ve veri minimizasyonu gerekir.

Öğretmen tarafından etiketlenmiş örneklerde `question_id`, kaynak checksum'ı, bölüm, soru metni, öğrenci turu/şık, aşama, onaylı kanıt kimlikleri, beklenen davranış, kısa rehber yanıtı ve inceleme durumu bulunur. Kanıt yok/çelişkili/konu dışı/görsel eksik örneklerinde kanıt listesi boş olabilir ve beklenen davranış geri dönüştür. Gerçek cevap anahtarı eğitim girdisine dahil edilmez; ifşa değerlendirmesi için ayrı erişim kontrollü etiket olarak tutulur. Sentetik diyaloglar ancak öğretmen gözden geçirdikten sonra eğitim adayıdır. Değerlendirmedeki soruları veya çözümlerini sentetik veri üretimine dahil etme.

Soru ve aynı kaynaktan türetilmiş yakın kopyalar aynı grupta kalacak şekilde train/dev/test ayrılır. Asıl test için mümkünse tüm birimler veya kitap bölümleri ayrılarak daha güçlü genelleme sınanır; bölüm bazlı ayrım veri kıtsa ayrıca soru bazlı sonuç da açıkça raporlanır. Yakın kopyalar ve ortak kaynak parçaları için metin benzerliği denetimi yapılır; test seti model, eşik veya prompt seçimi için kullanılmaz. Kaynak parçaları testte erişilebilir olabilir; bu beklenen RAG kurulumudur, fakat aynı kanıta dayalı ezber olasılığı sonuçların yorumunda belirtilmelidir. Bölüm dışı test ayrıca hesaplanır. Örnek ve sınıf sayıları, kapsam ve belirsizlik raporlanır; küçük sette geniş genelleme iddia edilmez.

Karşılaştırmalar, aynı sabit test, kanıt havuzu ve çıktı bütçesinde:

| Deney | Retrieval | Yanıt |
|---|---|---|
| A | mevcut BM25 | mevcut şablon |
| B | BM25 | eğitilmemiş Qwen3-4B |
| C | hibrit BM25 + dense | eğitilmemiş Qwen3-4B |
| D | hibrit | QLoRA adaptörü |
| E | aynı hibrit | Qwen3.5-4B eğitilmemiş, kaynak uygunsa |

B–D farkları ince ayar ve aramanın ayrı katkısını görünür kılar. Mümkünse aynı kanıtı vererek üretici karşılaştırmasını ve altın kanıtla üst sınır deneyini de yap. Reranker ve farklı dense modeller dev kümesinde ayrı ablasyonlardır. Eğitim tamamlanmadan D sonucu yazılmaz.

Ölçümler: retrieval için etiketlenmiş ilgili kanıtta Recall@k, MRR ve bölüm eşleşme oranı; rehberlik için öğretmenlerin kör ve rastgele sıralı değerlendirmesiyle kanıt sadakati, yanlış olgu, erken cevap ifşası, pedagojik yararlılık, Türkçe doğallık ve sesli okunabilirlik; cevapsız/çelişkili örneklerde doğru geri dönüş ve yanlış kesin yanıt oranı. İnsan değerlendirmesinde derecelendirme kuralları, değerlendirici sayısı ve uyuşmazlıklar kaydedilir. Otomatik ölçümler insan incelemesine yardımcıdır; [RAGAS](https://arxiv.org/abs/2309.15217) gibi model tabanlı puanlar bağımsız doğruluk kanıtı değildir.

Gecikmede donanım, model ve quantization, bağlam/çıktı token sayısı, eşzamanlılık, soğuk ve sıcak başlangıç, retrieval ve generation süreleriyle uçtan uca p50/p95 kaydedilir. Kalite metrikleri soru bazında pay/payda ve mümkünse eşleştirilmiş bootstrap güven aralığı ile verilir; öğretmen incelemeleri kör yapılır. Ürün eşikleri pilot verisi ve uzmanlarla belirlenir; eşik seçimi dev setinde yapılır ve test üzerinde önceden ilan edilmiş halde uygulanır. Eksik kanıt veya kritik hata yeterince temsil edilmiyorsa canlıya açma kararı verilemez.

## Çıktılar ve CV

1. Sürüm ve kaynak kökeni kayıtlı, izinleri belgelenmiş Türkçe tarih rehberliği veri şeması ve etiketleme rehberi.
2. Tekrarlanabilir Kaggle eğitimi: model revision, bağımlılık sürümleri, seed, GPU, eğitim ayarları, veri sürümü, adaptör ve çalışma özeti.
3. Aynı test üzerinde baseline, hibrit arama ve QLoRA ablasyonları; hata analizi ve uzman incelemesi.
4. Kanıt gösterimi, geri dönüş ve yerel model servis entegrasyonu; erişilebilirlik ve gecikme ölçümü.
5. Hassas veya telifli içerik paylaşılmadan hazırlanmış yöntem raporu, model kartı ve örnek demo.

Ancak sonuçlar elde edilince CV'de örneğin şu biçimde yazılabilir: “Öğretmen onaylı MEB kaynakları üzerinde Türkçe rehberli soru çözümü için hibrit retrieval ve QLoRA tabanlı açık ağırlıklı model geliştirdim; ayrılmış testte [metrik ve örnek sayısı], [donanım] üzerinde p95 [süre] ölçtüm.” Köşeli alanlar gerçek deney sonuçlarıyla doldurulur; mevcut durumda bunlar iddia edilemez.
