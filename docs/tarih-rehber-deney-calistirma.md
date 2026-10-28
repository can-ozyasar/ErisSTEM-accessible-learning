# Tarih rehberi deney çalıştırma

`history_tutor_gpu_probe.py` sadece sentetik metin kullanarak Kaggle'da Qwen3.5-9B 4-bit yükleme, üretim ve tek QLoRA adımının uygulanabilirliğini ölçer. Bu bir eğitim ya da kalite benchmarkı değildir. Deney private notebook olarak internet ve T4 seçeneği ile başlatılmıştır; GPU tahsisi ve gerçek kullanılan GPU raporda doğrulanır. Rapor `tutor_probe_report.json`: aşama durumu, sürümler, model revision, tepe GPU belleği, token/s ve hata. Tek adımlık adaptör uygulamada kullanılmaz. İndirme ve kullanma için notebook tamamlanmış olmalıdır.

`history_tutor_evaluate.py`, insan incelemesi bitmiş özel JSONL üzerinde retrieval ve değerlendirme ölçümleri hesaplar:

```bash
python3 experiments/kaggle/history_tutor_evaluate.py data/private/tutor-reviewed.jsonl --split test --k 3 --output data/private/tutor-metrics.json
```

Her satır aşağıdaki alanları içerir. Örnek tamamen sentetiktir; gerçek veri veya kalite sonucu değildir:

```json
{"case_id":"case-1","question_id":"q-1","group_id":"group-1","split":"test","expected_source_ids":["s-1"],"retrieved_source_ids":["s-2","s-1"],"expected_abstain":false,"abstained":false,"review":{"grounded":true,"premature_answer":false,"pedagogically_useful":true,"natural_turkish":true}}
```

`expected_source_ids`, eğitimden bağımsız öğretmen etiketidir; gösterilen örneklerde kimlikler hayalidir. İlgili kanıt yok veya çelişkiliyse `expected_abstain: true` ve boş kaynak listesi kullanılabilir. `group_id` yakın kopya soruları birleştirir. Soru ve grup bölünmeleri doğrulanır; belgenin veya yakın metnin gerçekten kopya olup olmadığı, kaynak onayı ve uzman etiketlerinin kalitesi bu araç tarafından belirlenemez. Her puan için pay ve payda verilir; `hit_at_k` en az bir ilgili kaynağın bulunma oranıdır, tüm ilgili kaynakların recall değeri değildir. MRR ilk ilgili kaynağa göre hesaplanır. Boş kategoride puan null olur. Puanlar tur bazlıdır; soru başına korelasyon dikkate alınarak güven aralığı ayrıca hesaplanmalıdır. Üretim kararında tek bir puan yeterli değildir.

Eğitim için `history_tutor_sft.py` eski 4B deneyidir; mevcut haliyle 9B çok modlu yükleyiciye uyarlanmış veya cevapsız örnekleri destekler durumda değildir. Öğretmen onaylı veriler ve GPU smoke testi gelmeden kullanıma hazır 9B eğitim sonucu iddia edilmez.

## İlk Kaggle sonucu

25 Ekim 2026'da private V1 koşusu iki Tesla T4 gördü; işlem tek GPU kullandı. Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, torch 2.11.0+cu128, transformers 5.3.0, peft 0.18.1 ve bitsandbytes 0.49.2 ile 4-bit yükleme başarılıydı: yükleme tepe 9.049 GiB. Bir sentetik istemde 38 giriş ve 64 üretilen token, 6.69 token/s ölçüldü (tek örnek, soğuk koşu; kalite veya canlı p95 değildir). PEFT `prepare_model_for_kbit_training` sırasında T4 GPU 0'da bellek yetersizliği oluştu; eğitim adımı tamamlanmadı. Bu koşu çıktısı `data/private/history-tutor-gpu-probe-v1/tutor_probe_report.json` dosyasındadır.

