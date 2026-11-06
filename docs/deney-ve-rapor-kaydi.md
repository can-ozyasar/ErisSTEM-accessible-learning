# ErişSTEM deney ve rapor kaydı

Bu belge, bitirme raporu ve makale için teknik kararların izini tutar. Kaynak
kitap metni, öğrenci verisi, ses kaydı, izin mesajı, dinleyici kimliği ve gizli
Kaggle çıktıları burada saklanmaz.

TTS için kaynaklı kalite araştırması, ölçütler ve deney karar kuralı
`docs/tts-kalite-arastirma-ve-deney-plani.md` belgesindedir.

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
| 2026-10 | Bilgi grafiği mimarisi | Kitap ağacı, kanıt atomu, anlamsal ilişki grafiği ve retrieval indeksi ayrıştırılmış; yalnız sürüm/sayım taşıyan öğretmen mimari haritası eklendi | Kaynak metni veya soru içeriğini açmadan kapsam, onay, zaman ilişkisi ve kabul kapılarını izlemek | Uygulandı; AYT private snapshot üretimi ve insan onaylı altın grafik sırada |
| 2026-10 | Görsel anlatım | Otomatik görsel betimlemeleri doğrulanmadan öğrenciye açılmıyor | Modelin görsel hakkında uydurma bilgi vermesini önlemek | Uygulandı |
| 2026-10 | TTS sağlayıcısı | Uzak TTS API yerine Docker iç ağında yerel Piper seçildi | Gecikme, maliyet, gizlilik ve çevrimdışı çalışma | Uygulandı |
| 2026-10 | Dil/ses değişimi | İngilizce özel adlarda ikinci ses veya İngilizce tarayıcı sesi kullanılmadı | Cümle ortasında ses değişimi tutarsız ve erişilebilirlik açısından rahatsız ediciydi | Uygulandı |
| 2026-10 | Tarih telaffuzu | MÖ, Roma yüzyılı, kaynak harfi ve belirli kurum adı için görüntü metninden ayrı konuşma normalizasyonu eklendi | PDF görünümü korunurken Türkçe sesletim düzeltildi | Uygulandı |
| 2026-10 | Tekrar dinleme | Ses yeniden üretimi yerine içerik özetli kalıcı WAV önbelleği eklendi | Aynı metnin tekrarında Piper gecikmesini kaldırmak | Uygulandı |
| 2026-10 | Büyük TTS modeli | Chatterbox Multilingual V3, geniş tarih üretimi için aday seçildi | Kör pilotta tek dinleyici 14/14 örnekte V3'ü tercih etti; V3 doğru okuma 12/14, Piper 6/14 işaretlendi | Geniş test sürüyor; öğrenci yayını kapalı |
| 2026-10 | Chatterbox V2 | Varsayılan kalite adayı seçilmedi | Kapalı metinlerdeki ASR ölçümü temel modeli geçmedi; doğallık ve konuşmacı benzerliği henüz kör dinleme ile ölçülmedi | Yeni, koşullaması eşlenmiş deney bekliyor |
| 2026-10 | Chatterbox'ı canlı çalıştırma | Mevcut CPU bilgisayarda gerçek zamanlı varsayılan yapılmadı | Yerel cihazda CUDA GPU yok; büyük modelin gecikmesi ve bellek ihtiyacı uygun değil | Ertelendi |
| 2026-10 | Fine tune | İlk V3 referans-ses deneyi bitmeden eğitim başlatılmadı | Temel modelin yeterli olduğu yerde gereksiz veri, GPU ve kalite riski oluşmamalı | Beklemede |
| 2026-10 | Eğitim verisi | MEB kitabı metni test ve alan sözlüğü olarak ayrıldı; doğrudan ses eğitimi verisi sayılmadı | TTS fine tune için izinli insan sesi ve eşleşen transkript gerekir | Uygulandı |
| 2026-10 | Referans ses verisi | Harici ses kaynağının izin mesajı depolanmadı | Konuşmacının özel iletişim verisi yerelde veya Git'te tutulmamalı | Uygulandı |
| 2026-10 | AYT Tarih-2 MEB kanıtı | 10, 11 ve checksum doğrulanmış 12. sınıf MEB kitapları tek private inceleme corpus'unda birleştirildi | Millî Mücadele, Lozan ve Atatürkçülük kanıtı 12. sınıf kitabı olmadan eksikti; ham PDF ve soru içeriği ürün/Kaggle alanına taşınmadı | Öğretmen PDF kırpımı incelemesi bekliyor |
| 2026-10 | PDF içindekiler ayrıştırması | Sabit 9. sınıf sayfa sınırları kaldırıldı; satır kırığı, blok sırası ve ayrı sayfa numarası onarımı eklendi | Yeni MEB kitaplarında sabit sınır yanlış kaynak aralığı üretiyordu; üç gerçek kitap ve birim testleriyle doğrulandı | Uygulandı |
| 2026-10 | AYT kanıt önerisi | Yıl etiketi bağlanmış adaylar için checksum bağlı, onaysız MEB kanıt önerisi üretildi | Otomatik eşleşme kaynak onayı değildir; yıl bağlanamayan adaylar ve tüm öneriler öğrenci RAG'ından kapalı tutulur | Öğretmen incelemesi bekliyor |
| 2026-10 | AYT yıl bağlama | Dikey yakınlık kuralı kaldırıldı; yıl etiketi yalnız aynı soru kutusundaki PDF koordinatıyla bağlanıyor | İki sütunlu sayfada komşu sütunun yılı yanlış atanmıştı; 2018–2021 adayları kapsam dışı, 2022–2026 adayları ayrı tutuluyor | Uygulandı |
| 2026-10 | AYT öneri havuzu | Otomatik öneri yalnız `review_for_approval` ders bilgisi adaylarıyla sınırlandı | Etkinlik/yönerge, görsel açıklaması ve belirsiz parçalar BM25 ile yüksek çıksa da kanıt önerisi değildir | Uygulandı; PDF kırpımı incelemesi bekliyor |
| 2026-10 | AYT PDF kırpım incelemesi | 2022–2026'ya bağlı 27 aday için ilk üç MEB önerisi private HTML/PDF kırpım paketi olarak üretildi | Öğretmen metin katmanındaki bozulmaya değil, kaynak PDF görünümüne göre karar vermeli; paket cevap vermez ve onay kaydı yazmaz | Uygulandı; 81 kırpım inceleme bekliyor |
| 2026-10 | AYT retrieval ön incelemesi | Bağımsız öğretmen rolündeki agent, 27 güncel adayın ilk üç önerisini onay vermeden sınıflandırdı: 9 primary adayı, 8 sınırlı bağlam, 10 yetersiz | Öneri kalitesi henüz yeterli değil; agent sonucu insan öğretmen yerine geçmez ve yalnız hedefli yeniden-getirme ile altın etiketleme sırasını belirler | Uygulandı; insan PDF kırpım incelemesi bekliyor |
| 2026-10 | Retrieval ölçüm kapısı | PDF kırpımı kontrolü, primary rolü ve inceleyen bilgisi olmadan BM25 değerlendirmesine girmeyen private altın kanıt şablonu eklendi | Dense/RRF/reranker deneyi, taban çizgi ve kapalı kaynak kimlikleri olmadan anlamlı karşılaştırma üretmez | Uygulandı; etiket bekliyor |
| 2026-10 | 9. sınıf kanıt kapsama deneyi | 9. sınıf kitabı ürün corpus'una katılmadan aynı 27 AYT bağlı soruda ayrı checksum corpus'uyla yeniden getirildi | 9. sınıfın gerçekten eksik kanıtı kapatıp kapatmadığı, mevcut önerileri bozmadan ölçülmelidir | İlk öneri 1 soruda değişti; 2 soruda ilk üçe 9. sınıf adayı girdi; PDF kırpım incelemesi bekliyor |
| 2026-10 | Kaynak alıntısı ve corpus sürümü | Tırnaklı ders kitabı kaynakları otomatik öğrenci kaynağı olmadan `manual_review` keşif kuyruğuna alındı; corpus checksum'ına indeks özeti eklendi | Eski filtre doğrudan tarih ilişkilerini sessizce dışarıda bırakıyordu; yalnız PDF checksum'ı çıkarım politikası değişimini yakalamıyordu | Uygulandı; yeni alıntılar yalnız private PDF kırpım incelemesine açık |
| 2026-10 | Zorunlu ilişki kısıtları | Geniş BM25 sonucu yerine kavram veya kişi–olay maddelerinin her birini arayan private keşif aracı eklendi | Geniş bağlam, doğrudan kanıt değildir; eksik zorunlu bağda sistem çekimser kalmalı | Eski Türk kavramı için 8 manual-review kesit; Türgiş–Karluk–Talas için çekimser; PDF incelemesi bekliyor |
| 2026-10 | Ham PDF geri dönüşü | Normal blok filtresinin dışında kalan, checksum bağlı PDF metin blokları yalnız kırpım incelemesi için tarandı; alıntılar `quoted_source` olarak işaretlendi | Kısa veya tırnaklı kaynak blokları doğrudan öğrenci kaynağı değildir, fakat hedefli kanıt keşfinde sessiz kapsam kaybını ölçmek gerekir | Hatun–kağan ve otağ–hükümdarlık ilişkileri için aday bulundu; `otağ = hükümdarın çadırı` eş anlamı bulunmadı; insan onayı bekliyor |
| 2026-10 | AYT kanıt rol inceleme formu | Private PDF kırpım paketi, rol seçimi ve checksum bağlı retrieval-gold JSON dışa aktarımı yapan çevrimdışı forma dönüştürüldü | İnceleyen kişiden kaynak metnini veya JSON şemasını elle düzenlemesi beklenmemeli; cevap anahtarı formda bulunmamalı | 9 yüksek öncelikli soru için form üretildi; insan onayı bekliyor |
| 2026-10 | AYT grafik ön doldurma | 9 öncelikli soru ve 22 zorunlu iddia üzerinde yalnız birebir, iki uçlu kanıtla ilişki önerisi sınandı | Mevcut adayların tamamı kısmi/alias temelli kaldığı için 0 ilişki önerisi üretildi; düşük güvenli bağlantıların grafiğe sızması önlendi | İnsan PDF kesiti onayı ve daha güçlü kanıt keşfi bekliyor |
| 2026-10 | Harici kanıt ikinci görüş pilotu | Private 12 iddia–kesit çifti, cevap anahtarı ve öğrenci verisi olmadan deneysel olarak sınıflandırıldı | Karar yalnız PDF kesiti inceleme sırasını önceliklendirebilir; hiçbir onayı otomatikleştiremez | 1 doğrudan, 3 kısmi, 8 ilgisiz; öğrenci akışında kapalı |

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
| Chatterbox V2 | Askıda | ASR anlaşılabilirlik kapısında temel modeli geçmedi; insan dinleme ve konuşmacı benzerliği olmadan kesin kalite kararı verilmez |
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
| Başlatılma | 20 Ekim 2026 |
| Sentez sonucu | 14/14 WAV üretildi, 0 hata; toplam 89,858 sn, ortalama 6,418 sn/birim |
| Ortam | NVIDIA Tesla T4; model revision `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18` |
| Sonraki ölçüm | Aynı 14 örneğin Piper ve V3 WAV'ları için private Whisper ASR karşılaştırması başlatıldı |
| ASR sonucu | Piper ortalama karakter doğruluğu %94,8 ve kritik kaçırma 7/14; V3 %94,9 ve kritik kaçırma 9/14. Otomatik sonuç tek başına kalite veya yayın kararı değildir. |
| Kör dinleme sonucu | Tek dinleyici 14/14 örnekte V3'ü daha doğal seçti. V3 doğru okuma 12/14, Piper 6/14 olarak işaretlendi. Tek dinleyicili pilot, genelleme veya öğrenci yayını kanıtı değildir. |
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

