# ErişSTEM deney ve rapor kaydı

Bu belge, bitirme raporu ve makale için teknik kararların izini tutar. Kaynak
kitap metni, öğrenci verisi, ses kaydı, izin mesajı, dinleyici kimliği ve gizli
Kaggle çıktıları burada saklanmaz.

## Araştırma soruları

1. Kaynak bağlı RAG, tarih sorularında cevabı doğrudan vermeden kanıt temelli
   bir öğrenme desteği sağlayabilir mi?
2. Yerel TTS, ağ bağımlılığı olmadan erişilebilir sesli okumayı yeterli
   gecikmeyle sağlayabilir mi?
3. Hazır çok dilli TTS ve alan uyarlaması, Türkçe tarih anlatımında hafif yerel
   TTS tabanına göre anlamlı bir iyileşme sağlıyor mu?

## TTS mimarisi

| Katman | Karar | Kanıt / artefakt |
|---|---|---|
| Hızlı yerel ses | Piper `tr_TR-dfki-medium`, Docker iç ağı | `apps/tts/Dockerfile`, `docs/yerel-tts.md` |
| Ses metni | Kaynak metni değişmeden tutulur; yalnız ses girdisinde MÖ, Roma yüzyılı ve doğrulanmış özel ad kuralları uygulanır | `apps/api/app/history_speech.py` |
| Tekrar dinleme | Doğrulanmış içerik WAV'ı özel volume içinde özet anahtarıyla önbelleğe alınır | `apps/api/app/local_tts.py` |
| Kalite adayı | Chatterbox Multilingual V3, Türkçe `tr` | `experiments/kaggle/tts_chatterbox_v3_reference_runner.py` |
| Öğrenci yayını | Otomatik sesletim kapısı ve kör dinleyici çalışması geçmeden kapalı | `apps/api/app/pipeline/tts_quality.py`, `tts_listener_study.py` |

## Karar günlüğü

| Tarih | Konu | Karar | Gerekçe | Durum |
|---|---|---|---|---|
| 2026-10 | Öğrenci giriş akışı | Öğrenci ve öğretmen için sağa-sola kaydırmalı tek kartlı menü kullanıldı | Çok sayıda düğme ve metin, dokunarak ve ekran okuyucuyla gezinmeyi zorlaştırıyordu | Uygulandı |
| 2026-10 | Soru çözümü | Cevabı doğrudan açıklayan akış reddedildi; soru kökü, şık ve kaynak kanıt üzerinden rehberli diyalog kullanıldı | Öğrenme ve hatırlama, cevabı görmekten daha öncelikli | Uygulandı |
| 2026-10 | RAG kaynağı | MEB kitabının ham PDF'si yerine sayfa, başlık, konu ve kaynak koordinatı bağlı bölümler kullanıldı | Görsel tasviri, QR ve kaynak dışı PDF mobilyası öğrenciyi yanıltmamalı | Uygulandı |
| 2026-10 | Görsel anlatım | Otomatik görsel betimlemeleri doğrulanmadan öğrenciye açılmıyor | Modelin görsel hakkında uydurma bilgi vermesini önlemek | Uygulandı |
| 2026-10 | TTS sağlayıcısı | Uzak TTS API yerine Docker iç ağında yerel Piper seçildi | Gecikme, maliyet, gizlilik ve çevrimdışı çalışma | Uygulandı |
| 2026-10 | Dil/ses değişimi | İngilizce özel adlarda ikinci ses veya İngilizce tarayıcı sesi kullanılmadı | Cümle ortasında ses değişimi tutarsız ve erişilebilirlik açısından rahatsız ediciydi | Uygulandı |
| 2026-10 | Tarih telaffuzu | MÖ, Roma yüzyılı, kaynak harfi ve belirli kurum adı için görüntü metninden ayrı konuşma normalizasyonu eklendi | PDF görünümü korunurken Türkçe sesletim düzeltildi | Uygulandı |
| 2026-10 | Tekrar dinleme | Ses yeniden üretimi yerine içerik özetli kalıcı WAV önbelleği eklendi | Aynı metnin tekrarında Piper gecikmesini kaldırmak | Uygulandı |
| 2026-10 | Büyük TTS modeli | Chatterbox Multilingual V3 kalite adayı seçildi | Tarih akustik pilotunda Piper'a göre daha doğal ses için aday sinyali verdi | Kaggle doğrulaması sürüyor |
| 2026-10 | Chatterbox V2 | Varsayılan kalite adayı yapılmadı | Mevcut kalite kapılarında yeterli sonucu vermedi | Elendi |
| 2026-10 | Chatterbox'ı canlı çalıştırma | Mevcut CPU bilgisayarda gerçek zamanlı varsayılan yapılmadı | Yerel cihazda CUDA GPU yok; büyük modelin gecikmesi ve bellek ihtiyacı uygun değil | Ertelendi |
| 2026-10 | Fine tune | İlk V3 referans-ses deneyi bitmeden eğitim başlatılmadı | Temel modelin yeterli olduğu yerde gereksiz veri, GPU ve kalite riski oluşmamalı | Beklemede |
| 2026-10 | Eğitim verisi | MEB kitabı metni test ve alan sözlüğü olarak ayrıldı; doğrudan ses eğitimi verisi sayılmadı | TTS fine tune için izinli insan sesi ve eşleşen transkript gerekir | Uygulandı |
| 2026-10 | Referans ses verisi | Harici ses kaynağının izin mesajı depolanmadı | Konuşmacının özel iletişim verisi yerelde veya Git'te tutulmamalı | Uygulandı |

