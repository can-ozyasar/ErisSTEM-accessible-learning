# Mobil öğrenci arayüzü ve Braille giriş sözleşmesi

Öğrenci uygulaması TalkBack/VoiceOver'ın yerine geçen bir ekran okuyucu
değildir. Telefonun sağ/sol kaydırma, dokunarak odaklama ve çift dokunarak
etkinleştirme davranışlarını işletim sistemi yönetir. Bu yüzden uygulama
bu hareketleri `touchstart`/`touchend` ile yakalamaz veya `preventDefault`
ile engellemez. Menü seçenekleri gerçek HTML düğmesi, arama/yazı alanları
gerçek `input`/`textarea`, ders başlıkları gerçek başlık ve tablolar gerçek
`table` öğeleridir. Eşdeğer işlemler görünür düğmelerle yapılır.

## Gezinme

- Kütüphane açılış ekranıdır; yayımlanmamış belgeler listelenmez.
- Ders düğmesi okuyucuya gider. Okuyucuda görünür **Kütüphaneye dön**
  düğmesi vardır. Tarayıcı/telefon geri hareketi History API üzerinden aynı
  ekrana döner; doğrudan açılmış ders bağlantısında uygulama içi geri
  kütüphaneye gider.
- Her ekran değişiminde ana başlık odaklanır. Klavyede Escape, yazı alanı
  düzenlenmiyorsa geri döner;
  okuyucuda Alt+H/F/R ve Alt+sol/sağ yardımcı kısayollardır. Bunlar
  TalkBack/VoiceOver hareketlerinin yerine geçmez.
- 48 piksel veya daha büyük düğme hedefleri, görünür odak, mobil tek sütun,
  yüksek kontrast ve azaltılmış hareket ayarları desteklenir.

## Braille ile yazma

Arama ve yazı alanı standart düzenlenebilir alanlardır. Kullanıcı bu alana
ekran okuyucuyla odaklanıp çift dokunduktan sonra cihazının desteklediği
Braille giriş yöntemini/klavyesini seçebilir. Web uygulaması işletim sistemi
klavyesini zorla değiştiremez ve kendi altı parmak hareket taklidini kurmaz;
cihaz/dil desteği değişebilir. Yazı alanı yalnız oturum içi taslaktır:
sunucuya gönderilmez, kalıcı kaydedilmez, sayfa yenilenince kaybolur.
Kopyalama ve temizleme işlemleri açık düğmelerdir. Gelecekte ödev/mesaj
yazımı eklendiğinde veri saklama, onay ve hata kurtarma ayrıca tasarlanacaktır.

Okuyucudaki Liblouis çıktısı doğrulanmış edebî metnin Braille hücreleridir;
bu, matematik Braille girişi veya cihazın yerel Braille klavyesinin yerini
tutmaz.

## Release öncesi insan testleri

En az TalkBack+Chrome/Android ve VoiceOver+Safari/iPhone üzerinde görme
engelli kullanıcılarla şu görevler tamamlanmalıdır: menüde ileri/geri
gezme, dersi açma, okuyucudan geri dönme, sesli okumayı durdurma, Braille
klavyeyle arama/yazma, kopyalama, ekran döndürme ve büyük yazı boyutunda
odak sırasını kontrol etme. Otomatik test veya masaüstü Chrome görüntüsü
bu kabulün yerine geçmez.
