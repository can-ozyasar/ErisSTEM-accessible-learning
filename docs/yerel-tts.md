# Yerel Türkçe seslendirme

Uygulama, Docker iç ağında çalışan Piper `tr_TR-dfki-medium` motorunu kullanır.
Motor CPU ile çalışır; ses, kaynak metin ve WAV verisi dış bir TTS sağlayıcısına
gönderilmez. Ders ve sınav ses uçları yalnız yerel onaylı içerikteki birimi
çözer. Ayrı `interface-speech` uç noktası geliştirme modunda, ekranda gösterilen
arayüz/koç metnini en çok 600 karakterle ve geçici olarak seslendirir; üretimde
kapalıdır ve metin/WAV saklamaz.

Doğrulanmış ders, soru ve tarih bölümlerinin WAV çıktısı özel Docker volume'ünde
içerik özetiyle saklanır. Aynı metin ikinci kez istendiğinde Piper yeniden
çalışmaz; WAV doğrudan döner. Arayüz keşif sesleri ve öğrenci tarafından girilen
metinler bu kalıcı önbelleğe yazılmaz.

Tarih kitabındaki `MÖ` ve Roma rakamıyla yazılmış yüzyıllar yalnız ses
metninde açılır; PDF metni aynı kalır. `Metropolitan Art Museum` adı
Türkçe ses modeline uygun `Metropoliten Art Müziyum` biçiminde hazırlanır.
Cümlenin tamamı **tek Türkçe sesle** sentezlenir; kurum adı için ses değişmez.
Diğer yabancı özel adlar için otomatik telaffuz tahmini yapılmaz; okunuşları
ayrıca gözden geçirilmelidir.

Seslendirme sırası şöyledir:

1. Dinleyici çalışması ile onaylanmış, sürüme bağlı kayıt varsa bu WAV kullanılır.
2. Böyle bir kayıt yoksa yerel Piper Türkçe motoru aynı doğrulanmış okuma
   birimini sentezler.
3. Yerel motor kullanılamıyorsa metin ekranda ve ekran okuyucuda kalır; tarayıcı
   yerleşik sesine veya başka dile sessizce düşülmez. Sesli komut/transkript
   desteği kapalı olsa da klavye ve ekran okuyucu akışı kullanılabilir.

25 Kasım 2026 itibarıyla 81 soruluk AYT Tarih yerel aday paketinin kök ve beş
şık birimleri için 486 Piper WAV'ı üretildi ve API üzerinden geçerli oldukları
doğrulandı. Yerel cache normal Docker yeniden başlatmalarında korunur. Aktif
paketle checksum/metin eşleşen fine-tuned V5 sabit kaydı bulunmadığından, bu
486 kayıt fine-tune sesi değil, Piper üretimidir. Tek makinede 4 CPU ayrılarak
ölçülen beş koç-yanıt WAV isteğinin p95'i 2,31 sn idi; bu küçük örneklem başka
donanımlar için performans garantisi değildir. Tam ölçüm ve kısıtlar [pilot
kabul raporundadır](../reports/ayt-private-pilot-acceptance-v1.json).

25 Kasım'daki ayrı envanter denetimi iki yerel V5 kurulumundaki 466 aday WAV'ı
da kontrol etti. Bunların kaynak soru paketi SHA-256'sı aktif paketten farklıydı;
504 sabit birimin hiçbirinde birebir paket/metin/model/WAV doğrulaması
sağlanmadı (0/504). Bu yüzden eski V5 WAV'ları yeni sorulara yeniden
eşleştirilmedi ve öğrenci yolunda Piper kaldı. Denetim özeti kabul raporundaki
`fine_tuned_static_audio_inventory` alanındadır; içerik taşımayan yerel kayıt
`data/private/ayt-history-exam/ogm-ai-reviewed-v5-static-audio-inventory-2026-11-25.json`
dosyasındadır.