## V3 fine tune altyapısı ve smoke koşusu

20 Ekim 2026 tarihinde fine tune için tekrar üretilebilir bir private Kaggle
hattı hazırlandı. Bu koşu doğrudan kalite iddiası taşımaz; önce veri filtresi,
V3 ağırlık uyumu, GPU belleği ve artefact geri indirme yolunu doğrular.

| Alan | Karar |
|---|---|
| Temel model | Chatterbox Multilingual V3, sabit model revision `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18` |
| Eğitilen bölüm | Yalnız T3; ses kodlayıcı ve S3Gen dondurulmuştur |
| Eğitim kodu | İlk smoke için topluluk T3 betiği `bf2017ddc1266acedb23189a4e9c823c91be8586` denendi; kalite V1 doğrudan T3 döngüsüne geçti, V2 bu döngünün hedef hizalamasını düzeltti |
| Kaynak snapshot | `omersaidd/tts_nisan_kumru_tur` revision `678712b026da89058feb010886de23983cc8563b`; ses veya transkript bu repoya alınmaz |
| Seçim | İlk melodili kayıt dışarıda; süre, ses seviyesi, clipping, etkin konuşma oranı ve metin uzunluğu filtresi |
| Smoke kapsamı | Yaklaşık 9 dakika temiz ses, 2 güncelleme adımı; kalite adayı değildir |
| İlk hedef kapsam | Yaklaşık 3 saat 15 dakika seçili ses, %8 sabit tohumlu held-out validation, 600 güncelleme adımı; V2 kalite koşusunda tüm eğitim kayıtlarını görmek için 1.500 adıma çıkarıldı |
| Saklanacak model | `t3_mtl23ls_v3.safetensors`; SHA-256 doğrulamasıyla yerelde `data/private/` altına indirilir |

Smoke notebook: `muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-smoke-v1`.
Bu bölümde eğitim sahibinin izin mesajı, ham ses veya transkript saklanmaz.
Smoke başarılı olduktan sonra aynı kapalı tarih setinde hazır V3 ve fine tune
adayını aynı koşullarda sentezleyip otomatik hata analizi ile kör dinlemeye
tekrar sokmak zorunludur.

İlk smoke koşusu, filtrelenmiş corpus üretiminden sonra Kaggle taban
imajındaki `torchvision`/`peft` ile güncel Transformers paketinin çakışması
nedeniyle eğitim başında durdu. Bu bir ses, veri veya model ağırlığı hatası
değildir. İkinci koşuda bu iki kullanılmayan paket kaldırıldı; `transformers`
`4.52.4`, `datasets` `3.6.0` ve `accelerate` `1.7.0` sabitlendi. Bu koşuda
eğitim betiğinin gömülü eski Chatterbox kopyasının resmî V3 paketinden önce
yüklenmesi nedeniyle V3 parametre imzası bulunamadı. Üçüncü koşu bu kopyayı
çalışma alanından kaldırır ve resmî `from_pretrained(..., t3_model="v3")`
imzasını eğitimden önce zorunlu olarak doğrular. Private notebook
`muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-smoke-v3`, 23 Ekim
2026 tarihinde T4 üzerinde başlatıldı. Sonuç alınmadan kalite eğitimi
başlatılmaz.

## Arayüz ve sesli erişim güncellemesi — 23 Ekim 2026

Yerel öğrenci uygulaması Docker Compose ile açıldı; web ve API sağlık istekleri
başarılıydı. Giriş ve öğrenci kaydırmalı menülerine görünür önceki/sonraki
denetimleri eklendi. Kart değişimi, sesli keşif etkinse aynı yerel TTS yolu
üzerinden duyurulur. Öğretmen girişinde soru ve kaynak incelemesi ana görev
olarak öne çıkarıldı; diğer araçlar açılır bölüme alındı. Soru çözümünde okuma
üstte, isteğe bağlı destek ve soru ilerletme yanıt akışının ardından yer alır.
Destekçi yanıtının seslendirilmesi artık ekranda görünen metni kullanır;
yeniden üretilmiş farklı bir yanıtın okunması önlenir. Aynı metnin sesi oturum
içi sınırlı önbellekten tekrar kullanılabilir.

Doğrulama: web derleme, lint, 15 birim testi ve giriş/öğrenci menüsü tarayıcı
testi geçti. Gerçek öğrenci kullanılabilirlik denemesi ayrıca yapılmalıdır.

## Çoklu erişim ihtiyaçları için arayüz — 23 Ekim 2026

Önceki kaydırmalı akışta uygulama, dokunmatik bağlantılara ek bir çift dokunma
koşulu koyuyordu. Telefon ekran okuyucusunun kendi etkinleştirme hareketiyle
çakışma riski nedeniyle bu koşul kaldırıldı. Kaydırma yanında düğme ve ok tuşu
korundu. Görsel dil açık maviye taşındı; temel metin büyütüldü. Kalıcı yazı
boyutu, yüksek kontrast ve hareket azaltma tercihleri eklendi. Soru değişiminde
odak yeni başlığa gider; seçili şık ayrıca “Seçildi” metniyle işaretlenir.
En büyük yazıda saptanan kart ve öğretmen gezinmesi taşmaları giderildi.

Derleme, lint ve giriş/öğrenci menüsü, dokunma, sesli keşif, tercih saklama,
yüksek kontrast ve soru odağı için hedefli tarayıcı testleri geçti. Bu sonuçlar
gerçek ekran okuyucu ve öğrenci denemesinin sonucu olarak sunulmaz. Pilot
görevleri ve raporlama ölçütleri `docs/erisilebilirlik-tasarim-ve-pilot.md`
dosyasında tanımlandı.

## V3 kalite eğitimi sonucu — 24 Ekim 2026

Private Kaggle notebook `muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-quality-v1`
`COMPLETE` durumunda. İndirilen içeriksiz raporlar, seçilen 1.602 kaydın
11.703,85 saniye (yaklaşık 3 saat 15 dakika) olduğunu, 50 kaydın kalite
filtresinde elendiğini ve bilinen melodili ilk kaydın dışarıda tutulduğunu
gösteriyor. T3 için 600/600 güncelleme yapıldı (AdamW, öğrenme oranı `1e-5`,
batch 1, fp16). Son eğitim kaybı `0,020497`; raporlanan validation kaybı
`0,031672` ve bu ölçüm yalnız 8 doğrulama örneğine dayanıyor. Bu kayıplar
sesin anlaşılabilirliğini veya temel modele göre iyileşmeyi kanıtlamaz.

Kaggle çıktı manifesti `t3_mtl23ls_v3.safetensors` için 2.143.989.752 bayt
ve SHA-256 `90e0a513e4d5f128233a6442f4d3e4c0ac47fefe2ac64eb88c39b28b2aa48060`
bildiriyor. Kullanıcının 24 Ekim talebiyle yerel ağırlık indirmesi durduruldu;
daha sonra yeniden istenince parça parça indirildi. Yerel
`data/private/kaggle-notebook-outputs/muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-quality-v1/20261024T094611Z/verified-artifact/t3_mtl23ls_v3.safetensors`
dosyası tam olarak 2.143.989.752 bayt; bağımsız SHA-256 kontrolü manifestle
eşleşti. Safetensors başlığı 292 adet F32 tensor içeriyor ve veri aralıkları
dosya boyutuyla tutarlı. Bu dosya başarısız adayın geri yüklenebilir arşividir.

### Eş koşullu tarih testi ve eğitim denetimi

24 Ekim'de aynı 14 kapalı tarih metni, aynı referans ses ve sabit rastgele
tohumlarla temel Chatterbox V3 ve T3 fine tune adayı arasında karşılaştırıldı.
Private Kaggle GPU koşusu 28/28 WAV üretti; 28 dosyanın SHA-256 değerleri
yerelde doğrulandı. Temel modelin sesleri 4,40–8,84 saniye sürerken fine tune
adayının 14 sesinin tamamı tam 39,92 saniye sürdü. Ortalama üretim süresi
sırasıyla 6,47 ve 36,17 saniyeydi. Eğitilmiş seslerde 10. saniyeden sonra da
sinyal bulundu; bu uzunluk sessiz dolgu değildir.
Sabitlenmiş [üretim kodu 1.000 yeni token sınırı](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/mtl_tts.py)
koyduğu için 39,92 saniyelik eşit süre, bitiş tokenı gelmeden bu sınıra
ulaşılmasıyla uyumludur.

Whisper large-v3 ön taramasında temel modelin 14/14 sesi çözümlendi; eğitilmiş
adayın 5/14 sesinde transkript boş veya güvenlik sınırını aşacak kadar uzundu.
Başarısız örnekler sıfır doğrulukla sayıldığında ortalama karakter doğruluğu
temel V3 için `0,9373`, eğitilmiş aday için `0,0190` oldu. Kritik terim
kaçırılan örnek sayısı sırasıyla 9/14 ve 14/14. Bu otomatik tarama insan
dinleme puanı değildir; buna rağmen adayın yayına alınmasını engelleyen açık
bir regresyon gösterir. İçeriksiz özet ve örnek bazlı özel puanlar
`data/private/tts_v3_finetune_paired_screen_v1.json` içinde saklanır.