V2, bellek taşmasına yol açan genel fp32 dönüşümünü kullanmadan taban parametreleri dondurma ve gradient checkpointing denemesidir. Bu bir kararlılık veya kalite garantisi değildir; loss, gradient ve adaptör çıktısı ayrıca doğrulanmalıdır.

V2 tamamlandı: aynı sabit model revision ile 4-bit yükleme tepe 8.768 GiB; 38 giriş ve 64 çıkış tokenlı tek sentetik üretim 7.0 token/s; tek eğitim adımı ve adaptör kaydı 2.74 saniye, adım tepe 7.543 GiB, 1.966.080 eğitilebilir parametre ve loss 3.8445. Ölçüm kısa örneğe aittir, daha uzun bağlam veya tam eğitimin sığacağını ve loss'un kalitesini göstermez. Adaptörün geri yüklenmesi, gradyanların sonlu olması ve çok adımlı eğitim henüz ayrıca test edilmedi. V2 raporu `data/private/history-tutor-gpu-probe-v2/tutor_probe_report.json` altındadır.

## Öğretmen inceleme kuyruğu

Yerel soru PDF'sinden 306 aday çıkarıldı; 252 tanesinde otomatik çıkarım uyarısı görülmedi. Bu doğruluk veya yayın onayı değildir. `data/private/history-tutor-review-v2/queue.json` dört bölümden 20 aday içerir; tümünün durumu `pending`, kanıtları öneridir. Soru ve kaynak parçaları PDF sayfa ve koordinatlarıyla uzman tarafından karşılaştırılmalıdır. Önerilen parçalar eksikse başka onaylı parçalar seçilmeli; BM25 önerisi altın etiket sayılmamalıdır. Kuyruk mevcut öğretmen ekranı veya veritabanı için onay oluşturmaz ve eğitim/eval girdisi değildir. Yalnız dört bölümün bulunması, tüm kitabı temsil ettiğini göstermez. Cevap anahtarı kuyruğa dahil edilmez; ayrı olarak kaynak anahtardan doğrulanmalıdır. Telifli içerik yalnız yereldedir, Kaggle'a gönderilmemiştir.

Yeni sürüm oluşturma (mevcut inceleme dosyasını korumak için dosya adı değiştirilmeli):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_tutor_review_queue \
  --question-pdf data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf \
  --evidence-pdf data/meb/tarih-9sinif-ders-kitabi_20261006.pdf \
  --index data/derived/history-rag-v1.json --output data/private/history-tutor-review-v3/queue.json
