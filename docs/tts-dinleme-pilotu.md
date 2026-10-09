# Özel TTS dinleme pilotu — düz metin

Bu çalışma ses modelini eğitmez ve öğrenci yayını yapmaz. Eski `v2` kalite
raporları korunur; noktalama/Türkçe normalizasyonu düzeltilen `v3` raporları
iki adayı yalnız **düz metin** dinleme aşamasına almıştır. 60 örneklik Gold,
özgün sentetik kalibrasyondur; gerçek ders içeriğinin kalite kanıtı değildir.

## Hazır özel materyal

`data/private/tts_evaluation/blind-study-v3/` altında `voice-a` ve `voice-b`
klasörleri vardır. Her birinin `reviewer-01`, `reviewer-02`, `reviewer-03`
alt klasöründe çevrimdışı açılabilen `index.html` ve 12 checksum doğrulanmış
WAV bulunur. Aday eşlemesini dinleyicilere söylemeyin. Paketler ve cevaplar
private kalır; repoya veya öğrenci uygulamasına yüklenmez.

Üç bağımsız dinleyiciye kendi numarasındaki A ve B klasörlerini verin.
Sırayı dengeleyin: örneğin 1 ve 3 önce A'yı, 2 önce B'yi dinlesin. Her
örnekte ses–referans eşleşmesi, anlaşılabilirlik ve ciddi artefact ayrı
işaretlenir. Başkası adına “hepsi geçti” yanıtı doldurulmaz. İndirilen iki
`listener-response.json` dosyasını aday ve dinleyiciye göre ayrı adlandırıp
`data/private/tts_evaluation/blind-study-v3/responses/` altında saklayın.

## Değerlendirme

Üç gerçek yanıt mevcut olunca şu sırada ilerleyin:

1. `python -m app.pipeline.tts_listener_response_assembly` ile her adayın
   üç paketi ve üç yanıtını, ilgili private `run_records.json` dosyasına
   bağlayıp `tts-listener-study-v1` manifesti üretin. Kimlik, örnek ve WAV
   checksum uyuşmazsa komut durur.
2. `python -m app.pipeline.tts_listener_study evaluate` ile aynı Gold,
   sentez koşusu, `*-quality-v3.json` ve birleşik yanıt manifestini puanlayın.
   Bir eksik/yanlış yanıt veya ciddi artefact geçişi engeller.
3. Dinleyici geçişi bile yalnız *kalibrasyon* bulgusudur. Gerçek yayımlanmış
   doğrudan metinden ayrı, insan doğrulamalı private değerlendirme kümesi ve
   ekran okuyucu kullanan öğrenci görev testi olmadan ses varlığı yayımlanmaz.

Örnek A adayının üç yanıtını birleştirme komutu (yollar yanıtların konumuna
göre uyarlanır):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.tts_listener_response_assembly \
  --packet data/private/tts_evaluation/chatterbox-v3-text-v3-listener-packets/reviewer-01.json \
  --packet data/private/tts_evaluation/chatterbox-v3-text-v3-listener-packets/reviewer-02.json \
  --packet data/private/tts_evaluation/chatterbox-v3-text-v3-listener-packets/reviewer-03.json \
  --response data/private/tts_evaluation/blind-study-v3/responses/voice-a-reviewer-01.json \
  --response data/private/tts_evaluation/blind-study-v3/responses/voice-a-reviewer-02.json \
  --response data/private/tts_evaluation/blind-study-v3/responses/voice-a-reviewer-03.json \
  --synthesis-run data/private/kaggle-notebook-outputs/muhammedcanozyasar/eristem-tts-cb-v3-ref-v1/20261008T151258Z/eristem-private-tts-chatterbox-v3-reference-v1/run_records.json \
  --output data/private/tts_evaluation/voice-a-text-v3-listener-study.json
```

`voice-b` için aynı komutta `mms-tur-text-v3-listener-packets`, B yanıtları
ve MMS sentez koşusu kullanılır. Birleşik manifestte referans metin veya
ses yolu yoktur; yine de dinleyici yanıtları private tutulmalıdır.

## Başarıyı ne sayacağız?

- Öğrenci her türde doğru kavramı anlayabiliyor mu? Salt ASR harf doğruluğu
  bu soruyu cevaplamaz.
- Formülde işleç, tabloda başlık/hücre, grafikte eksen ve sayısal birim yanlış
  söyleniyorsa ses güzel olsa da o tür kullanılmaz.
- Fine-tuning ancak gerçek hata kümeleri insan dinlemesiyle doğrulanınca,
  izinli tek-konuşmacı kayıtlar ve ayrı train/validation seti hazır olunca
  başlatılır. Bu pilot için yeni Kaggle GPU koşusu gerekmiyor.