Eğitim kodu yeniden incelendi: `loss_for`, her konuşma tokenının çıktısını
aynı konumdaki tokena karşı puanlıyor. [Sabitlenmiş resmî T3 `forward`
uygulamasında](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/models/t3/t3.py)
o konumun gizli durumu mevcut tokenın gömülmesini zaten görüyor. Bu nedenle
düşük eğitim/validation kaybı, sıradaki konuşma tokenını ve bitiş tokenını
öğrendiğini kanıtlamıyor; aynı konum hedefi olası ana neden. Ayrıca seçilmiş
1.602 kayıt 3 saat 15 dakikalık bir *havuz* oluşturuyor. Sabit bölme 1.492
eğitim ve 110 doğrulama kaydı veriyor. `train_rows[step % len(train_rows)]`
ve 600 adım nedeniyle eğitim kayıtlarının yalnız ilk 600'ü (%40,2) görüldü;
doğrulama kaydı olarak da yalnız ilk 8'i ölçüldü. Önceki bölümdeki 3 saat 15
dakika ifadesi eğitimde tüketilen ses süresi olarak yorumlanmamalı. Yeniden
eğitimden önce kayıp hedefleri bir token
kaydırılmalı, eğitim kapsamı sayılmalı ve kısa smoke koşusunda bitiş davranışı
ölçülmeli. Mevcut model, başarısız denemenin denetlenebilir çıktısı olarak
saklanır; öğrenci uygulamasına bağlanmaz.

### Kör A/B insan dinleme deneyi

`experiments/kaggle/tts_v3_finetune_ab.py`, aynı koşuda üretilen 14 temel ve
14 eğitilmiş sesi dosya özetlerini kontrol ederek yerel, çevrimdışı bir
dinleme sayfasına kopyalar. Her metin için A/B kimliği gizlidir; temel model
7 örnekte A, 7 örnekte B'dir. Kimlik eşlemesi sayfadan ayrı olarak
`data/private/tts_v3_finetune_ab_v1_mapping.json` dosyasında kalır. Dinleyici
doğallık ve metin doğruluğunu ayrı işaretler; form yalnız yerel JSON indirir.
Sayfanın 14 çift, 28 oynatıcı, ilerleme ve JSON indirme akışı yerel Chrome
ile sınandı. İnsan yanıtı henüz alınmadığından A/B tercih sonucu raporlanmaz.

24 Ekim geri bildiriminde dinleyici, eğitilmiş adayın bütün örneklerinin
normalden yaklaşık 5–6 kat uzun olduğunu ve anlaşılır sözcük yerine gürültü
duyduğunu bildirdi. Bu nitel geri bildirim önceki Whisper ve süre bulgusuyla
aynı yöndedir. Kör formun sayısal yanıtı alınmadı; bu gözlem A/B tercih oranı
olarak sunulmaz.

`tts_chatterbox_v3_finetune_runner_v2.py` ile yeni deney ayrıldı. V1 ağırlığı
korundu. V2, T3 konumundaki logiti sıradaki ses ve metin tokenıyla eşleştirir;
bitiş tokenını hedefe dahil eder, temel ağırlığı sabit revizyondan yükler,
eğitim kayıtlarını karıştırır ve kalite koşusunda hepsinin görülmesini şart
koşar. Eğitim sonrası kısa ses üretimi 1–15 saniye aralığından çıkarsa deneme
başarısız sayılır. Önce 8 adımlık private Kaggle smoke koşusu
`eristem-tts-chatterbox-v3-finetune-smoke-v7` başlatıldı. Smoke çıktısı
dinlenip konuşma doğruluğu görülmeden kalite koşusu başlatılmaz.

İlk düzeltilmiş smoke v7 koşusunda 3,76 saniyelik ses üretildi, fakat üretim
çağrısı T3 içine aynı ağırlıkları paylaşan `patched_model` eklediği için
sonraki `safetensors.save_file` kayıt adımı hata verdi. Model ağırlığı artık
üretimden önce kaydediliyor. Ayrıca eğitim referans penceresi resmî V3
üretimindeki 6 saniyeye eşitlendi. Ayrı smoke v8 koşusu 24 Ekim'de tamamlandı:
8 adım, 72 eğitim kaydının 8'i görüldü; 3 ayrı doğrulama kaydı kullanıldı;
ilk/son doğrulama kayıpları `5,540528` ve `5,381458`. Kısa test sesi
3,84 saniye sürdü. Bu süre yalnız bitiş davranışını doğrular; anlaşılabilirlik
için Whisper large-v3 koşusu `eristem-tts-v3-finetune-smoke-asr-v1` başlatıldı.
V8'in model ağırlığı private Kaggle çıktısında `7cb1599e9fffc30df446212740397fabda2385d4f32c4ca1779ae19884003d8f`
SHA-256 ile saklanır; bu sekiz adımlık ağırlık kalite adayı değildir.
Whisper large-v3, V8 sesini beklenen “Bugün tarih dersinde eski uygarlıkları
öğreniyoruz.” cümlesiyle birebir çözdü (`1,0000` karakter doğruluğu).
Proje sahibi örneği dinleyip “anlaşılır ve doğal” olarak değerlendirdi.
Bu, tek cümlelik smoke sonucudur. Tam kalite koşusu
`eristem-tts-chatterbox-v3-finetune-quality-v2` 24 Ekim'de Kaggle sırasına
girdi: 1.500 adım, 250 adımda bir doğrulama kaybı ve en iyi ara ağırlığın
seçilmesi. Kapalı tarih metinlerinde eş koşullu test hâlâ gereklidir.

Kalite V2 koşusu tamamlandı: 1.492 eğitim kaydının her biri en az bir kez
görüldü; held-out doğrulama kaybı `5,770085` değerinden seçilen 1.500. adımda
`4,424032` değerine indi. Ağırlığın SHA-256 değeri
`ec48ce09a53ab90dc44493955b7aaffa3555573da141559c9ccc875235d57a5e`dir.
İnternet kotası nedeniyle 2 GB ağırlık yerelde indirilmedi; private Kaggle
çıktısı yeni eş koşullu testin doğrudan kaynağı olarak bağlandı. Bu test,
`eristem-tts-v3-finetune-eval-v2`, temel V3 ve eğitilmiş V2 için aynı 14
kapalı tarih metnini, aynı referansı ve aynı tohumları üretir.

Eş koşullu V2 değerlendirmesi 28/28 ses üretti. Temel V3 ve V2 adayının
ortalama ses süreleri sırasıyla `6,631` ve `6,306` saniyedir; V1'deki sabit
`39,92` saniye ve gürültü regresyonu V2'de görülmedi. Whisper large-v3, her
iki adayın 14/14 sesini çözdü. Buna karşılık 14 kapalı tarih metninde ortalama
karakter doğruluğu temel V3 için `0,9347`, V2 için `0,9190` oldu (`-0,0157`,
yani `-1,57` yüzde puan). Kritik terim kaçıran örnek sayısı `9/14` ve
`10/14`; kaçırılan terim sayısı `11` ve `12` oldu. Bu sonuç V2'nin ses
üretimini işler duruma getirdiğini, ancak metin doğruluğunda temel modeli
geçtiğini göstermediğini belirtir. Bu yüzden V2 varsayılan öğrenci sesi olarak
seçilmedi. Ancak bu tek ölçüt, ses kimliği veya doğallık yönündeki olası faydayı
ölçmez; V2 kesin olarak reddedilmemiştir. Ayrı referans kaydıyla koşullanan
yeni deney ve kör insan dinlemesi tamamlanmadan kalite iddiası yapılmaz.

### Koşullaması eşlenmiş V3 fine tune tasarımı — 24 Ekim 2026

V2'de hedef cümlenin sesi hem üretilecek konuşma tokenlarını hem de konuşmacı
ve altı saniyelik akustik referansı çıkarıyordu. Gerçek üretimde ise model,
başka bir referans kayıtla yeni bir metin üretir. Bu eğitim-üretim farkını
gidermek için sonraki deneyde her hedef kayıt, aynı izinli konuşmacının fakat
farklı bir kaydından seçilen referansla koşullandırılacaktır. Doğrulama
hedefleri de yalnız eğitim bölümünden seçilmiş referans kullanacaktır. Böylece
hedef sesin kopyalanması yerine metin ile bağımsız ses kimliğinin birleşimi
öğretilir.

Eğitim kapsamında yalnız resmî Chatterbox Multilingual V3'ün T3 bölümü
eğitilebilir kalır; ses kodlayıcı ve S3Gen dalga üreticisi dondurulur. Bu,
modelin ses üretim zincirini gereksizce bozma riskini azaltır. Yeni koşu,
öğrenme oranı ısınması ve azalan zamanlamayla kısa bir 200 adım uyumluluk
deneyi, ardından aynı koşulu kullanan tam eğitim olarak iki aşamada yapılır.
Kısa deneyden ses üretimi, kayıp ve bellek doğrulanmadan tam eğitim başlatılmaz.

Model seçimi tek bir kayıpla yapılmaz. Kapalı tarih kümesinde Whisper karakter
doğruluğu ve kritik terimler anlaşılabilirlik kapısıdır; buna ek olarak aynı
referansla konuşmacı gömme benzerliği, üretim süresi ve körlenmiş insan A/B
dinlemesi raporlanır. Dinleyici her çift için doğallık (1--5), telaffuzun
doğruluğu, hedef sese benzerlik (1--5) ve genel tercih bildirir. A/B kimliği
gizlenir ve her metinde dengeli çevrilir. İlk kullanıcı pilotu sayısal sonuç
yerine kullanılabilirlik geri bildirimi sayılır; rapora genellenebilir bulgu
olarak geçebilmesi için birden çok dinleyici gerekir.

İlk cross-reference pilotu private Kaggle notebook
`eristem-tts-chatterbox-v3-finetune-crossref-v3` üzerinde tamamlandı. Yaklaşık
60 dakika kabul edilmiş konuşmadan 491 kayıt seçildi; 453 eğitim kaydının
200'ü görüldü. Doğrulama kaybı `5,999957` değerinden `5,304672` değerine
indi; kısa üretim denetimi `3,12` saniyelik geçerli ses verdi. Bu pilotun
SHA-256 değeri `c1838de5473a99ed51a811b44c4fd3311dfc0427233a5deb2fcf6e6ecde7b111`.
Pilot yalnız mimariyi ve koşullama değişimini doğrular; kalite iddiası değildir.
Temel V3 ile aynı 14 kapalı tarih metnindeki eş koşullu ses üretimi,
`eristem-tts-v3-finetune-eval-v3pilot` private değerlendirmesinde başlatıldı.
Değerlendirme tamamlandı: temel ve pilot aday için 28/28 ses üretildi, hata
oluşmadı. Temel seslerin süre aralığı `4,40--8,84` saniye, pilotun süre aralığı
`4,16--8,92` saniyedir; önceki V1'deki sabit uzunluk ve gürültü belirtisi
görülmedi. Sonraki bağımsız kapı Whisper large-v3 ile metin doğruluğu, ardından
kör insan dinlemesidir.

