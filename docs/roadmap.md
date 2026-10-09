# ErişSTEM ürün ve mühendislik yol haritası

## 9 Ekim 2026 — Modüler öğrenme atölyesi

Öğrenci çalışma rotası kümeler, çember ve uçak için ön bilgi → kavram keşfi ve
rehberli çalışma → yeni yardımsız görev → 24 saat sonra farklı görev akışına
genişletildi. İlk yanıt, yardım ve geçilen sorular ayrı yerel kayıtlardır;
resmî sınav puanı veya kalıcı öğrenme başarısı olarak sunulmaz.
Uygulanan kapsam ve teknik doğrulama [atölye uygulama notunda](ogrenme-atolyesi-uygulama.md),
görme engelli kullanıcılarla yapılacak görevler [pilot protokolünde](ogrenme-atolyesi-pilot.md)
bulunur. Uzman içerik incelemesi, gerçek ekran okuyucu görevleri ve öğrenme etkisi
hâlâ kabul kapılarıdır. Aşağıdaki aşamalar içerik dönüşümü omurgasını anlatır.

Amaç PDF OCR çıktısını göstermek değil; doğrulanmış STEM içeriğini öğrenciye
ekran okuyucu, TTS ve Braille ile güvenilir biçimde sunmaktır. Öğretmen,
her içeriği yeniden yazan kişi değil; yalnız otomatik kalite kapısının belirsiz
bulduğu istisnaların denetçisidir.

## Aşama 1 — Güvenilir içerik omurgası

- Metin, formül, tablo, grafik ve alıştırma için kanonik kaynak-bağlı içerik
  sözleşmesi.
- Her blokta koordinat/checksum, okuma sırası, ekran okuyucu etiketi, sesli
  temsil ve kalite kanıtı.
- Öğrenci okuyucusu için doğrulanmış bloklardan üretilen sıralı okuma planı;
  düşük güvenli bloklar bu plana giremez.
- `auto-approved`, `review-required`, `blocked` kararları; confidence tek
  başına hiçbir zaman yayın kararı vermez.
- Kaynak bağı, şema veya render bozulursa içerik öğrenciye hiç ulaşmaz.

Başarı ölçütü: yüksek kaliteli doğrudan metin blokları öğretmene gitmeden
yayın adayına dönüşür; riskli bloklar eksiksiz izlenebilir bir istisna
kuyruğuna gider.

## Aşama 2 — Tür-özel çıkarım ve Gold kapıları

- Metin: Türkçe karakter, okuma sırası ve kaynak-metni tutarlılığı.
- Formül: MathML, kritik operatör, görsel render ve Türkçe okunuş doğrulaması.
- Tablo: hücre geometrisi, başlık ilişkileri, sembol doğruluğu ve Gold ölçümü.
- Grafik: eksen/seri/tutum modeli ve erişilebilir trend özeti.
- Alıştırma: soru, seçenek, formül ve görsel ilişkisini koruyan yapı.

Başarı ölçütü: her tür kendi Gold metriğini geçmeden otomatik yayına aday
olamaz. VLM/OCR yalnız aday üretir; karar vermez.

## Aşama 3 — Öğrenci okuyucusu, TTS ve Braille

- Başlık, paragraf, formül, tablo, grafik ve alıştırmalar arasında klavye ve
  ekran okuyucu ile tür-bazlı gezinme.
- Türkçe TTS: hız, duraklat/devam, cümle/öğe atlama; matematik için kısa ve
  ayrıntılı okunuş modu.
- İlk sürüm, işletim sistemi/tarayıcının Türkçe sesini yalnız doğrulanmış
  okuma planı üzerinde kullanır. Fine-tuning ancak lisanslı ses kayıtları,
  matematik sesletim Gold'u, kör kullanıcı görev testleri ve mevcut sese karşı
  anlaşılabilirlik değerlendirmesiyle başlatılır.
- Braille adaptörü: kanonik metin/MathML'den gerçek Türkçe-matematik Braille
  dönüşümü; Unicode görsel taklidi değil.
- Formül, tablo ve grafik için ayrı ses/Braille sözleşmeleri: formülde kısa ve
  ayrıntılı MathML okunuşu; tabloda yapısal gezinme; grafikte yalnız
  doğrulanmış eksen ve özet. Bu sözleşmeler haricinde TTS/AI açıklama üretemez.
- NVDA+Firefox, TalkBack+Chrome ve klavye görev testleri release kapısıdır.

Başarı ölçütü: öğrenci bir formülü, tabloyu ve grafiği fare kullanmadan
anlayıp gezinebilir; ses ve Braille aynı doğrulanmış kaynaktan gelir.

### Etkin öğrenme dikey dilimi (uygulandı; kullanıcı doğrulaması bekliyor)

