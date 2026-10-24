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