Whisper large-v3 ön kapısında temel V3 ortalama karakter doğruluğu `0,9347`,
cross-reference pilot ise `0,9422` elde etti (`+0,0075`, yani `+0,75` yüzde
puan). Kritik terim kaçıran örnek sayısı her iki adayda `9/14`; kaçırılan
toplam terim sayısı temel için `11`, pilot için `10` oldu. Ortalama üretim
süresi `6,53` saniyeden `6,35` saniyeye, ortalama gerçek zaman katsayısı
`0,989` değerinden `0,982` değerine indi. Bu sonuç pilotun otomatik ön kapıyı
geçtiğini gösterir; ses doğallığı ve konuşmacı benzerliği için insan dinlemesi
henüz yapılmamıştır.

Bu sonuçla tam koşu `eristem-tts-chatterbox-v3-finetune-crossref-v4` private
Kaggle notebook'unda başlatıldı. Tam koşu yaklaşık 3 saat 15 dakika kabul
edilmiş konuşma, 1.500 adım, altı saniyeden kısa olmayan referans havuzu,
ısıtma ve cosine öğrenme oranı zamanlamasını kullanır. Ağırlık yalnız Kaggle
çıktısında tutulur; yerel indirme yapılmaz.

V4 tam koşusu tamamlandı. Kaggle raporlarına yalnız bellek üzerinden erişildi:
1.602 kayıt ve 11.703,85 saniye seçildi; 1.492 eğitim kaydının tamamı 1.500
adımda görüldü. 1.010 eğitim kaydı altı saniyelik referans havuzuna girdi.
İlk ve seçilen doğrulama kayıpları `5,974521` ve `5,006765` oldu; son
değerlendirmede 110 held-out kayıt kullanıldı. Kısa sentez denetimi 3,2 saniye
üretti. Modelin bildirilen SHA-256 değeri
`274bfe98e45280aab2687f456bb94a86d0adfa3c220b9f0137a7c32f22648493`.
Bu değer Kaggle raporundan okunmuştur; yerelde dosya hash doğrulaması
yapılmamıştır. `eristem-tts-v3-finetune-eval-v4` private notebook'u ağırlığı
Kaggle çıktısı olarak bağlayarak aynı 14 tarih metninde temel V3 ve V4 seslerini
üretmek üzere başlatıldı. İnsan dinlemesi ve ASR karşılaştırması bekleniyor.

V4 eş koşullu üretim değerlendirmesi tamamlandı: 28/28 ses üretildi. Temel V3
sesleri 4,40--8,84 saniye (ortalama 6,631), V4 sesleri 3,92--8,32 saniye
(ortalama 6,240) sürdü. Süreler eski 39,92 saniyelik bitiş hatasına işaret
etmiyor; tek başına anlaşılabilirliği veya ses doğallığını doğrulamıyor.
Whisper large-v3 taraması `eristem-tts-v3-finetune-asr-v4` üzerinde başlatıldı.
Bu özetler Kaggle raporlarından bellekte okundu; model ve sesler indirilmedi.

Whisper large-v3 28/28 sesi çözdü. Aynı 14 tarih metninde ortalama karakter
doğruluğu temel modelde `0,9347`, V4'te `0,9400` idi (`+0,53` yüzde puan).
ASR çıktısında kritik terim kaçırılan örnek sayısı sırasıyla `9/14` ve `8/14`,
kaçırılan toplam terim sayısı her iki modelde `11` oldu. Ortalama üretim süresi
`6,57` ve `6,13` saniye, gerçek zaman katsayısı `0,995` ve `0,990` ölçüldü.
Bu, 14 metinlik küçük bir otomatik ön taramadır; ASR hataları ve test kümesinin
deneyler boyunca tekrar kullanılması sonuçların genellenmesini sınırlar. V4'ün
doğallığı, konuşmacı benzerliği ve öğrencilerce tercihi kör dinleme olmadan
değerlendirilmiş sayılmaz.

### Pilot ile V4 karşılaştırmasının denetimi ve kör dinleme

Pilot ve V4 otomatik değerlendirmeleri aynı 14 kapalı metin özeti, aynı model
revizyonu, kod revizyonu, referans ses özeti, tohum ve T4 türünü kullanmıştır.
Bununla birlikte bağımsız koşularda temel modele ait 14 WAV dosyasının hash'i
eşleşmedi. Sabit tohum dosya düzeyinde tekrarlanabilirliği garanti etmemiştir;
farkın nedeni henüz ölçülmemiştir. Pilot `0,9422`, V4 `0,9400` karakter
doğruluğu arasındaki 0,22 yüzde puanlık fark, küçük örneklem ve üretim
değişkenliği karşısında modelin kesin kötüleştiğini göstermemektedir. Pilot ve
V4 yalnız adım sayısında değil, referans havuzu ve veri kapsamı bakımından da
farklıdır; nedensel bir eğitim süresi sonucu çıkarılamaz.

Değerlendirme kodunun WAV yazımından önce ölçtüğü genlik tepe değeri 56/56
çıktıda 1'in üzerindeydi. Varsayılan PCM16 kaydı genlik kırpmasına yol açabilir;
kırpılan örnek oranı ve işitsel etkisi bu özetten bilinmemektedir. İnsan A/B
testi için her iki model aynı sabit `0,60` kazançla yeniden sentezlenir,
tepe değer 0,999 altında doğrulanır ve 14 çiftte A/B sırası dengelenir.
Kör Kaggle notebook'u `eristem-tts-blind-pilot-v4` oluşturuldu. Kullanıcı
tercihleri gelene kadar insan değerlendirme sonucu raporlanmaz.

Bu ilk kör test iki eğitilmiş adayı (200 adımlık pilot ve 1.500 adımlık V4)
karşılaştırır; hazır temel modeli içermez. Proje sahibi bunu fark edince ayrı
`eristem-tts-blind-base-v4` notebook'u başlatıldı: aynı izinli referans sesi,
aynı metinleri, aynı sabit kazancı ve dengeli A/B sırasını kullanarak hazır V3
ile V4'ü karşılaştırır. Referans ses her iki modele verildiği için iki sesin
aynı kişiye benzemesi beklenir; ölçülen fark model ağırlıklarının etkisidir.

Bağımsız private Kaggle ağırlık denetimi tamamlandı. Hazır ve V4 dosyalarının
SHA-256 özetleri farklı; kontrol edilen 8 tensörün tamamında sayısal değişim
tespit edildi. Bu bulgu iki ağırlığın farklı olduğunu doğrular, hangi A/B
sesinin daha iyi olduğu hakkında karar vermez. 25 Ekim'de 13 dinleyici tercihi
alındı; test kimliği ve 14. yanıt teyit edilene kadar kör eşleme açılmadı.

Ses--transkript eşleşmesi için `eristem-tts-alignment-audit-pilot` private
Kaggle koşusu başlatıldı. İlk 200 teknik filtreyi geçen kayıtta Whisper
large-v3 ile karakter hata oranı ön taraması yapılır. Ham ses ve transkript
çıktı olarak kaydedilmez; yüksek uyuşmazlık otomatik etiket düzeltmesi veya
kesin ret sebebi sayılmaz, elle inceleme için işaretlenir.

14. dinleyici yanıtı B olarak iletildi. Yanıtlar `eristem-tts-blind-base-v4`
testine aitse özel cevap anahtarına göre V4 7, hazır V3 6 tercih ve 1 eşitlik
vardır. Kullanıcı test adını açıkça doğrulamadığından eşlemenin test kimliği
koşulludur. Kullanıcı daha sonra doğru testin Blind Base V4 olduğunu doğruladı.
Bu tek dinleyici ve 14 çift ile üstünlük veya genelleme iddiası
kurulamaz; örneklerin geliştirmede kullanılmış olması ayrıca sınırlamadır.

Tekrarlanan ses veya normalize metinleri geçişli olarak aynı grupta tutan
deterministik veri bölme ve ayrı eğitim referansı seçme yardımcı kodu hazırlandı;
üç birim testi ve Ruff kontrolü geçti. Henüz eğitim hattına bağlanmadı.

Ses--transkript pilotu tamamlandı: ilk 203 kayıttan müzikli ilk kayıt ve
teknik filtrede reddedilen iki kayıt çıkarıldı; 200 kayıt yazıya döküldü.
Whisper ile normalize edilmiş ortalama karakter hata oranı 0,00114, medyan
0; 200 kaydın tamamı 0,05 veya altında. Bu, ilk 200 kayıttaki otomatik
eşleşme göstergesidir; tüm veri kümesinin kalitesini veya ses doğallığını
kanıtlamaz. ASR hataları ve sıralı örnekleme yanlılığı mümkündür.

Kullanıcı, 14 kör yanıtın Base V4 testine ait olduğunu ayrıca doğruladı.
Yeni V5 eğitim adayı için aynı ses ve normalize metin tekrarlarını geçişli
gruplarla bir arada tutan veri bölmesi ve farklı gruptan eğitim referansı
seçimi V4 eğitim hattına eklendi. `eristem-tts-v5-grouped-smoke` özel Kaggle
koşusu sekiz adımlık teknik doğrulama olarak başlatıldı; bu koşu bir kalite
eğitimi veya kalite kanıtı değildir. Yerel grup ayırma testlerinin üçü geçti.
`eristem-tts-gpu-latency-base-v4` özel Kaggle koşusu model yükleme, ilk
üretim ve sonraki üretim sürelerini CUDA senkronizasyonuyla ölçmek üzere
başlatıldı. Tam üretim süresi gerçek akıştaki ilk ses gecikmesi değildir.

25 Ekim: Her iki özel Kaggle koşusu COMPLETE oldu. V5 kısa denemede 606,73
saniye, 84 kayıt seçildi; 81 eğitim, 3 doğrulama kaydı kullanıldı, 8 adımda
8 eğitim kaydı görüldü ve 4,16 saniyelik teknik konuşma çıktısı üretildi.
İzleme kaybı 5,904598'den 5,767865'e indi; üç doğrulama kaydı ve sekiz adım
kalite artışını kanıtlamaz. Kaydedilen T3 dosyası 2.143.989.752 bayt, SHA-256
`b8d664d63118f476c4696047bc228f02b4e99d69336146e5aad2aea7b8f5e602`;
yalnız teknik test ağırlığıdır.

Tesla T4 hız ölçümünde 14 çift üretildi; ilk örnek hariç 13 örneğin medyan
RTF değeri temel V3 için 0,9923, V4 için 1,0016; medyan üretim süreleri
sırasıyla 6,4885 ve 6,3249 saniyedir. Referans hazırlama üretim süresine
dahildir; oynatma, model yükleme ve gerçek streaming ilk ses gecikmesi dahil
değildir. Model yükleme sırasıyla 16,4297 ve 14,1909 saniye; ilk üretim
10,1611 ve 6,2682 saniyedir. V3 önce, V4 aynı süreçte sonra çalıştığından
bu ilk ölçümler eşit soğuk başlangıç karşılaştırması değildir. Sonuçlar T4
ve bu metinlerle sınırlıdır, genel hız üstünlüğü göstermez.

