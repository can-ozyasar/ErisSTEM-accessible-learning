# ErişSTEM ürün ve mühendislik yol haritası

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

## Aşama 4 — Öğrenen kalite sistemi

- Öğretmen düzeltmeleri anonimleştirilmiş private Gold örneklerine dönüşür.
- Hata kümeleri (sembol, tablo başlığı, formül operatörü, grafik ekseni)
  ayrı ölçülür.
- Yalnız Gold'da kanıtlanan modeller/rule-set'ler sürüme alınır; gerileme
  öğrenci yayımını otomatik durdurur.
- Fine-tuning, ancak yeterli çeşitlilikte Gold veri ve baseline başarısızlığı
  varsa değerlendirilir.
- TTS için en az 50 private Gold sesletim örneği, yüzde 98+ sesletim doğruluğu,
  kritik matematik belirteçlerinde yüzde 100 doğruluk ve ardından kör kullanıcı
  dinleyici çalışması zorunludur. Bu kapı geçilmeden özel ses modeli seçilmez.
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

## Mevcut durum

Kaynak bağlama, tablo öğretmen istisna kuyruğu, immutable kalite raporu ve
sembol Gold kapısı mevcuttur. PaddleOCR-VL, 9 kritik sembolde yüzde 0 exact
doğruluk verdiği için otomatik yayın adayı değildir. TTS/Braille henüz ürün
özelliği değildir; Aşama 3'ün kabul kriterleri sağlanmadan tamamlandı diye
işaretlenmeyecektir.
