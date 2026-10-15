# Öğrenci sesli komutları: açık mikrofon, güvenli yönlendirme

## Karar

Öğrencinin bulunduğu ekrana göre geçerli kısa Türkçe komutlar belirlenir. Aynı
`VoiceCommandPanel`, kütüphane, tarih kitabı, yayımlanmış belge okuyucusu,
soru bankası ve yazma alanında kullanılır. `voice_commands.ts` konuşmayı dar,
deterministik bir niyet kümesine ayrıştırır. Her ekran yalnız kendi izin verdiği
niyetleri çalıştırır. Anlaşılmayan veya o ekranda geçersiz komut hiçbir işlem
yapmaz. Sesle cevap gönderme, onay verme, kayıt silme veya içerik yayımlama yoktur.

Mikrofon sürekli açık değildir: kullanıcı tek komutluk dinlemeyi başlatır,
tarayıcının izin denetimi geçerlidir. Varsayılan yalnız cihaz içi `tr-TR`
tanımadır; destek ve dil paketi `SpeechRecognition.available()` ile kontrol edilir.
Dil paketi varsa kullanıcı ayrıca kurabilir. Tarayıcı bu garantiyi veremiyorsa
mikrofon otomatik olarak uzak tanımaya geçmez. Tarayıcı sağlayıcısının tanıması
ancak kullanıcı olası uzak ses işleme uyarısını açıkça kabul ederse kullanılır.
Konuşma metni uygulama API'sine gönderilmez veya saklanmaz.

Her ekranda aynı komutlar yazılarak da uygulanabilir. Bu, mikrofon izni,
tarayıcı desteği, gürültü veya konuşma farklılığı nedeniyle ses tanımanın
başarısız olduğu durumda tam bir geri dönüş yoludur. Standart butonlar ve ekran
okuyucu gezintisi korunur. Ses çıkışı mevcut doğrulanmış içerik/TTS hattından
gelir; ses tanıma sonucu hiçbir zaman kaynak içerik gibi kabul edilmez.

## Geçerli görev örnekleri

| Bağlam | Komut | Eylem |
| --- | --- | --- |
| Kütüphane | “tarih kitabını aç” | Tarih okuyucusuna geç |
| Kütüphane | “soru bankasını aç” | Onaylı soru alanına geç |
| Tarih/okuyucu | “sonraki sayfa”, “sayfa kırk iki” | Sayfa sınırlarını denetleyerek geç |
| Tarih/okuyucu | “sonraki bölüm”, “seçili bölümü oku” | Bölüm odağını değiştir/dinlet |
| Soru | “sonraki soru”, “şıkları göster”, “şık A’yı oku” | Soruya geç, şıkları aç veya yalnız şıkkı dinlet; cevap işaretlenmez |
| Yazma | “yazı alanına geç”, “yazdığımı oku” | Odağı taşı veya kısa yazıyı yerel sesle oku |

## Sınırlar

Tarayıcıların cihaz içi Türkçe tanıma desteği ve dil paketi mevcudiyeti aynı
değildir. Varsayılanın her cihazda mikrofonla çalışacağı iddia edilmez. Ekranda
tanıma modu, dinleme durumu, algılanan komut ve hata açıklaması görünür.
Tarayıcı sağlayıcısı seçeneği kullanılırsa sesin uzak sunucuya gitme olasılığı
vardır; sağlayıcının veri saklama davranışı uygulama tarafından denetlenemez.
Bu nedenle gerçek cihazlarda Türkçe aksan, gürültü ve ekran okuyucuyla eşzamanlı
çalışma kullanıcı testi gerektirir. Sesli komut sistemi öğretmen onay kapısını
ve soru bankasının yayımlanma durumunu değiştirmez.