25 Ekim: `eristem-tts-v5-grouped-quality` özel Kaggle GPU koşusu başlatıldı.
Planlanan kapsam, yaklaşık 11.700 saniye teknik filtrelenmiş konuşma ve 1.500
T3 güncellemesidir; gerçekleşen kapsam ve seçilen checkpoint ancak koşu bitince
rapordan doğrulanabilir. Önceki sekiz adımlık pilot kalite modeli değildir.
Tam koşu başarılı olursa geçici korpus ve ikinci geçici ağırlık kopyası
silinir; ağırlık ve içeriksiz rapor özel notebook çıktısında kalır.
Temel V3 karşılaştırma koşusu `tts_v3_finetune_eval_runner_v5.py` olarak
hazırlandı: kalite koşusunun manifest ve SHA-256 değerini doğrular, iki modele
eşit 0,60 kazanç uygular ve clipping sınırını kontrol eder. Değerlendirme
henüz başlatılmadı. Önceden kullanılan 14 metin geliştirme verisidir, nihai
bağımsız test olarak sunulamaz.

V5 kalite koşusu tamamlandı: 1.602 uygun kayıt, 11.703,85 saniye (yaklaşık
3 saat 15 dakika); 1.478 eğitim kaydının tamamı görüldü, 124 kayıt doğrulamada
kullanıldı. 1.500 güncelleme tamamlandı; 16 kayıttan oluşan izleme kümesinde
başlangıç kaybı 6,027237, seçilen 1.500. adım kaybı 4,929451; 124 kaydın
nihai ortalama kaybı 5,038001. Kaybın düşmesi dinleme kalitesini kanıtlamaz.
3,32 saniyelik teknik üretim yapıldı, dinleme henüz yapılmadı. Özel Kaggle
çıktısında 2.143.989.752 bayt T3 ağırlığı, SHA-256
`8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503`.
`eristem-tts-v5-base-eval` özel karşılaştırma koşusu başlatıldı; veri gelişim
amaçlı önceki 14 tarih örneğidir, henüz ASR veya kör dinleme sonucu değildir.

V3–V5 karşılaştırma sentezi tamamlandı: 28/28 ses üretildi, sıfır üretim
hatası; eşit 0,60 kazanç sonrası tüm tepe değerler sınır altında. Aynı ses
dosyalarından `eristem-tts-blind-base-v5` özel kör dinleme notebook'u 14 çift
olarak hazırlandı; yedi çiftte temel model A, yedisinde B. Hangi çiftin hangi
eşlemeye sahip olduğu dinleyici yanıtları alınana dek gizli kalmalıdır.
`eristem-tts-v5-base-asr` Whisper taraması başlatıldı; sonucu henüz yok.

Kullanıcı 14 kör çift için tercihlerini iletti: 1B, 2A, 3A, 4A, 5 eşit,
6B, 7B, 8A, 9B, 10B, 11B, 12A, 13B, 14A. Özel anahtarla eşlemede V5 10,
hazır V3 3 tercih ve 1 eşitlik çıktı. Bu, bir dinleyicinin daha önce geliştirme
için kullanılan 14 metindeki tercihidir; genel kullanıcı üstünlüğü veya
doğruluk oranı değildir. Whisper 28/28 sesi yazıya döktü; sayısal puanlama
`eristem-tts-v5-base-score` koşusunda başlatıldı.

Whisper puanlaması tamamlandı: ortalama karakter doğruluğu temel V3 %93,47,
V5 %93,98 (fark +0,51 yüzde puan); her ikisinde 14 örneğin 9'unda en az bir
kritik terim kaçırıldı ve toplam 11 kritik terim kaçırıldı. Bunlar Whisper
transkriptine dayalı işaretlerdir, işitsel doğruluk hatası olarak kesinlenmez.
Aynı 14 geliştirme metninde tek tohum ve tek dinleyiciyle bulunan bu sonuçlar
bağımsız genelleme veya büyük doğruluk artışı kanıtı değildir.

Yeni dinleme turu için kitabın PDF 90–91. sayfalarından sekiz kısa parça
seçildi; metinler yerel PDF metin katmanında doğrulandı, önceki 14 test
metniyle tam çakışmadıkları kontrol edildi ve mevcut Türkçe okuma kuralları
uygulandı. Bu, önceki dinleme kümesinden ayrı bir testtir; TTS ses veri
kümesinin tüm metinleriyle çakışmazlığı henüz doğrulanmış değildir. Özel
`eristem-tts-v5-new-history-blind` notebook'unda temel V3 ve V5 aynı sekiz
girdi ve referansla, dengeli kör A/B düzeninde değerlendirilecek. Whisper
tarama koşusu hazırlandı; üretim tamamlanmadan başlatılmayacak.

Yeni tarih testinin özel notebook'u tamamlandı: V3 ve V5 toplam 16/16 ses
üretti, 8 anonim çift ve özel cevap anahtarı oluştu. Metinlerin ekrana
basılan özgün hâli ile mevcut uygulamanın TTS için dönüştürdüğü metin ayrı
saklandı; ikisi de özel Kaggle koşusunda kaldı. Bu yeni örneklerle yapılan
Whisper taraması `eristem-tts-v5-new-history-asr` olarak başlatıldı; henüz
tamamlanmadı. Kullanıcı tercihleri gelmeden kör anahtar açılmamalı.

Kullanıcı yeni testte sayı içeren seslerin çok bozuk olduğunu bildirdi.
Whisper çıktılarında hem hazır V3 hem V5 için 546, 753, 509 ve 27 içeren
örneklerde sayıların tanınmadığı gözlendi. İnceleme, mevcut tarih metin
işlemesinin MÖ ve Roma yüzyıllarını açarken Arap rakamlı MÖ/MS yıllarını
modele rakamla bıraktığını gösterdi. `history_speech.py` içinde açık MÖ/MS
yıl bağlamında 0–9999 arası sayılar ve desteklenen bulunma/ayrılma ekleri
Türkçe sözcüklere çevrildi; belirsiz gösterimler dönüştürülmez. Yedi yerel
tarih-seslendirme testi ve Ruff kontrolü geçti. Ses kalitesi henüz insan
dinlemesiyle doğrulanmadı. Aynı sekiz parça yeni işlemeyle
`eristem-tts-v5-numbers-fixed-blind` özel Kaggle koşusunda yeniden üretiliyor;
eski ve yeni üretim koşuları karşılaştırmalı incelenebilir.

Düzeltilmiş tarih metinleriyle özel Kaggle üretimi tamamlandı: 16/16 ses,
0 üretim hatası, 8 kör çift. Seçilen V5 ağırlığının SHA-256 değeri eğitim
çıktısıyla eşleşti; bu henüz sayı telaffuzunun doğru olduğunu kanıtlamaz.
İnsan dinlemesi ve `eristem-tts-numbers-fixed-asr` Whisper taraması bekleniyor.

Düzeltilmiş testte kullanıcı tercihleri 1B, 2B, 3A, 4A, 5A, 6B, 7B,
8B; kör eşlemeye göre hazır V3 5, V5 3 tercih aldı. Bu sekiz çiftlik tek
dinleyici sonucu genel üstünlük kanıtlamaz; metin ön işlemesi değiştiği için
önceki testle doğrudan tek değişkenli model karşılaştırması değildir. Whisper
16/16 sesi yazıya döktü ve sayı içeren 3, 4, 5. örneklerde her iki model için
546, 753, 509 ve 27 sayılarını doğru tanıdı. Önceki üretimlerde bunları
tanımamıştı. ASR okumanın doğru olduğunu kesin kanıtlamaz; kullanıcıdan
sayılara ilişkin doğrudan dinleme teyidi bekleniyor.

Kullanıcı düzeltilmiş sayıların okunuşunun anlaşılır olduğunu doğruladı.
Ardından açık yıl bağlamını kapsamak için dört basamaklı, bulunma veya ayrılma
eki almış yıllar ve `yılında` gibi yıl birimiyle verilen sayılar da yazıya
çevrildi. Tarih, kaynak ve soru yapısı testlerinde 15 test geçti. Yeni
genişletilmiş kurallar için henüz ayrı sesli dinleme yapılmadı.

Kullanıcının V5 adayıyla devam etme kararına uygun yerel WAV servis taslağı
eklendi. V5 T3 özeti doğrulanır, referans ve model yerel dosyalardan okunur,
API önbelleği ses sürümüne göre ayrılabilir. Model, referans ve bağımlılıklar
yerelde kurulmadığından gerçek V5 üretimi ve uçtan uca çalışma denenmedi.
Servis yardımcıları, API önbelleği ve tarih metni testlerinde 19 test geçti;
kurulum ve sınırlar `docs/v5-yerel-ses-kurulumu.md` içindedir.

Model indirilmeden ses ve erişilebilirlik geliştirmeleri: aynı API sürecindeki
eşzamanlı aynı ses istekleri önbellek anahtarına göre birleştirilir; ilk istek
başarılıysa diğerleri kaydedilen WAV'ı kullanır. Bu, süreçler arası kilit
değildir. Tarih okuyucusunda sayfa veya bölüm değişince önceki ses ve URL'si
temizlenir; durdurma düğmesi ve ses komutu aynı oynatıcıyı durdurur. İlgili
20 API testi, 15 web testi, web derleme ve lint kontrolleri geçti. Tarayıcı ve
gerçek ekran okuyucu ile kullanım ayrıca doğrulanmalıdır.

V5 önceden üretilmiş sunum sesleri için kitap PDF 40–49. sayfalarındaki 191
okuma bölgesi ve öğrenciye sunulabilir 9 onaylı sorunun 174 okuma birimi
kaynak ve metin özetiyle özel manifestte hazırlandı. Bir başka onaylı soru
düzen karışıklığı denetiminden geçmedi. 365 birimin 78'inde rakam bulunduğu
için bunlar sayı okunuşu inceleninceye kadar üretimden ayrıldı. Manifest
özel Kaggle veri kümesine yüklendi; dört benzersiz metinlik
`eristem-tts-v5-demo-smoke` denemesi çalışıyor. Tam üretim paketi hazır,
deneme başarıyla tamamlanana kadar başlatılmadı. Yerel demo ses eşleştirmesi
kaynak PDF, metin, bölüm kimliği, V5 ağırlık ve WAV özetini doğrular; dosya
henüz indirilmedi ve bu altyapı otomatik olarak etkinleştirilmedi. Altı ilgili
test ve Ruff geçti. Teknik kontrol telaffuz veya insan dinlemesi yerine geçmez.

