# Türkçe STEM TTS kayıt protokolü

Bu protokol, kişisel sesle model eğitimi düşünülmeden önce güvenilir ve
denetlenebilir bir private corpus toplamak içindir. Kayıtlar ve transkriptler
`data/private/` dışında tutulmaz, Git'e eklenmez ve öğrenciye dağıtılmaz.

## Kim kayıt yapabilir?

Kendi sesinizle kayıt yapabilirsiniz; profesyonel dublaj eğitimi zorunlu
değildir. Aranan özellik doğal, anlaşılır ve tutarlı Türkçe konuşmadır:

- Cümleleri acele etmeden, yapay biçimde hecelemeksizin okuyun.
- Aynı mikrofon, aynı mesafe ve benzer ses seviyesiyle kayıt alın.
- Matematikte `eşittir`, `kümesi`, `elemanıdır`, `alt küme`, `karekök`,
  `artı/eksi`, üst/alt indis gibi hedef sesletimleri tutarlı söyleyin.
- Her kayıt tek bir kısa okuma birimi olsun; ideal pratik aralık yaklaşık
  3–15 saniyedir. Çok uzun paragraf veya kesilmiş yarım cümle kaydetmeyin.

Arkadaşın sesi veya YouTube kaydı, ancak kayıt sahibinin **açık yazılı izni**
ile kullanılabilir. İzin, sesin TTS/model eğitimi için kullanılacağını,
private saklanacağını ve kişi isterse corpus/modelden çıkarma prosedürünü açıkça
belirtmelidir. Bir videonun herkese açık olması veya kanala erişimin bulunması
tek başına ses modeli eğitimi izni değildir. Çocukların sesini kullanmayın.

## Teknik kayıt standardı

- Sessiz, yankısız bir odada; müzik, TV, bildirim, klavye ve başka konuşma
  olmadan kayıt alın.
- Mono PCM WAV, en az 22.05 kHz ve en az 16-bit kullanın; 24 kHz veya 48 kHz
  tercih edilir.
- Kayıt öncesi 2–3 saniye ortam gürültüsünü dinleyin; patlama, clipping,
  sürekli uğultu veya yankı varsa yeniden kaydedin.
- Kayıt metni ile söylenen ifade tam eşleşmelidir. Metni değiştirmeyin,
  atlamayın; hata olursa dosyayı baştan kaydedin.

## Ayrı veri kümeleri

1. **TTS değerlendirme Gold'u:** En az 50 doğrulanmış ders birimi. Bu set,
   tarayıcı sesi ve model adaylarını kıyaslamak içindir; eğitim için
   kullanılmaz.
2. **Eğitim corpus'u:** Açık rızalı konuşmacının WAV + tam transkript
   çiftleri. Eğitim ve validation bölümleri birbirinden ayrıdır. Dersin
   doğrulanmış konuşma sözleşmeleri bu corpusun prompt kaynağı olur.

Önce değerlendirme Gold'u ile hazır ses motorunun gerçekten yetersiz olduğu
kanıtlanır. Ancak bundan sonra, model ailesinin resmî veri gereksinimine göre
eğitim corpus miktarı kararlaştırılır; rastgele internet sesiyle fine-tuning
başlatılmaz.

Projede bunun için 60 özgün ve dengeli Türkçe STEM sesletim örneğinden oluşan
bir calibration Gold üreticisi vardır. Bu örnekler MEB kaynağı veya öğrenciye
sunulan ders içeriği değildir; yalnız model adaylarını ilk kez sınamak içindir:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.bootstrap_tts_evaluation_gold \
  --output data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json