Eksik aday sesleri üretmek için yalnız özel Kaggle'a gönderilecek bir girdi
hazırlandı: 487 sabit birim (387 benzersiz, rakam içermeyen metin); telaffuz
incelemesi bekleyen 17 rakamlı birimin metni yüklemeden çıkarıldı. Yalnız
manifest yüklendi; PDF, MEB kanıtı ve öğrenci verisi gönderilmedi. Özel Kaggle
sürüm 2, eski dataset mount yolu varsayımı nedeniyle `missing_manifest` hatası
verdi; sentez başlamadı. Sürüm 3, tek manifesti `/kaggle/input` altında şemayla
bulup model checksum'ını bağımlılık kurulumundan önce doğrulayarak bu kök nedeni
giderdi. Sürüm 3, 25 Kasım 2026 12:26:57–13:03:51 UTC arasında Tesla T4
üzerinde tamamlandı. 387/387 benzersiz, rakam içermeyen metin üretildi. Girdi
manifesti, model ve runner checksum'ları beklenen değerlerle eşleşti. WAV'ların
tamamı checksum ve boyut bakımından doğrulandı; tümü geçerli mono 24 kHz PCM
olarak açıldı. Üretim kaydı
`data/private/kaggle-notebook-outputs/muhammedcanozyasar/eristem-tts-v5-demo-full/20261125T130446Z/eristem-tts-v5-demo-generated-v1/run_records.json`
yolundadır. Bu otomatik kontroller telaffuz/doğallık onayı değildir.

Bu kapı artık yalnız belge düzeyinde değil, çalışma anında da zorunludur:
kurulum aracı `runtime_enabled: false` ve `requires_listening_review: true`
yazar; API bu bayraklar değişmeden V5 WAV'ı sunmaz ve Piper'a düşer. 487 kaynak
birimi 387 WAV'a bağlandı ve kapalı aday paketine kuruldu:
`data/private/tts-v5-ayt-static-candidate-2026-11-25/`. Yerel dinleme sayfası
`data/private/tts-v5-ayt-static-candidate-2026-11-25/listener-review-v2.html`
yolunda hazır. WAV'lar ancak paket/model/metin checksum'ları eşleşip dinleyici
onayı alındıktan sonra etkinleştirilebilir. Bu koşum öğrenciye veya kamuya
yayın izni anlamına gelmez.

Yeni koşularda indirilen WAV'lar önce
`experiments/kaggle/install_v5_demo_audio.py` ile checksum doğrulamalı fakat
kapalı bir aday klasörüne kurulmalıdır. Dinleme sayfası yerelde hazırlanır:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.prepare_ayt_v5_audio_listener_review \
  --input-manifest data/private/tts-v5-ayt-static-input-2026-11-25-minimized/manifest.json \
  --candidate-root data/private/tts-v5-ayt-static-candidate-2026-11-25 \
  --output data/private/tts-v5-ayt-static-candidate-2026-11-25/listener-review-v2.html
```

Sayfayı tarayıcıda açıp dinlenen her kayıt için anlaşılabilirlik, telaffuz ve
artefakt alanlarını seçin; incelemediğiniz birimleri boş bırakın. Sayfanın
indirdiği `ayt-v5-listener-review.json` yalnız seçili kararları ve metin
checksum'larını içerir. Ardından
`app.pipeline.promote_ayt_v5_reviewed_audio` yalnız tüm kalite alanlarını geçen
açık onayları yeni bir klasöre çıkarır. Reddedilen, incelenmeyen ve sayılı
birimler etkinleşmez; Piper bunları okumaya devam eder.

Piper sesi, `tr_TR-dfki-medium` model kartındaki CC BY-NC-SA 4.0 veri lisansı
nedeniyle geliştirme ve araştırma kurulumu içindir; ticari/halka açık yayına
otomatik taşınmaz. Yayın için ses/model lisansı, metin hakkı ve dinleyici
doğrulaması ayrı kontrol edilmelidir. Piper'ın Türkçe, ONNX ve yerel HTTP
çalışma biçimi [Piper belgelerinde](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md)
ve [ses model kartında](https://huggingface.co/rhasspy/piper-voices/tree/main/tr/tr_TR/dfki/medium)
belgelenmiştir.

Eğitilmiş Chatterbox Multilingual V3 V5 T3 ağırlığı araştırma artefaktı olarak
mevcuttur; fakat etkin 81 soruluk paket için doğrulanmış sabit ses envanteri
0/504'tür. Yerel servis için gereken temel Chatterbox dosyaları ve referans
ses bu makinede hazır değildir; bu yüzden ağırlık öğrenci yoluna bağlanmamıştır.
V5 ancak tüm birimler checksum/metin/model sürümüne bağlandığında, Türkçe tarih
okunuşları dinleyiciyle kontrol edildiğinde ve gerçek cihaz performans kapısını
geçtiğinde seçilebilir. Dinleyici karşılaştırması olmadan Piper'dan üstün olduğu
iddia edilmez.

9 Ekim 2026 yerel kurulum doğrulamasında model imaj içine indirildi ve API
üzerinden doğrulanmış demo birimi için 22.050 Hz mono WAV üretildi. TTS
servisinin portu ana makineye yayınlanmaz.