İlk dört metinlik deneme üretimden sonra geçici kontrol noktası dizinindeki
`.locks` klasörünü dosya gibi silmeye çalıştığı için hata verdi. Geçici model
bağlantıları ve ses referansı Kaggle çıktı alanı dışına taşındı; düzeltmeyle
deneme ikinci sürüm olarak yeniden başlatıldı. Tam üretim yine deneme sonucu
doğrulanmadan başlatılmadı. Rakam içeren 78 birimde soru numaraları, yıllar,
aralıklar ve kaynak sayfaları gibi farklı bağlamlar var; otomatik olarak tek
bir okuma kuralı uygulanmadı. Rakam içermeyen 255 benzersiz metin üretime aday.

İkinci kısa deneme tamamlandı: dört kaydın tamamı teknik kontrollerden geçti,
girdi ve model özetleri beklenen değerlerle eşleşti. Bu sonuç dinleme ve
telaffuz doğrulaması değildir. Ardından `eristem-tts-v5-demo-full` özel Kaggle
çalışması 255 rakamsız benzersiz metin için başlatıldı; sonuçlar henüz yerel
olarak indirilmedi veya uygulamaya yüklenmedi.

Toplu üretim tamamlandı; 255 WAV'ın tümü üretildi ve yaklaşık 83,6 MB ses
dosyası yerel olarak indirildi. Girdi, V5 model ve her WAV'ın SHA-256 özeti
doğrulandı; 287 kaynak birimi bu dosyalara bağlandı. API'de bir kitap bölgesi
ve bir onaylı soru ses isteği sınandı; ikisi de 200 döndürdü ve cevapların
özetleri kurulu V5 dosyalarıyla eşleşti. Sayısal metin içeren 78 birim
üretilmedi, mevcut TTS'e geri döner. İnsan dinlemesi ve telaffuz kontrolü
bu üretim için henüz yapılmadı; sonuçlar sunum için ön değerlendirme niteliğinde.