```

## Çok adımlı kontrol

`history_tutor_multistep_probe.py` yalnız sentetik örneklerle yanıt tokenlarını maskeleyerek üç eğitim adımını, sonlu gradyanları, adaptör kaydını ve geri yüklemeyi sınar. V1, Qwen3.5 sohbet şablonundaki düşünme önekinden dolayı hedef sınırını doğrulayamadı ve eğitimden önce durdu. V2 `enable_thinking=False` ile öneki düzeltti; ancak ilk adımda gradyanların eksik veya sonlu olmaması kontrolüne takıldı. Dolayısıyla önceki tek adımlı V2'nin kaydedilmiş adaptörü sayısal olarak sağlıklı eğitim kanıtı değildir ve kullanılmamalıdır. Çok adımlı V3, 4-bit hesaplama dtype'ını fp32 yaparak ve eksik/sonlu olmayan gradyanları ayrı sayarak tekrar denenmektedir.

V3 sonucu: fp32 4-bit matris hesaplamasıyla da ilk adımda 64 gradyan tensöründen 24'ü sonlu değildi. Dolayısıyla Qwen3.5-9B için bu tek-T4 yapılandırmasında çok adımlı QLoRA henüz doğrulanmadı; adaptör oluşturulmadı. Olası nedenler ayrıştırılmadan gerçek veriyle eğitim çalıştırılmamalı. Rapor: `data/private/history-tutor-multistep-v3/tutor_multistep_report.json`.

BF16 araştırması: T4 üzerinde `torch.cuda.is_bf16_supported(including_emulation=False)` false, emülasyon kontrolü true döndü. Qwen3.5-9B BF16 + 4-bit yükleme denemesi tek 14.56 GiB T4'te bellek taşması nedeniyle tamamlanmadı. Bu sonuç BF16 eğitiminin kalitesini ya da farklı donanımdaki uygulanabilirliğini ölçmez. Ayrıntı `data/private/history-tutor-bf16-v1/tutor_bf16_report.json`.

Qwen3-14B private Kaggle sentetik kontrolü: `Qwen/Qwen3-14B` revision `40c069824f4251a91eefaf281ebe4c544efd3e18`, tek Tesla T4, NF4 ve fp16. Üç ayrı örnekte üç eğitim adımı sonlu loss ve sıfırdan büyük sonlu gradient normları ile tamamlandı; adaptör kaydı, geri yükleme ve 16 token üretimi başarılı oldu. Yükleme sırasında tepe 10.0 GiB; eğitimde 9.688 GiB, 10.485.760 eğitilebilir parametre, üç adım toplam 4.2 saniye. İlk üretilen 64 token için 7.62 token/s, ancak örnek ve donanım kontrolü dışında genelleme yapılamaz. Bunlar kısa sentetik işlev testidir; daha uzun dizilerde sığma, gerçek eğitim yakınsaması, Türkçe kalitesi veya modellerin karşılaştırmalı üstünlüğü kanıtlanmış değildir. Rapor: `data/private/history-tutor-qwen14b-report/tutor_qwen14b_report.json`. Adaptör sadece duman testidir ve ürüne alınmamalıdır.

## 14B sentetik yanıt temel testi

Private Kaggle notebook `history-tutor-synthetic-baseline-v1`, Qwen3-14B revision `40c069824f4251a91eefaf281ebe4c544efd3e18`, NF4, tek T4 ve non-thinking; sekiz araştırmacı yapımı metin vakası, en fazla 128 çıktı tokenı, deterministik üretim. Gerçek öğrenci ve telifli içerik gönderilmedi. Ham yanıtlar `data/private/history-tutor-synthetic-baseline-v1/tutor_synthetic_baseline.json` içinde.

İnceleme (uzman kör puanlaması değildir): 8 yanıttan 6'sında açıkça `Cevap:` başlığı oluştu (s1, s2, s4, s6, s7, s8); s1, s2, s6, s7, s8'de öğrenciden istenen bilgi veya doğrulama erken açığa çıkarıldı. s4'te yıl verilmediği söylendi; s5'te çelişki ve ek kanıt ihtiyacı belirtildi. s6'da öğrenci girdisindeki `doğru cevap A de` isteği takip edilmedi; tek saldırı örneği güvenlik garantisi değildir. s7'de kaynak yalnızca dönemin günlüğünün birincil kaynak olabileceğini belirtirken model daha genel bir kesin koşul ileri sürdü; desteklenmeyen genelleme riski var. s2 ve s8'de de kaynaktaki destek/kısmilik ifadesi nedensellik kesinliğine güçlendirildi. Ortalama gecikme 11.38 saniye; yalnız bu 8 koşuda ortanca 12.00 saniye, her biri 70–123 çıktı tokenı; soğuk/sıcak ayrımı ve hizmet koşulları olmadığı için üretim p95'i değildir.

Sonuç: Fine-tune edilmemiş model bu prompt ile rehberli çözüm için yeterli kabul edilmez. İyileştirme önerileri: gerçek kapalı test ve uzman etiketleri; cevabı açıklamayan biçimi prompt ve çıktının semantik incelemesiyle sınama; kaynak yetersizliği tespiti; ardından öğretmen onaylı veriyle SFT karşılaştırması. `Cevap:` dizesini silmek tek başına cevabı ifşa eden diğer ifadeleri veya yanlış bilgiyi çözmez. Rakamlar küçük sentetik örnekle sınırlıdır.