```

## Aday ses kalite ve dinleyici çalışması

Kaggle'da WAV üretiminin başarılı olması yalnız sentezin tamamlandığını
gösterir; adayın doğru, anlaşılır veya öğrenciye uygun olduğunu göstermez.
Bu nedenle her aday aşağıdaki kapılardan sırayla geçer:

1. Her Gold birimi için private ASR çıktısı veya insan tarafından dinlenmiş
   `observed_spoken_text` oluşturulur. Bu dosya ders metni içerdiği için
   `data/private/` altında kalır ve `tts-candidate-v1` şemasını kullanır.
2. Otomatik sesletim ve kritik belirteç kapısı çalışır. En az 50 Gold örneği
   ve her içerik türünde en az 10 örnek gerekir. `tts-quality-policy-v3`,
   tek bir küresel yüzde yerine tür-bazlı eşikler kullanır: metin için
   `%98 / %95`, alıştırma için `%96 / %97`, tablo ve grafik için `%95 / %97`,
   formül için `%95 / %98` (sırasıyla sesletim / kritik belirteç). Bunlar
   **öğrenci yayım eşiği değil**, insan dinleme testine giriş eşiğidir.
3. Yalnız bu kapıyı geçen aday için üç bağımsız, aday adı gizlenmiş dinleyici
   paketi oluşturulur. Aday yalnız bazı türleri geçerse paketler yalnız bu
   türleri içerir; başarısız türlerden ses öğrenciye açılmaz. Her gözden
   geçiren paketteki tüm örneklerde referans eşleşmesini, anlaşılırlığı ve
   ciddi artefact olup olmadığını işaretler.
4. Aynı WAV checksum'ı, sentez koşusu ve otomatik kalite raporuna bağlı üç
   tam inceleme başarılı olmadan ses varlığı manifesti oluşturulamaz.

Otomatik kalite raporunu, private Gold ve ASR/insan transkriptiyle üretin:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_quality \
  --gold data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json \
  --candidate data/private/tts_evaluation/chatterbox-v2-transcripts.json \
  --output data/private/tts_evaluation/chatterbox-v2-quality.json
```

Karar `tts-candidate-passed-listener-study-required` veya
`tts-candidate-kind-limited-listener-study-required` değilse dinleyici
çalışması ve öğrenci sesi başlatılmaz. İkinci karar yalnız raporda açıkça
listelenen `eligible_kinds` için geçerlidir. Geçerse paketler şöyle hazırlanır:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_listener_study build-packets \
  --gold data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json \
  --synthesis-run data/private/.../run_records.json \
  --automatic-quality-report data/private/tts_evaluation/chatterbox-v2-quality.json \
  --study-id chatterbox-v2-study-001 \
  --reviewer-id reviewer-01 --reviewer-id reviewer-02 --reviewer-id reviewer-03 \
  --output-dir data/private/tts_evaluation/listener-packets
```

Gözden geçiren yanıtları `tts-listener-study-v1` şemasında private toplanır.
Her yanıtta `id`, `audio_sha256`, `matches_reference`, `intelligible` ve
`serious_artifact` alanları bulunur. Toplu karar için:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_listener_study evaluate \
  --gold data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json \
  --synthesis-run data/private/.../run_records.json \
  --automatic-quality-report data/private/tts_evaluation/chatterbox-v2-quality.json \
  --study data/private/tts_evaluation/chatterbox-v2-listener-study.json \
  --output data/private/tts_evaluation/chatterbox-v2-listener-report.json
```

Bir ciddi artefact, eksik inceleme, farklı WAV checksum'ı veya başarısız
otomatik kapı `tts-listener-study-blocked` üretir. Bu raporlar içerik,
transkript, ses yolu veya dinleyici kimliği içermez.

## Adaylar geçmezse: teşhis ve seçim kaydı

ASR eşleşmesi dinleyici deneyiminin yerine geçmez; yine de hangi türün sonraki
deneyde öncelikli olduğunu içerik sızdırmadan gösterir. Aşağıdaki araç,
transkript veya Gold metnini rapora yazmadan tür başına kritik-belirteç kaybı,
tam eşleşme sayısı ve hata şiddeti dağılımı üretir:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_error_analysis \
  --gold data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json \
  --candidate data/private/tts_evaluation/candidate-transcripts.json \
  --output data/private/tts_evaluation/candidate-error-analysis.json
```

Birden çok aday karşılaştırıldığında sıralama veya ortalama puan, öğrenci sesi
seçmek için tek başına kullanılamaz. Bunun yerine aşağıdaki fail-closed seçim
raporu yalnız `eligible_kinds` içeren adayları kör dinleyici testine geçirir:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_candidate_selection \
  --quality-report data/private/tts_evaluation/candidate-a-quality.json \
  --quality-report data/private/tts_evaluation/candidate-b-quality.json \
  --output data/private/tts_evaluation/candidate-selection.json
```

`no_candidate_eligible` sonucu başarısızlık gizlenmez: ses varlığı,
dinleyici paketi ve öğrenci yayımı oluşturulmaz. Sonraki iş hata kümelerine
uygun yeni bir aday veya açık rızalı, eğitim/validation ayrımlı kayıt corpus'u
hazırlamaktır; değerlendirme Gold'u eğitim verisine dönüştürülmez.

## 2026-10-09 ölçüm denetimi ve geçerli karar

