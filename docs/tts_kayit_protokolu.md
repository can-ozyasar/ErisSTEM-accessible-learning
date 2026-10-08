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
   ve her içerik türünde en az 10 örnek gerekir. `tts-quality-policy-v2`,
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

## Öğrenciye ses teslim kapısı

Bir Kaggle/TTS adayının WAV üretmiş olması öğrenciye sunulması için yeterli
değildir. Öğrenci API'si yalnız `verified-tts-audio-assets-v1` manifestindeki
şu bağların hepsi doğrulandığında sesi verir:

- öğrenci belgesi ve yayımlanmış sürüm numarası;
- doğrulanmış okuma biriminin `spoken_text` SHA-256 değeri;
- dinleyici çalışmasından geçmiş adayın kalite raporu checksum'ı;
- dinleyici çalışmasının geçtiği açık işaret;
- WAV dosyasının byte uzunluğu ve SHA-256 değeri.

Belge metni, yayın sürümü veya WAV sonradan değişirse eşleşme bozulur ve API
`404` döndürür. Öğrenci okuyucusu bu durumda başka bir dosyayı tahmin ederek
çalmaz; varsa yalnız aynı doğrulanmış metnin tarayıcı/işletim sistemi sesini
kullanır. Ses varlıkları varsayılan olarak
`data/derived/student-audio/<document-id>/` altında private tutulur ve Git'e
eklenmez.
