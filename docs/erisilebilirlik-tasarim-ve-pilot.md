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

## AYT denemesi için manuel ekran okuyucu kontrolü

Bu kontrol listesi uygulama içi teknik kontrol içindir; katılımcı çalışmasının
veya öğretmen/içerik doğrulamasının yerine geçmez. Otomatik Chromium/axe
sonuçları [özel pilot kabul raporunda](../reports/ayt-private-pilot-acceptance-v1.json)
bulunur. NVDA + Firefox ve TalkBack + Chrome adımları henüz çalıştırılmadıysa
sonuç alanları `bekliyor` bırakılmalıdır.

### Hazırlık

- Denemeyi yerel Docker kurulumu ve gerçek 81 soruluk yerel pilot paketiyle aç.
- NVDA + Firefox için masaüstü; TalkBack + Chrome için Android kullan. Sürüm,
  cihaz, giriş yöntemi ve TTS/ekran okuyucu konuşma ayarını kaydet.
- Önce yalnız klavye/dokunmatik ekran okuyucu hareketleriyle dene; uygulamanın
  isteğe bağlı sesli komutlarını ilk turda kapalı tut.
- Test için bir yanıt seç, sayfayı yenile ve oturumu bitir. Yanlış yanıtlı
  sonuçtan koçluğu aç; ikinci turda kısa bir gerekçe gir. Özel soru/cevap metnini
  gözlem raporuna kopyalama.

### Görevler ve beklenen davranış

| ID | Görev | Beklenen erişilebilir davranış | Sonuç |
|---|---|---|---|
| A1 | Deneme alanını aç ve başlatma onayını tamamla | Başlıklar mantıklı sırada okunur; `Erişilebilir AYT Tarih denemesi`, oturum soru sayısı/süre bilgisi ve `Provayı başlat` bulunur; onay kutusu etiketi anlaşılırdır. | bekliyor |
| A2 | Denemeyi başlat ve ilk soruyu oku | Odak `Soru 1 / 81` başlığına gelir; soru kökü ve `Yanıtınız` grubu erişilebilir; beş seçenek etiketleri ve metinleri birbirinden ayırt edilir. | bekliyor |
| A3 | Bir şık seç, yenile ve kaydın kaldığını doğrula | Seçili radio durumu ekran okuyucu tarafından duyurulur; yenilemeden sonra aynı seçim görünür; doğru yanıt/çözüm sınav sırasında duyurulmaz. | bekliyor |
| A4 | İşaretle, sonraki/önceki soruya git ve süreyi oku | Eylem düğmelerinin amacı açıkça duyurulur; soru başlığı değişir ve yeni soru anlaşılır; kalan süre metin veya `Kalan süreyi seslendir` ile erişilir. | bekliyor |
| A5 | Denemeyi bitir ve yanlış soruda koçluğu başlat | Sonuç başlığına ulaşılır; cevap/çözüm henüz açıklanmaz; `Kaynakla birlikte çöz` eylemi bulunur ve ilk koç mesajı odak/okuma sırasını bozmaz. | bekliyor |
| A6 | Düşünceni yaz ve ikinci ipucunu aç | `Soru hakkındaki düşünceniz` alanı etiketlidir; metin girişinden sonra `Düşüncemi paylaş ve ikinci ipucunu aç` bulunur; izin verilen aşamada kaynak, doğru yanıt ve açıklama erişilebilir biçimde sunulur. | bekliyor |
| A7 | Sınav verisini sil | `Prova verisini sil` eylemi ve onay penceresi anlaşılır; silme tamamlanınca başlangıç durumuna dönülür. | bekliyor |

Her görev için `tamamlandı`, `yardımla tamamlandı`, `başarısız` veya `uygulanmadı`
seçeneklerinden birini ve engelin kısa, kişisel veri içermeyen açıklamasını
kaydet. Bir hata bulunursa tarayıcı/ekran okuyucu sürümü, hangi öğeye odaklanıldığı
ve beklenen/duyulan fark yazılır. Uygulamayı güncelledikten sonra aynı görev
tekrar edilir. A1–A7'nin otomatik testte geçmesi manuel sütunu geçilmiş sayılmaz.

### Koşu kaydı şablonu

```text
Tarih/saat:
Uygulama commit'i:
Ortam: NVDA + Firefox | TalkBack + Chrome
Sürüm/cihaz:
Girdi yöntemi ve konuşma ayarı:
A1–A7 sonuçları:
Bulunan engeller (özel soru/yanıt metni olmadan):
Tekrar test sonucu:
```

Gerçek kullanıcı pilotu ayrıca rıza, güvenli gözlem ve anonim raporlama
protokolüyle yürütülür; bu teknik kontrol kaydı katılımcı araştırma verisi
değildir.