İkinci V5 önceden üretim paketi, ana giriş ve öğrenci menüsündeki sabit sesli
yönlendirmeleri ve kitap PDF'sinin 50–59. sayfalarındaki rakamsız bölgeleri
içerir. 165 özgün WAV (yaklaşık 46,8 MB) teknik olarak doğrulandı ve 179
kaynak birimine bağlandı. API'nin başlangıç yönlendirmesi ile 50. sayfadaki
bir kaynak bölümü canlı isteklerle sınandı; her iki dönen WAV da kurulu V5
dosyasının özetiyle eşleşti. Dinamik veya önceden bilinmeyen arayüz metinleri
ve sayısal bölümler bu pakette değildir; bunlar için insan dinlemesi ve ayrı
okunuş kuralları gerekir.
| 2026-10 | Kanıt demeti motoru | Sabit soru başına üç kesit varsayımı kaldırıldı; öğretmen/agent taslağındaki zorunlu kanıt iddialarını ayrı arayan, sayfa çeşitliliği koruyan private demet motoru eklendi | Anahtar kelime benzerliği, temel olgu ve kişi–olay/tarih–olay ilişkisini aynı anda kanıtlamaz; eksik zorunlu iddiada sistem çekimser kalmalı | Uygulandı; 14 birim testi geçti, agent taslak planı ve PDF kırpım incelemesi bekliyor |
| 2026-10 | AYT kanıt planı false-negative denetimi | Tarih agentı 9 soruluk private planın kısmi adaylarını cevap anahtarı olmadan sınıflandırdı; doğrulanabilir plan yamaları uygulandı ve aynı checksum sürümünde karşılaştırıldı | İlk plan 23/23 zorunlu iddiayı eksik bırakıyordu; yama sonrası eksik sayı 17/22 ve yalnız 1 sıkı inceleme adayı oluştu. Bu adayın semantik denetimi PDF kırpımı olmadan onay vermedi | Uygulandı; kaynak onayı 0, öğrenci RAG/QLoRA kapısı kapalı |
| 2026-10 | Kaynak içi ilişki çıkarma pilotu | Dört seçilmiş MEB kesitinden atomik ilişki önerileri çıkarıldı; uçlar, kaynak fiili ve alıntı yerelde denetlendi | Sabit ilişki türünün eğitim veya destek ilişkilerini yanlış yer/tarih ilişkisine zorlamaması için kaynak fiili ayrıca tutuldu | 2 öneri, 6 yerel ret; 3 PDF kesitiyle insan incelemesi bekliyor |
| 2026-10 | Kaynak içi ilişki kontrollü genişletme | İlk beş farklı kaynak kesiti, cümle-düğüm, pasif fiil, ilişki yönü ve olay biçimi kapılarıyla tekrar işlendi | İlk genişletmede görülen ters yön ve fiilli düğüm hataları kalıcı ön filtreye dönüştürüldü | 10 adayın 8’i yerelde elendi; kalan 2 ilişki private PDF kesiti incelemesine alındı |
| 2026-10 | AYT kaynak ilişki kuyruğu | Dokuz öncelikli AYT sorusunun 60 farklı kaynak kesiti checksum bağlı küçük partilerde işlendi ve tek private yapıt olarak birleştirildi | Ara kesinti veya yeniden çalışma tek partiyi bozmasın diye parti kimliği ve benzersiz kaynak denetimi kullanıldı | 112 ham adaydan 70’i yerelde elendi; 42 ilişki içeren 32 PDF kesiti insan inceleme kuyruğunda, kaynak onayı 0 |
| 2026-10 | İkinci kaynak okuması ve QLoRA hazırlık kapısı | 42 yerel kapıdan geçmiş ilişki, soru ve cevap anahtarı olmadan aynı kaynak kesitine bağlı ikinci denetimden geçirildi; yalnız doğrudan görünenler PDF kesiti paketine alındı. QLoRA dışa aktarımına altı durum, 120 grup ve 84/18/18 bölme denetimi eklendi | İkinci denetim insan onayı değildir; sadece inceleme yükünü azaltır. Eğitim, onaylı kaynak ve tam grup olmadan başlamamalı | 41 ilişki / 31 PDF kesiti özel insan inceleme kuyruğunda; 1 ilişki bağlam yetersizliğiyle çıkarıldı. Gerçek QLoRA hazırlık raporu 0/120 tam grup nedeniyle `blocked`; Kaggle eğitimi başlatılmadı |
| 2026-10 | Soru yapısı ve konu dengesi kuyruğu | Lisanslı 9. sınıf soru bankası, soru metni ve cevap anahtarı dışa aktarılmadan yapısal risklere göre tarandı; konu başlıkları Unicode apostrof farklarından arındırıldı ve test adı konu kabul edilmedi | Farklı yazılmış aynı başlıkları ayrı konu saymak veya “Ünite Tarama Testi”ni ders konusu saymak dengeyi yapay olarak yükseltiyordu | 306 adayın 223’ü yapısal olarak uygun, bunların 120’si yedi başlığa dengeli dağıtıldı. Bu havuz 9. sınıf olduğundan AYT odaklı QLoRA’ya otomatik girmez; ayrıca kanıt ve öğretmen onayı bekler |
| 2026-11 | Atom ve bağlam çıkarma denetimi | AYT konu özeti ile 10., 11. ve 12. sınıf MEB kaynakları için fiziksel kitap yapısı, kısa bilgi atomu, uzun bağlam ve görsel/yapısal inceleme rotası ayrıldı | Albert Malche maddesi, 105 karakter alt sınırı ve baştaki madde imi yüzünden indeks dışında kalmıştı. İçindekilerde `20. Yüzyıl` ile başlayan düz başlık da yanlışlıkla hiyerarşik başlık sayılıp atılıyordu | İki hata regresyon testine alındı. Konu özeti 73 bölüm olarak yeniden işlendi; kısa atomlar ve bağlamlar ayrı tutuldu. Tablo, şema ve görsel taşıyan sayfalar otomatik kanıt yerine görsel PDF inceleme rotasına bırakıldı |
| 2026-11 | Yeniden üretilebilir AYT retrieval denetimi | Önceki atom denetiminin eski corpus sürümüne bağlı olduğu saptanınca aynı 23 önceki hata + 20 karşılaştırma sorusu, cevap anahtarından yalıtılmış transkripsiyon ve düzeltilmiş corpusla tekrar hazırlandı | Eski sonuç yeni kaynak çıkarıcısının başarısını veya hatasını ölçemezdi. Tekrarlanan sayfa etiketi de atom adayı olarak kalıyordu | 2.951 aday belgeyle (2.664 atom, 287 bağlam) private Kaggle koşusu başlatıldı. Albert atomunun varlığı ve tekrar eden sayfa etiketinin yokluğu yerelde doğrulandı; sonuçlar PDF-kırpım incelemesi gelmeden runtime/QLoRA kararına dönüşmeyecek |
| 2026-11 | Atom/bağlam hibrit retrieval denetimi | 43 sabit AYT sorusunda 516 kaynak kartı cevap anahtarına erişmeyen üç bağımsız tarih agentı tarafından PDF kırpımı üzerinden kör incelendi | Atom ranking kimliği `kaynak:atom:parça`, kırpım inceleme kimliği `kaynak:parça` biçimindeydi; ölçüm ilk çalışmada bu eşdeğer kimlikleri eşleştiremedi. Normalizasyon regresyon testi eklendi | 9 soru doğrudan veya en çok üç atomla desteklenebilir bulundu. RRF, BM25’e göre Recall@3 `+0,111`, MRR@3 `+0,037` sağladı ve yanlış kanıt oranını `0,630`dan `0,593`e indirdi. Uçtan uca ölçülen BM25+dense p95 toplamı yaklaşık `163 ms`; teknik kabul eşiğini geçti. İnsan kaynak onayı olmadığı için runtime ve QLoRA hâlâ kapalı |
| 2026-11 | AYT hedef kapsamını sabitleme | 2022–2026 bağımsız incelenmiş AYT EA/SÖZ metadata’sı sınıf seçimi için, OGM AYT EA 2018–2026 konu dağılım tablosu ise altı ince bölümün sıralanması için checksum bağlı private manifestte birleştirildi | 2022–2026 etiket örneği 12. sınıfı açıkça seçse de yalnız beş geniş ünite bırakıyordu; veriyi altı ünite varmış gibi göstermemek için ince bölüm sırası resmî dağılım tablosunun fiziksel 87–88. sayfalarına bağlandı | İlk kapsam: Millî Mücadele’ye hazırlık (9), Batı Cephesi (7), I. Dünya Savaşı süreci (5), siyasi gelişmeler (3), Doğu/Güney Cepheleri (2), Atatürk ilkeleri (2). Her bölümde MEB corpus adayları bulundu; manifest yalnız private keşif allowlist’i, runtime ve QLoRA kapıları kapalı |
| 2026-11 | QLoRA soru havuzu kalite denetimi | Tarih öğretmeni rolündeki bağımsız inceleme, mevcut 120 soruluk private OCR havuzunu yeni altı bölüm kapsamına göre sayısal ve içerik yalıtımlı değerlendirdi | Geniş “Millî Mücadele” ve “Atatürkçülük” başlıkları altı bölümü ayırt etmiyor; doğrudan 120’ye bölmek, kapsam dışı veriyi eğitime sokar | 43 soru koşullu kanıt-keşif adayı, 77 soru kapsam dışı; alt bölüm düzeyinde onaylı soru sayısı 0. Önce 43 aday alt bölüm ve kanıt demeti incelemesinden geçecek, ardından eksik alanlara hedefli soru eklenmeden eğitim başlatılmayacak |
| 2026-11 | AYT hedef soru kapasitesi ve ilk kalibrasyon | OGM konu pekiştirme, OGM AYT tarama ve MEB 12. sınıf ünite sonu soru sayfaları, cevap/çözüm sayfaları okunmadan ayrı private aday havuzlarında işlendi; üç tarih öğretmeni incelemesi bölüm uyumunu ve yapısal riskleri değerlendirdi | İlk 43 adayın yalnız 13’ü güçlü kaynak inceleme önceliği aldı; I. Dünya Savaşı ve siyasi gelişmeler eksikti. Tarama kaynağı 8 yönlendirilebilir adayla bu boşlukların bir kısmını kapatıyor. MEB ünite sonu OCR’sinde 17 adayın kökü veya seçenekleri kesik çıktı | İnceleme öncesi ham kapasite 86, 120 grup hedefi için en az 34 ek ham aday gerekiyor; ret ve yeniden çıkarımlar nedeniyle bu alt sınırdır. Şimdi güçlü adaylar PDF kesiti/kanıt demeti incelemesine, bozuk MEB adayları ise yeniden çıkarıma gider. Hiçbiri runtime veya QLoRA’ya açılmadı |
| 2026-11 | 12. sınıf PDF sürüm bütünlüğü | Önceki corpusun 12. sınıf kaynak checksum’ına karşılık gelen PDF’nin yerelde bulunmadığı; eldeki MEB ders kitabının farklı sürüm olduğu saptandı | Kaynak metni ile PDF kesitini aynı dosyadan doğrulayamayan retrieval/inceleme sonucu kanıt onayı sayılamaz | Yerelde mevcut MEB kitabı ve AYT konu özetiyle 32 bölümlü, 771 bağlam ve 872 atomlu yeni private corpus kuruldu. Eski 12. sınıf kaynak adayları geçersizleştirildi; 43 soruluk kalibrasyon yeni corpus checksum’ıyla yeniden başlatıldı |
| 2026-11 | Yerel 12. sınıf atom–bağlam keşif kuyruğu | Yerelde doğrulanabilir **T.C. İnkılap Tarihi ve Atatürkçülük** PDF’sinin altı AYT hedef bölümünde kısa bilgi atomları ve açıklayıcı bağlamlar ayrı BM25 indekslerine alındı; top-20 adaylar RRF ile birleştirildi ve aynı sayfa türündeki tekrarlar azaltıldı | `manual_review` durumu kaynak parçasının onaysız olduğunu gösterir; bunu aramadan tümüyle dışlamak 195 kısa atom ile 186 temiz bağlamın çoğunu görünmez yapıyordu. Bu durum onay anlamına gelmez | 43 cevap-anahtarsız aday sorunun tümü için PDF kırpım incelemesi gerektiren aday seti üretildi; p50 `1,664 ms`, p95 `2,088 ms` yerel BM25 aşaması ölçüldü. Öğrenci RAG’ı ve QLoRA kapıları kapalı; tarih öğretmeni rolündeki kör kaynak denetimi bekliyor |
| 2026-11 | Yerel 12. sınıf dense retrieval geliştirme koşusu | Yeni atom–bağlam öğretmen denetimindeki 13 `direct`/`bounded_inference` soru ve 17 koordinatlı destek kesitiyle Qwen3-Embedding-4B için private Kaggle geliştirme kümesi hazırlandı; BM25, instruction-aware dense ve top-20 RRF aynı etiketlerde ölçülecek | 43 adayın tamamını gold kabul etmek yanlış kanıtı ölçüme doğru cevap gibi sokardı. Yalnız PDF-kırpım denetiminde desteklenen kayıtlar değerlendirme etiketi oldu; bunlar cevap anahtarı değildir | Private veri kümesi ve GPU koşusu başlatıldı. Girdi 381 hedef-bölüm atom/bağlam adayını, cevap anahtarsız ihtiyaç metnini ve evaluation-only kesit kimliklerini içerir; ham PDF, cevap, çözümlü açıklama ve öğrenci verisi içermez. Sonuç gelmeden runtime/QLoRA kararı yok |
| 2026-11 | Qwen3-Embedding-4B yerel 12. sınıf AYT geliştirme deneyi | Private Kaggle T4 koşusunda, 381 hedef-bölüm atom/bağlam adayı üzerinde 13 PDF-kırpım etiketli, cevap-anahtarsız geliştirme ihtiyacı için BM25, Türkçe instruction-aware Qwen dense ve RRF karşılaştırıldı | Dense yol, BM25’e göre Recall@3 `0,5385 → 0,7692` (`+0,2307`), MRR@3 `0,2564 → 0,3846` (`+0,1282`) ve nDCG@3 `0,2921 → 0,4311` (`+0,1390`) sağladı. RRF aynı Recall@3’e ulaştı ancak MRR@3 `0,3333` ile dense’in gerisinde kaldı | Qwen dense geliştirme adayı olarak kabul edildi; RRF varsayılan yapılmadı. Sorgu dense p95 `136,710 ms` ve BM25 p95 `5,538 ms`; bu teknik retrieval eşiğinin altında. Küme küçük ve geliştirme amaçlı olduğundan kapalı test, yanlış kanıt incelemesi ve insan kaynak onayı tamamlanmadan runtime/QLoRA kapıları kapalı |
| 2026-11 | Resmî AYT soru havuzu genişletme | 2022–2026 EA Tarih-1 ve SÖZ Tarih-2 private aday dosyalarından, tam kök ve A–E seçenek düzeni doğrulanmış sorular cevap/çözüm sayfalarına erişmeden ortak şemaya aktarıldı | Eksik OCR kökü veya eksik seçenek, kaynak getirme ya da koçluk örneği için güvenli değildir; bu kayıtlar zorla tamamlanmadı | 40 aday (`20` Tarih-1, `20` Tarih-2) tarih öğretmeni incelemesine verildi. İnceleme yalnız hedef altı bölüme kesin atama, erişilebilirlik ve kanıt ihtiyacı belirleyecek; kaynak/runtme/QLoRA onayı üretmeyecek |
| 2026-11 | Ajan öğretmen onay politikası ve resmî AYT kaynak kuyruğu | Proje onay politikası mimari manifestte `history_teacher_agent_v1` PDF-kesit incelemesi olarak açıklandı; resmî AYT geniş havuzundan hedef altı bölüme atanmış 10 soru, checksum bağlı atom–bağlam kaynak kuyruğuna aktarıldı | Ajan incelemesi insan öğretmen onayı diye raporlanmayacak. Buna rağmen her karar kaynak checksum’ı, koordinat, gerekçe ve `is_human_teacher_approval=false` provenance’ı taşımadan kabul edilmeyecek | Resmî AYT soruları için kaynak-kesit denetimi başlatıldı; öğrenci RAG’ı ve QLoRA onayı hâlâ kapalı |
| 2026-11 | Resmî AYT sorularında dense yeniden getirme | Resmî AYT hedef denetiminde 10 sorudan yalnız birinin BM25 atom–bağlam demeti doğrudan destek verdi; dokuz `retrieval_miss` için Qwen3-Embedding-4B ile cevap anahtarsız dense aday yeniden sıralaması başlatıldı | İlk BM25 kuyruğundaki düşük kanıt oranı “kitapta bilgi yok” olarak yorumlanmadı. Yeni dense sıralama yalnız PDF kesiti denetimi için aday üretir ve hiçbir onay/koçluk kaydı oluşturmaz | Private Kaggle veri kümesi ve GPU koşusu başlatıldı; 381 hedef bölüm kesiti, 10 resmî soru ihtiyacı ve ham PDF/cevap/çözüm içermeyen girdi kullanılıyor |
| 2026-11 | Resmî AYT dense yeniden getirme denetimi | Qwen3-Embedding-4B'nin resmî 10 AYT sorusundaki dense top-3 sonuçları PDF kesiti üzerinden önceki atom–bağlam BM25/RRF denetimiyle karşılaştırıldı | Doğrudan destek `1 → 2` arttı; yanlış aday sayısı `3 → 2` düştü. Ancak bir `indirect → wrong` ve bir `indirect → insufficient` geçişi oluştu; yalnız toplam metrikle model yolunu runtime varsayılanı saymak doğru olmaz | Dense yol daha ileri ilişki/demet geliştirme için aday kaldı; runtime ve QLoRA kabul edilmedi. Geçiş tablosu, destek artışı ile kalite gerilemelerini birlikte kaydeder |
| 2026-11 | Şık hipotezleriyle çoklu-sorgu retrieval ablation’ı | Resmî AYT sorusunda kök ve her şık, doğru cevap etiketi kullanılmadan ayrı retrieval ihtiyacı olarak üretildi; Qwen dense sıralamaları RRF ile birleşecek | Tek büyük sorgu, birbirinden farklı şıkların terimlerini birbirine karıştırarak kişi–olay ve kronoloji ayrımını zayıflatabiliyor. Şıklar ancak `contrast` kanıtı adayını genişletir; doğru şık göstergesi değildir | Private Kaggle koşusu başlatıldı. Sonuç, aynı PDF-kesit rubriğinde tek-sorgu dense yolundan daha çok doğrudan destek üretmez veya yeni kalite kaybı getirirse reddedilecek |
| 2026-11 | Şık hipotezleriyle çoklu-sorgu retrieval sonucu | Aynı 10 resmî AYT sorusunda Qwen dense kök+şık RRF adayları PDF kesitiyle denetlendi; tek-sorgu dense denetimiyle eş soru bazında karşılaştırıldı | Çoklu sorgu iki doğrudan kanıtı korudu ancak `wrong` sonuç sayısını `2 → 4` yükseltti; şık terimleri bazı sorularda doğru tarihsel ilişki yerine konusal gürültüyü öne çıkardı | Reddedildi: runtime, öğrenci RAG’ı ve QLoRA için kullanılmayacak. Gecikme p95 yaklaşık `688,656 ms` olsa da kalite gerilemesi kabul edilemez |
| 2026-11 | İlişki-demeti kaynak denetimi hazırlığı | Tek-sorgu dense’in top-3 sınırında kalan resmî AYT soruları için dense ve BM25 top-20 adayları birleştirildi; yalnız birebir aynı PDF kesitleri birleştirildi, önce sayfa çeşitliliği korunarak her soru için 10 kaynak kartı hazırlandı | Kişi–olay, tarih–olay ve neden–sonuç sorularında ilk üç benzer paragrafın eksik olması, kaynakta bilgi olmadığı anlamına gelmez. Daha geniş aday küme bir ilişki iddiasını otomatik doğrulamaz; her kenar yine PDF kesitinde açıkça görülmelidir | 10 soru ve 100 kaynak kartı tarih öğretmeni ajanı PDF-kesit incelemesine girdi. Kuyruk yalnız keşif içindir; kaynak grafiği, öğrenci RAG’ı ve QLoRA kapıları kapalıdır |
| 2026-11 | İlişki-demeti PDF denetimi | Dense+BM25 top-20 birleşiminden seçilen 100 kaynak kartı, aynı 10 resmî AYT sorusu için PDF sayfa ve koordinat kesitleriyle incelendi; kaynak anahtarı, kayıt kimliği, birebir alıntı ve provenance programatik olarak doğrulandı | Destekleyici sonucu yalnız kaynak kesitindeki açık bilgi veya en fazla üç atomla kurulan sınırlandırılmış ilişki saydık. Normalize edilmiş ya da üç noktayla kısaltılmış alıntılar doğrulamada reddedildi ve OCR boşlukları korunarak birebir kaynak alıntısına düzeltildi | `direct/bounded_inference` sayısı `2 → 3` oldu: iki doğrudan kanıt korundu, Ali Rıza Paşa–Amasya zinciri sınırlandırılmış çıkarım olarak eklendi. Bir `indirect → wrong` geçişi olduğundan bu yol runtime varsayılanı değildir; QLoRA ve öğrenci RAG kapıları kapalıdır |
| 2026-11 | Şıksız kök-sorgu dense ablation’ı | Aynı 10 resmî AYT sorusu ve 381 kaynak adayında Qwen3-Embedding-4B yalnız soru kökü ile ihtiyaç planını gömdü; şık metinleri sorgudan çıkarıldı ve ilk üç sonuç PDF kesitlerinde denetlendi | Şıklar doğru cevap etiketi taşımasa da tek sorguda birleşince ilişkisiz kişi, tarih ve yer terimlerini öne çıkarabiliyor. Bu nedenle gecikme ve kanıt kalitesi aynı anda ölçüldü | T4 p95 `114,744 ms` oldu; ancak doğrudan kanıt `2 → 2` sabit kaldı ve iki kalite gerilemesi görüldü (`indirect → wrong`, `insufficient → wrong`). Reddedildi: runtime, öğrenci RAG’ı ve QLoRA için kullanılmayacak |
| 2026-11 | Çok kaynaklı 11+12. sınıf dense denetimi hazırlığı | Yerelde checksum’ı doğrulanmış 11. sınıf tarih kitabı ile 12. sınıf İnkılap Tarihi kitabı, hedef 12. sınıf bölümleri ve temiz 11. sınıf adayları üzerinden ayrı bir private keşif kümesine alındı | Bazı resmî AYT sorularındaki kişi veya olay bilgisi yalnız 11. sınıf kitabında yer alıyor. Bunu 12. sınıf corpusunun retrieval hatası gibi göstermek yerine, kaynak sürümünü ve her kesitin geldiği PDF’yi açıkça taşımak gerekir | Qwen3-Embedding-4B koşusu yalnız aday getirme için çalışıyor. Sonuç hazır olduğunda 11 ve 12. sınıf kartları checksum, sayfa, koordinat ve birebir alıntıyla ayrı PDF kesitlerinde incelenecek; cevap anahtarı, öğrenci RAG’ı ve QLoRA’ya erişim yok |
| 2026-11 | Çok kaynaklı PDF-kesiti inceleme sözleşmesi | Retrieval tamamlanmadan önce, iki kitaptan gelen adayları bir araya getiren private inceleme kuyruğu ve provenance doğrulayıcısı eklendi | Bir araya gelen sonuçlarda 11. sınıf kesitinin 12. sınıf kaynağı sanılması ya da sıralama sonucunun kanıt gibi kullanılması kabul edilemez | Her kart kaynak checksum’ı, kitap adı, sayfa, koordinat ve birebir kesit metnini taşır. Denetim; tüm kartların gerçekten incelendiğini, ilişki alıntısının ilgili kesitte geçtiğini, kaynak bağlarının eşleştiğini ve cevap/çözüm erişiminin olmadığını doğrular. Bu mekanizma öğrenci RAG’ı veya QLoRA onayı değildir |
| 2026-11 | 11+12. sınıf çok kaynaklı dense keşif koşusu | Qwen3-Embedding-4B, checksum bağlı 11. ve 12. sınıf MEB kaynaklarından oluşan 2.178 atom/bağlam adayını 10 resmî AYT sorusunun cevap-anahtarsız ihtiyaç planıyla T4 üzerinde sıraladı | Girdi ve çıktı şemaları, corpus checksum’ı, iki kaynak bağı, aday kimlikleri ve cevap/çözüm/runtime/QLoRA kapıları indirilen çıktıda programatik olarak doğrulandı | Sorgu aşaması p50 `168,918 ms`, p95 `173,613 ms` oldu. Top-20 dense, BM25 ve RRF adayından sayfa çeşitliliğiyle seçilmiş 100 kartın 29’u 11. sınıf, 71’i 12. sınıf PDF’sine ait. Teknik çıktı kanıt değildir; PDF-kesiti tarih öğretmeni ajan denetimi sürüyor |
| 2026-11 | Çok kaynaklı dense ön PDF denetimi | Ajan kotası nedeniyle bağımsız ikinci denetim tamamlanamadı. Yerel incelemede 100 kartın kaynak PDF’si, checksum’ı, sayfası ve koordinatı kontrol edildi; destek iddiası yalnız açık metin ve görsel kesit ilişkisinin görüldüğü kartlarda verildi | Bu kayıt tarih öğretmeni ajanının bağımsız onayı değildir. Bir adayda OCR metin sırası ile kesit sırası farklı olsa da görsel kesitte başlık ve açıklama birlikte görüldü; bu nedenle layout-normalizasyonu ayrı tutuldu | Ön ölçümde 6 doğrudan, 1 dolaylı, 2 yetersiz ve 1 yanlış aday görüldü; önceki 12. sınıf dense tabanına göre destek `2 → 6` oldu. Bir `indirect → wrong` geçişi bulunduğu için yalnız ölçüm sonucu olarak saklandı; runtime, bilgi grafiği ve QLoRA kapıları kapalı |
| 2026-11 | PDF kesiti metin-kapsam regresyon kapısı | Çok kaynaklı inceleme paketine PDF koordinatındaki metnin alıntı tokenlarını layout farklarına toleranslı biçimde kapsayıp kapsamadığı kontrolü eklendi; soft hyphen, satır bölünmesi ve başlık-paragraf sırası normalize edildi | Yalnız OCR string eşitliği, doğru görsel kesiti yanlışlıkla reddedebiliyor. Sadece token kapsamı da kaynak onayı değildir; checksum, koordinat ve görsel inceleme ile birlikte kullanılır | 100 kartın tümü yeniden üretimde geçti. Alakasız alıntı, eksik kaynak eşlemesi ve yanlış checksum testleri de geçiyor; paket hâlâ private ve onaysız |
| 2026-11 | Tam MEB kaynak coverage girdisi | 10. ve 11. sınıf kitapları, 12. sınıf İnkılap kitabı ve AYT konu özeti tek bir öğrenci-dışı keşif girdisinde checksum bağları korunarak birleştirildi | Konu özeti retrieval’a hiç girmeden “kaynakta yok” kararı vermek sistemik coverage hatasıdır. Dört kaynak aynı indeks gibi kabul edilmiyor; her kart kendi kitap, sınıf, checksum ve PDF kesitiyle denetlenmeli | 7.502 atom/bağlam adayı ve aynı 10 cevap-anahtarsız ihtiyaç planı hazırlandı. Bu girdi henüz Kaggle dense koşusuna veya runtime’a açılmadı; sonraki deney, mevcut 11+12 sonucuyla karşılaştırmalı coverage denetimi olacak |
| 2026-11 | Tam MEB coverage Kaggle koşusu | Dört kaynaklı 7.502 aday girdisi private Kaggle veri kümesine yüklendi ve Qwen3-Embedding-4B T4 runner’ı başlatıldı | Bu koşu yalnız kaynak kapsamını sınar. Sonuç kartları PDF checksum ve görsel kesit incelemesinden geçmeden öğrenci RAG’ına veya QLoRA’ya giremez | Veri kümesi `eristem-ayt-full-multisource-local10-12-summary-v1`, notebook `eristem-ayt-full-ms-v1`; durum kontrolü belirlenen aralık sonunda yapılacak |
| 2026-11 | Tam corpus inceleme şeması | PDF inceleme kuyruğu, paket üreticisi ve provenance doğrulayıcısı hem önceki 11+12 corpusunu hem de 10+11+12+AYT özetli tam corpus şemalarını kabul edecek şekilde genişletildi | Tam corpus sonucu geldiğinde dört kaynağın kartları aynı kaynak sanılmadan checksum, sayfa ve koordinatla incelenebilir; eski kuyruğun davranışı geriye dönük test edildi | `90bfa71` kaydı; 7 yerel test geçti. Bu yalnız inceleme altyapısıdır, insan onayı veya runtime/QLoRA etkinleştirmez |
| 2026-11 | Retrieval çıktı doğrulama kapısı | Tam corpus Kaggle çıktısının şema, corpus checksum’ı, kaynak bağları, sorgu-belge kimlikleri, sıralama tekrarları ve cevap/çözüm/runtime/QLoRA izolasyonu programatik doğrulamaya alındı | Kaggle’da dosyanın oluşması tek başına geçerli sonuç sayılmaz; keşif dışı belge, eksik sorgu veya cevap anahtarı erişimi ölçümü geçersiz kılar | `0ce42c4`; tam corpus fixture’ı ve güvenlik ihlali regresyonlarıyla 10 test geçti |
| 2026-11 | Eski retrieval çıktısı uyumluluk denetimi | Önceki 11+12 Kaggle çıktısında gecikmelerin liste, yeni koşularda ise özet nesnesi olarak yazıldığı saptandı; doğrulayıcı iki biçimi de açıkça kabul ediyor | Sürüm farkını hata diye yok saymak veya alanı kontrolsüz esnetmek ölçüm güvenilirliğini düşürürdü | Mevcut 2.178 belge/10 sorgu çıktısı başarıyla doğrulandı; 4 regresyon testi geçti. Tam corpus sonucu henüz yok |