- `sets-grade9-v1`: MEB PDF'sinden çıkarılmamış, sürümlü ve sentetik 9. sınıf
  kümeler alıştırmaları. Birleşim, kesişim ve fark için rehberli soru → benzer
  yardımsız tekrar akışı. Yanıtlar deterministik küme cebriyle denetlenir;
  cevap anahtarı veya ipuçları öğrenciye indirilen soru verisinde bulunmaz.
- Yanlış rehberli yanıta en çok üç basamaklı, cevabı açık etmeyen, önceden
  yazılmış ipucu; aktarım sorusunda ipucu yok. Yanıt metni saklanmaz; yalnız
  tamamlanan adımlar, sürüm anahtarıyla öğrencinin cihazında tutulur.
- Standart metin girişi cihazın Braille klavyesine açıktır. Soru yerel Türkçe
  TTS varsa seslendirilebilir; yoksa yanlış dilde ses seçilmez, ekran okuyucu
  metni kullanılır. Bu, matematiksel Braille veya erişilebilirlik kullanıcı
  testlerinin tamamlandığı anlamına gelmez.
- Sonraki kalite kapısı: görme engelli öğrencilerle gerçek görev testi,
  bağımsız ilk-deneme/tekrar başarısı ve geri bildirim ölçümü. Ardından ancak
  öğretmen doğrulamalı özgün ders soruları sisteme alınacak; LLM yalnız kaynak
  bağlı, sınırlı açıklama adayı olabilir ve deterministik denetimi geçemez.

## Aşama 4 — Öğrenen kalite sistemi

- Öğretmen düzeltmeleri anonimleştirilmiş private Gold örneklerine dönüşür.
- Hata kümeleri (sembol, tablo başlığı, formül operatörü, grafik ekseni)
  ayrı ölçülür.
- Yalnız Gold'da kanıtlanan modeller/rule-set'ler sürüme alınır; gerileme
  öğrenci yayımını otomatik durdurur.
- Fine-tuning, ancak yeterli çeşitlilikte Gold veri ve baseline başarısızlığı
  varsa değerlendirilir.
- TTS otomatik kapısı artık tek bir ortalama ile karar vermez: en az 50 private
  Gold örneği ve her değerlendirilen tür için en az 10 örnek gerekir. Metin,
  alıştırma, tablo, grafik ve formülün ayrı sesletim/kritik-belirteç eşikleri
  vardır. Formül en sıkı kritik-belirteç eşiğine sahiptir. Bu eşikler yalnız
  kör dinleyici çalışmasına giriş içindir; öğrenci yayımı değildir. Bir aday
  yalnız geçtiği türler için dinleyici çalışmasına girebilir; diğer türler
  doğrulanmış tarayıcı TTS'inde kalır.
- `build_tts_gold` yalnız otomatik kalite kapısını geçmiş kanonik okuma
  birimlerinden private TTS Gold hazırlar. Öğretmen yalnız kritik sesletim
  belirteçlerini örneklem bazında denetler; ders içeriğini baştan yazmaz.
- TTS aday seçimi katmanlıdır: tarayıcı sesi yalnız geliştirme tabanı; lisans
  incelemeli hafif yerel ONNX aday ile CUDA üzerinde kalite adayı aynı private
  Gold ile karşılaştırılır. Eğitim, izinli konuşmacı kayıtları ve baseline'a
  karşı kör dinleyici iyileşmesi olmadan başlatılmaz (ADR 0016).
- Eğitim corpus'u için açık rıza, geri çekme süreci, WAV kalite denetimi ve
  train/validation ayrımı zorunludur. Herkese açık video veya kanal erişimi
  eğitim rızası yerine geçmez; `tts_training_corpus` yalnız private yapı
  denetimi yapar, ses/model kalitesi kararı vermez.
- Onaylı TTS sesleri öğrenciye ancak belge sürümü, doğrulanmış konuşma metni
  hash'i, aday kalite raporu, dinleyici çalışması ve WAV checksum'ı birlikte
  eşleşirse sunulur. Eşleşmeyen veya eksik ses dosyası için sistem rastgele
  bir artefact göstermez; onaylı metin üzerindeki tarayıcı TTS'iyle sınırlı
  kalır.
- Harici TTS kaynakları için `tts-training-source-registry-v1` vardır.
  Birleştirilmiş çok-konuşmacılı setler tek-ses fine-tuning'e doğrudan
  giremez. Hedef konuşmacı için tek-konuşmacı, ses/transkript hakkı, açık
  ses-modeli eğitimi izni, geri çekme süreci ve private izin kaydı birlikte
  şarttır. Matematik ders sesi ayrı bir `math-text-analysis` rolünde tutulur;
  hedef sesle karıştırılmaz.