Önceki `v2` tarama, PDF/OCR için yazılmış noktalama duyarlı karşılaştırmayı
konuşma transkriptine uyguluyordu. Örneğin Gold'daki `birleşim` kritik sözcüğü
referansta `birleşim.` olarak geçtiğinde bile yanlışlıkla eksik sayılıyordu.
60 örnekte 17 referans birimi en az bir kritik belirteci bu nedenle birebir
taşımıyormuş gibi görünüyordu. `tts-quality-policy-v3` Türkçe büyük/küçük
harfi normalleştirir, konuşulmayan noktalamayı çıkarır, matematik işleçlerini
korur ve Gold kritik belirteçlerinin kendi referansında bulunmasını zorunlu
kılar. Eski raporlar değiştirilmedi; yeni raporlar private `*-quality-v3.json`
dosyalarındadır.

Yeni karar: Chatterbox V3 Nisan referans sesi ve MMS-TUR **yalnız `text`**
türünde otomatik *dinleyici testine giriş* kapısını geçti. Chatterbox V2 hiçbir
türde geçmedi. Formül/tablo/grafik/alıştırma hâlâ engelli. Her aday için üç
özel dinleyici paketi `data/private/tts_evaluation/*-text-v3-listener-packets/`
altında hazırlandı; her pakette yalnız 12 düz metin birimi vardır. Her iki
adayın 12/12 metin WAV'ı yerelde manifest SHA-256 ile doğrulandı. Paket
oluşturmak insan dinlemesini gerçekleştirmek **değildir**; yanıtlar ve
bağımsız kör dinleme olmadan öğrenciye model sesi açılamaz. Bu Gold ayrıca
özgün sentetik kalibrasyon cümlelerinden oluşur, gerçek ders sayfalarının
anlaşılırlığını tek başına kanıtlamaz.
Offline dinleme arayüzü, üç dinleyicinin görevleri ve yanıtları birleştirme
komutu `docs/tts-dinleme-pilotu.md` içindedir.

Çalışan öğrenci arayüzünde cihazın **yerel** Türkçe sesi listelenir/seçilir.
Yerel Türkçe ses yoksa sistem sessizce başka dilin veya uzak TTS servisinin
sesine geçmez. Onaylı WAV
bulunmadığında yalnız yayımlanmış metin bu cihaz sesiyle okunabilir;
matematik veya OCR taslağına ham TTS uygulanmaz.

**Bir sonraki karar noktası:** üç bağımsız dinleyici, iki adayın metin
örneklerini aday kimliği gizli biçimde dinler; eksik/yanlış sözcük, anlaşılma
ve artefact işaretler. Başarılı sonuçtan sonra bile gerçek yayımlanmış ders
metni için ayrı kaynak-bağlı Gold ve öğrenci görev testi gerekir. Formül ve
tablo için önce kanonik Türkçe okunuş/gold hatalarını kapatıp sonra yeni
sentez denemesi yapılmalıdır. Fine-tuning henüz yapılmadı; aynı hatalı
değerlendirme üstüne eğitim başlatmak GPU ve veri israfı olurdu.

## Private manifest ve doğrulama

Örnek manifest yapısı (metinler burada temsili tutulur; gerçek içerik private
dosyada kalır):

```json
{
  "schema_version": "tts-training-corpus-v1",
  "consent": {
    "speaker_reference": "speaker-001",
    "source": "self-recorded",
    "adult_consent_attested": true,
    "voice_model_training_consent_attested": true,
    "withdrawal_process_available": true
  },
  "recordings": [
    {
      "id": "utterance-001",
      "audio_path": "audio/utterance-001.wav",
      "transcript": "private verified spoken text",
      "kind": "formula",
      "split": "train"
    }
  ]
}
```

Corpus en az bir `train` ve bir `validation` kaydı içermelidir. Manifesti,
ses veya metni rapora yazmadan şu komutla doğrulayın:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_training_corpus \
  --manifest data/private/tts_voice_corpus/manifest.json \
  --audio-root data/private/tts_voice_corpus \
  --output data/private/tts_voice_corpus_validation.json
