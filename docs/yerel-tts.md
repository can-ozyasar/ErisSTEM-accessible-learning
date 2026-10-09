# Yerel Türkçe seslendirme

Uygulama, Docker iç ağında çalışan Piper `tr_TR-dfki-medium` motorunu kullanır.
Motor CPU ile çalışır; ses, kaynak metin ve WAV verisi dış bir TTS sağlayıcısına
gönderilmez. Öğrenci tarayıcısı serbest metin gönderemez: API önce yayımlanmış
okuma planındaki doğrulanmış birimi çözer, yalnız o birimi Piper'a iletir.

Seslendirme sırası şöyledir:

1. Dinleyici çalışması ile onaylanmış, sürüme bağlı kayıt varsa bu WAV kullanılır.
2. Böyle bir kayıt yoksa yerel Piper Türkçe motoru aynı doğrulanmış okuma
   birimini sentezler.
3. Yerel motor geçici olarak kullanılamıyorsa tarayıcıdaki yerel Türkçe ses
   devreye girer. Başka dil veya uzak servis otomatik seçilmez.

Piper sesi, `tr_TR-dfki-medium` model kartındaki CC BY-NC-SA 4.0 veri lisansı
nedeniyle geliştirme ve araştırma kurulumu içindir; ticari/halka açık yayına
otomatik taşınmaz. Yayın için ses/model lisansı, metin hakkı ve dinleyici
doğrulaması ayrı kontrol edilmelidir. Piper'ın Türkçe, ONNX ve yerel HTTP
çalışma biçimi [Piper belgelerinde](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md)
ve [ses model kartında](https://huggingface.co/rhasspy/piper-voices/tree/main/tr/tr_TR/dfki/medium)
belgelenmiştir.

Yüksek kalite hedefi için sonraki aday yerel GPU üzerinde Chatterbox
Multilingual V3'tür. Türkçeyi destekler; fakat bu bilgisayarda GPU yoktur ve
model, Piper'a göre çok daha büyük bir çalışma belleği ister. Chatterbox ile
üretilen ses ancak kaynak-bağlı otomatik kontrol, en az üç dinleyici ve
doğrulanmış ses varlığı manifestinden sonra birinci sıraya alınır. Fine-tuning
yalnız açık model eğitimi rızası olan tek konuşmacı kayıtlarıyla yapılır.

9 Ekim 2026 yerel kurulum doğrulamasında model imaj içine indirildi ve API
üzerinden doğrulanmış demo birimi için 22.050 Hz mono WAV üretildi. TTS
servisinin portu ana makineye yayınlanmaz.