- Formül okunuşu bir üretken modele bırakılmaz. Tam kalite kapısından geçen
  MathML, `turkish-math-speech-v1` ile sınırlı/deterministik Türkçe konuşma
  planına derlenir. Desteklenmeyen notasyon reddedilir ve öğretmen denetimine
  gider; ham OCR/LaTex öğrenci TTS girdisi değildir.

## Mevcut durum

Öğrenme atölyesine uzman içerik incelemesi, rıza referanslı yetişkin pilotu,
sürüm bağlı yayın kontrolü ve kaynaklı 2026 sınav erişim provası eklendi.
Prova kayıtları gerçek katılımcı kanıtı sayılmaz; kritik kullanıcı sorunu,
eski içerik kanıtı veya eksik uzman onayı yayını engeller. Sınav akışı altı
özgün prosedür sorusuyla gezinme ve zaman yönetimi çalıştırır; tam müfredat
denemesi değildir. Kurulum, ekranlar ve kalan insan doğrulamaları
[tam uygulama işletim notlarında](tam-uygulama-isletim.md) açıklanır.

Kaynak bağlama, tablo öğretmen istisna kuyruğu, immutable kalite raporu ve
sembol Gold kapısı mevcuttur. PaddleOCR-VL, 9 kritik sembolde yüzde 0 exact
doğruluk verdiği için otomatik yayın adayı değildir. Öğrenci arayüzü artık
yayımlanmış belge listesini, doğrulanmış metin okuma planını ve yayımlanmış
tabloları yapısal HTML ile gösterir. Başlık/paragraf için Türkçe Liblouis
Grade 1 dönüşümü kaynak metne geri dönüş denetimiyle açılır; desteklenmeyen
karakter veya matematik sembolünde kapalı kalır. Bu, matematiksel Braille
veya fiziksel Braille ekranı doğrulaması anlamına gelmez.
Mobil öğrenci kabuğu ekran okuyucunun yerel kaydırma/çift dokunma
davranışlarıyla uyumlu menü, History API geri dönüşü ve cihazın Braille
klavyesine açık standart yazı alanı içerir. Ayrıntılar
`docs/mobil-erisebilirlik.md` dosyasındadır.
Yayımlanmış metin için kaynak sürümüne bağlı, cihazda saklanan isteğe bağlı
hatırlama/tekrar akışı ve basit yayımlanmış tablolar için hücre odaklı gezinme
eklendi. Bunlar öğrenciyle görev testinden geçmedikçe erişilebilirlik başarısı
olarak sayılmaz. Araştırma, uygulanmış kapsam, P0–P2 işleri ve kabul kapıları
`docs/ogrenci-ogrenme-deneyimi.md` dosyasındadır.
Öğretmen tarafından kaynak PDF üzerinde Türkçe okunuşu onaylanıp bağımsız
onaylayıcı tarafından yayımlanmış, desteklenen MathML formülleri artık
deterministik Türkçe okuma planına girer. Öğretmen paneli LaTeX göstermeden
önerilen okunuşu sunar; yanlışsa onay engellenir ve özel düzeltme gerekir.
Yayımlanmış tablolarda her hücre satır/sütun ve başlığıyla odaklanabilir;
bilinen matematik sembolleri Türkçe sözcüklere çevrilir. Bilinmeyen sembol
için uygulama TTS'i anlam uydurmaz; öğretmen yalnız istisna hücrenin Türkçe
okunuşunu kaynakla karşılaştırarak yazabilir. Bunlar ses modelinin başarısı değil,
ses modelinden önceki içerik ve gezinme katmanıdır.

Üç TTS adayının ilk 60 örneklik ASR/Gold karşılaştırmasındaki "hiçbir aday
uygun değil" sonucu, konuşulmayan noktalamayı hata sayan ölçümden
etkilenmişti. Düzeltme ve immutable v3 yeniden puanlamasında Nisan referanslı
Chatterbox V3 ile MMS-TUR yalnız düz metin dinleyici çalışmasına giriş hakkı
kazandı; diğer türler engelli ve aday sesleri öğrenciye açılmadı. Ayrıntı ve
sonraki insan değerlendirmesi `docs/tts_kayit_protokolu.md` içindedir.
Öğrenci WAV kapısı artık yalnız manifestteki onay bayrağına güvenmez; hash'li
kalite/dinleyici raporlarını ve kaynak-bağlı release Gold kapsamını da arar.
Desteklenmeyen formüller için düzeltme akışı ve matematiksel Braille, grafik ve alıştırma yapısal
gezinmesi, masaüstü ve mobil ekran okuyucularla kör görev testleri ile
doğrulanmış matematik Braille standardı hâlâ Aşama 3 release engelleridir.
