# ErişSTEM erişilebilir arayüz kararı ve okul pilotu

## Kullanım ilkeleri

Birincil akış, ekranı hiç görmeyen öğrencinin ekran okuyucu ve klavye ile
başlayıp kitap bölümü veya soruya ulaşabilmesi üzerine kuruludur. Aynı akış,
az gören, renk ayırt etmekte zorlanan veya küçük hedefleri seçmekte zorlanan
öğrenciler için de çalışmalıdır. Tek bir renk, hareket, ses veya kaydırma
hareketi bir işlevi kullanmanın tek yolu olamaz.

- Giriş ve öğrenci alanları tek etkin kart gösterir. Sağ/sol kaydırma yanında
  görünür önceki/sonraki düğmeleri ve ok tuşları vardır. Etkin kart değişimi
  ekran okuyucuya canlı metinle, isteğe bağlı sesli keşifte yerel TTS ile
  duyurulur.
- Bağlantı ve düğmeler doğal tarayıcı davranışıyla çalışır. Uygulama ikinci
  bir dokunma zorunluluğu koymaz; telefon ekran okuyucusunun kendi çift
  dokunma hareketi korunur.
- Soru yüklenince odak soru başlığına taşınır. Şık seçimi işaret, kalın sınır
  ve “Seçildi” metniyle anlaşılır. Destekçi yanıtı görünür metnin aynısı
  olarak seslendirilir; yanıt yeniden üretilmez.
- Sesli keşif kullanıcının açık eylemiyle başlar. Metin ve standart ekran
  okuyucu erişimi ses hizmetine bağlı değildir. Durumlar metinle de sunulur.
- Yazı boyutu, yüksek kontrast ve hareket azaltma tercihleri bütün ekranlarda
  kullanılabilir ve bu tarayıcıda saklanır.

Bu kararlar W3C'nin [farklı görme ihtiyaçları](https://www.w3.org/WAI/people-use-web/abilities-barriers/visual/),
[kaydırmalı arayüz örüntüsü](https://www.w3.org/WAI/ARIA/apg/patterns/carousel/),
[renk dışında işaret kullanımı](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html),
[yeniden akış](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html),
[durum mesajları](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
ve [hedef boyutu](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)
rehberlerine göre seçildi.

## Okul pilotunda sınanacak görevler

Her katılımcıya yön tarif etmeden şu görevler verilir. Öğretmen veya gözlemci
yardımı, yanlış etkinleştirmeleri, tamamlanma süresini ve öğrencinin kendi
ifadesiyle zorlandığı noktaları kaydeder. Katılımcının tercih ettiği ekran
okuyucu, büyütme ve giriş yöntemi korunur.

| Görev | Beklenen bağımsız sonuç |
|---|---|
| Girişten öğrenci alanına geç | Alanı bulur ve açar; beklenmedik bir sayfa açılmaz |
| Tarih kitabına ulaş ve bir bölümü dinle | Bölümü seçer, okumayı başlatır ve durdurur |
| Soru bankasında konu ve soru seç | Etkin konu/soruyu anlayarak değiştirir |
| Bir şık seç ve desteği aç | Seçiminin kaydedildiğini anlar; cevabı doğrudan görmeden ipucu alır |
| Destekçi yanıtını dinle ve sonraki soruya geç | Görünen yanıtla aynı sesi duyar; yeni soru başlığını fark eder |
| Yazıyı büyüt ve yüksek kontrastı aç | Ayarı bulur, uygular ve sayfayı yatay kaydırmadan kullanır |
| Öğretmen alanından soru denetimine geç | Birincil öğretmen görevini bulur ve açar |

Önerilen deneme koşulları: klavye ve ekran okuyucu, telefon ekran okuyucusu,
%200 metin büyütme, yüksek kontrast ve yalnız klavye. Sınıf ortamındaki ses
düzeyi, kulaklık ve cihaz politikaları da gözlenir. Sesli keşif ile ekran
okuyucunun aynı anda konuşmasının yorucu olup olmadığı özellikle sorulur.

## Kabul ve raporlama

Bir görev için “tamamlandı” ancak katılımcı hedefe ekrandaki yönlendirme ve
kendi yardımcı teknolojisiyle ulaştıysa işaretlenir. Yardım isteyen,
yanlış sayfaya giden veya odak kaybolduğu için yeniden başlayan denemeler
ayrı kaydedilir. Sonuçlar katılımcı sayısı, cihaz, yardımcı teknoloji ve görev
bazında verilir; küçük pilot sonuçları genelleştirilmez.

Otomatik axe taraması ve tarayıcı testleri yalnız teknik engellerin bir
bölümünü yakalar. Okul kullanımına hazır olma kararı için, kullanıcılarla
değerlendirme ve standart denetimi birlikte yapılmalıdır; bu yaklaşım
[W3C'nin kullanıcıları değerlendirmeye katma rehberi](https://www.w3.org/WAI/test-evaluate/involving-users/)
ile uyumludur.