## Kullanılan teknoloji ve bileşen envanteri

| Alan | Kullanılan bileşen | İşlev |
|---|---|---|
| Web arayüzü | React, TypeScript, Vite | Öğrenci, öğretmen, soru çözme ve kaynak okuma ekranları |
| API | FastAPI, Python | Kaynak erişimi, TTS sınırı, RAG ve öğretmen denetimi |
| Veri | PostgreSQL, yerel private dosya alanı | İş akışı, sürüm ve private kaynak artefaktları |
| PDF işleme | PyMuPDF | Sayfa görüntüsü, metin bölgesi ve bağlantı koordinatları |
| Yerel TTS | Piper, ONNX | Hızlı Türkçe yerel ses üretimi |
| Kalite TTS | Chatterbox Multilingual V3 | Kaggle GPU'da referans sesli Türkçe tarih sentezi |
| GPU deneyi | Private Kaggle T4 Notebook | Büyük model sentezi, ASR ve karşılaştırma |
| TTS değerlendirme | Whisper/ASR, kritik belirteç kontrolü, kör dinleme | Otomatik ve insan temelli kalite kapısı |
| RAG | Konu eşleşmesi, öğretmen onaylı parçalar, Türkçe BM25 | Soruya kaynak bağlı rehberlik |
| Ses önbelleği | SHA-256 anahtarlı private Docker volume | Tekrar dinlemede WAV'ı doğrudan döndürme |

## Denenen ve bırakılan ya da sınırlandırılan yaklaşımlar