```

Doğrulama yalnız dosya yapısı, WAV standardı, süre istatistikleri ve rıza
attestasyonunu raporlar. Bu rapor `corpus-structure-valid` dese bile model
eğitiminin uygun veya başarılı olacağını iddia etmez.

## Harici veri kaynakları: Nisan sesi ve matematik alan verisi

Bir Hugging Face veri kartı, ses modeli eğitimi izni yerine geçmez. Özellikle
birleştirilmiş çok-konuşmacılı bir veri seti, tek bir hedef ses için doğrudan
eğitim corpus'u değildir. Her harici kaynak önce private kaynak kayıt defterine
ayrı rolüyle girer:

- **Nisan Kumru hedef sesi:** Tek-konuşmacı eğitim yolu yalnız Nisan'a ait
  kaynaklar için açılır. Kaynağın gerçekten tek konuşmacı olduğunu, ses ve
  transkript kullanım hakkını, açık ses-modeli eğitimi iznini ve geri çekme
  sürecini doğrulayan private bir izin kaydı olmadan ses indirilmez veya
  fine-tuning'e eklenmez.
- **`afkfatih/turkish-tts-combined-raw`:** Kaynak envanteri olarak ele
  alınır; farklı konuşmacıların WAV'ları tek-ses eğitimine karıştırılmaz.
  İçinden kullanılacak bir alt kaynak ayrıca kayda alınır ve yukarıdaki Nisan
  koşullarını tek başına geçmelidir.
- **`ysdede/khanacademy-turkish-math`:** İlk kullanım rolü ses eğitimi değil,
  Türkçe matematik okunuşu kalıplarının analizi ve domain değerlendirmesidir.
  Bu sesler hedef konuşmacının sesiyle karıştırılmaz. Metin kullanım hakkı
  kayda geçmeden bu rol de açılmaz.

Bu kaydı üretmek için (kayıt dosyası private tutulur):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_source_registry \
  --registry data/private/tts_sources/registry.json \
  --output data/private/tts_sources/validation-report.json
```

`voice-training-blocked` kararı bir hata değil, eksik köken/izin varken
sesin yanlışlıkla eğitime girmesini önleyen beklenen davranıştır. Ancak
`private-corpus-intake-permitted` sonucundan sonra seçili WAV'lar normal
`tts-training-corpus-v1` denetimine verilebilir.

## Matematik okunuşu: önce deterministik plan, sonra ses

Formül için modelin ham OCR, Markdown veya LaTex'i doğrudan seslendirmesi
yasaktır. `turkish_math_speech` yalnız tam doğrulanmış MathML ve tam kalite
kanıtı aldıktan sonra sınırlı, sürümlenmiş bir Türkçe okunuş planı üretir.
Şimdiki güvenli alt küme; sayılar, işlem/karşılaştırma/küme operatörleri,
kesir, karekök/kök, üst indis, alt indis ve parantezdir. Bilinmeyen MathML
etiketi, aşırı karmaşık ifade veya bozuk işaretleme fail-closed reddedilir;
öğretmen doğrulanmış alternatif okunuş girene kadar öğrenciye ses üretilmez.

Bu plan TTS modelini değiştirmez. Önce kanonik `spoken_text` üretir; ses
motoru yalnız bu planı kullanır. Böylece seçilecek Nisan sesli aday ve
tarayıcı TTS'i aynı matematik dilbilgisini paylaşır.

## Öğrenciye ses teslim kapısı

Bir Kaggle/TTS adayının WAV üretmiş olması öğrenciye sunulması için yeterli
değildir. Öğrenci API'si yalnız `verified-tts-audio-assets-v2` manifestindeki
şu bağların hepsi doğrulandığında sesi verir:

- öğrenci belgesi ve yayımlanmış sürüm numarası;
- doğrulanmış okuma biriminin `spoken_text` SHA-256 değeri;
- dinleyici çalışmasından geçmiş adayın kalite raporu checksum'ı;
- dinleyici çalışmasının geçtiği açık işaret;
- WAV dosyasının byte uzunluğu ve SHA-256 değeri.

Manifestin kendi `listener_study_passed` bayrağı artık yeterli değildir.
Ses klasöründeki `quality_report.json` ve `listener_report.json` dosyalarının
hash'leri manifestle eşleşir; kalite raporu en az 50 Gold/ilgili türde en az
10 örnek, uygun otomatik karar ve **`source-bound-release`** kapsamı taşımalı;
dinleyici raporu aynı adaya ve kalite raporuna bağlı, en az üç tam incelemeyle
geçmiş olmalıdır. Bu turn'deki 60 sentetik kalibrasyon Gold'u
`evaluation_scope=calibration` sayılır; kendi başına öğrenci WAV'ı açamaz.

Belge metni, yayın sürümü veya WAV sonradan değişirse eşleşme bozulur ve API
`404` döndürür. Öğrenci okuyucusu bu durumda başka bir dosyayı tahmin ederek
çalmaz; varsa yalnız aynı doğrulanmış metnin tarayıcı/işletim sistemi sesini
kullanır. Ses varlıkları varsayılan olarak
`data/derived/student-audio/<document-id>/` altında private tutulur ve Git'e
eklenmez.