| Yaklaşım | Sonuç | Rapor notu |
|---|---|---|
| Tarayıcının rastgele uygun sesi | Sınırlandırıldı | Türkçe dışı veya farklı sesin sessizce seçilmesine izin verilmedi |
| Metin içindeki yabancı ad için ayrı İngilizce ses | Bırakıldı | Tek cümlede iki ses öğrenme akışını bozdu |
| Ham PDF/OCR metnini doğrudan RAG ve TTS'e verme | Bırakıldı | Başlık, görsel, soru ve kaynak bağlamı ayrıştırılmadan güvenilir değil |
| Otomatik görsel açıklama | Bırakıldı | Öğretmen doğrulaması yokken öğrenciye bilgi olarak sunulmuyor |
| Cevap anahtarını destekçi modele açma | Bırakıldı | Öğrencinin cevabı doğrudan görmesini önlemek için sunucu sınırının dışında tutuluyor |
| Chatterbox V2 | Elendi | V3 ve diğer adaylarla yapılan mevcut kalite elemesinde yeterli değil |
| Kaggle'ı canlı öğrenci altyapısı yapmak | Bırakıldı | Kaggle yalnız süreli private GPU deneyi; öğrenci uygulaması yerel çalışır |
| MEB kitabı metniyle TTS eğitimi | Bırakıldı | Kitap metni değerlendirme ve alan uyarlama testi; fine tune için ses-transkript çifti gerekir |

## Her deney kaydında zorunlu alanlar

Yeni bir deney tamamlandığında bu belgeye aşağıdakiler eklenir:

1. Amaç ve test edilen hipotez.
2. Girdi kapsamı: yalnız sayfa/örnek sayısı, içerik metni olmadan.
3. Model, sürüm, sabitlenmiş ağırlık ve çalışma ortamı.
4. Ayarlar: ses profili veya eğitim hiperparametreleri.
5. Ölçülen metrikler ve temel sürüm karşılaştırması.
6. Başarısızlıklar, hata türleri ve sonraki karar.
7. Öğrenci yayınına açık/kapalı durumu.

## Ölçülmüş ilk gecikme sonucu

20 Ekim 2026 tarihinde, yerel tarih bölümü ses uç noktasında:

| Durum | Yanıt süresi |
|---|---:|
| İlk Piper sentezi | 2,486 sn |
| Aynı doğrulanmış metnin kalıcı WAV önbelleğinden dönüşü | 0,003 sn |

Bu ölçüm tek kısa tarih bölümü üzerinde yapılmıştır; genel gecikme iddiası
değildir. Ağ, oynatma başlangıcı ve farklı metin uzunlukları ayrı raporlanır.

## Chatterbox V3 tarih deneyi

| Alan | Kayıt |
|---|---|
| Deney türü | Fine tune değil; hazır V3 ile referans ses tabanlı sentez |
| Girdi | 14 kaynak bağlı, private tarih değerlendirme birimi |
| Referans ses | Tek teknik olarak uygun kısa konuşma kaydı; kimlik ve ses dosyası bu repoda tutulmaz |
| Çalışma ortamı | Private Kaggle T4 notebook |
| Notebook | `muhammedcanozyasar/eristem-history-tts-chatterbox-v3-v2` |
| Başlatılma | 20 Ekim 2026; sonuç bekleniyor |
| Yayın durumu | Öğrenci yayını kapalı |

## Fine tune çalışması için raporlanacaklar

Fine tune yalnız açık izinli tek konuşmacı WAV ve transkript çiftleri ile
değerlendirilir. Kaynak ses dosyası veya izin mesajı depolanmaz. Her deney için
yalnız şu özetler rapora girer:

- model ve sabitlenmiş sürüm;
- eğitim/validation kayıt sayısı, toplam süre ve tür dağılımı;
- GPU, hassasiyet, batch, learning rate, epoch ve eğitilebilir katmanlar;
- WER, CER, kritik tarih terimi doğruluğu ve hata türleri;
- kör dinleyici A/B tercih oranı, anlaşılırlık ve ciddi artefact sayısı;
- sentez gecikmesi, gerçek zaman katsayısı ve önbellek gecikmesi;
- model/adapter boyutu, yerel çalıştırma gereksinimi ve lisans özeti.

## Raporlama kuralı

Bir yüzde, yalnız aynı kapalı test kümesinde temel model ve aday sürüm
karşılaştırıldıysa rapora yazılır. Hazır V3 karşılaştırması, fine tune sonucu
olarak sunulmaz. Tek dinleyici veya küçük örneklem bulgusu pilot olarak
etiketlenir.
