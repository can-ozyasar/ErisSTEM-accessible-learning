# Tarih için kaynak-bağlı erişilebilir öğrenme mimarisi

## Karar ve kapsam

Ana ders kaynağı: MEB 2026, 9. sınıf Tarih Ders Kitabı, 263 PDF sayfası.
Kaynak: https://tymm.meb.gov.tr/kitap/43/tarih-9.sinif-ders-kitabi
Yerel dosyanın SHA-256 değeri: `a7bd70d3ddf7ead61f201b10a35079a2d0f87088f5e61bab830cc33a515335fe`.
Soru bankası ayrı bir kitap türüdür; kullanıcı PDF'si henüz sağlanmadığı için soru bankası içeriği üretilmez.

Matematik OCR hattı tarih kitabına zorlanmaz. PDF metin katmanı ve geometrisi ilk kanıt katmanıdır.
Her bölgenin sayfa, kutu, tür, okuma sırası ve metni saklanır. Görsel, metin ve bağlantı
ayrı bölgelerdir. Sayfadaki konum ve aynı satır/sütun ilişkisi korunur. Özellikle 42. sayfada
haritanın sağındaki dar metin ile altındaki geniş metin PDF'de tek bloktur; satır koordinatları
ile ayrılır. 40. sayfada iki ayrı görselin alt yazısı yatay örtüşmeye göre ilişkilendirilir.

## İçerik türleri ve güven sınırı

- Ders kitabı düz metni: PDF metin katmanından alınır, seçili alan bazında yerel TTS ile okunur.
- Görsel veya harita: PDF sayfasında seçilebilir; alt yazı varsa aynen okunur. Alt yazı,
  ayrıntılı görsel betimlemesi değildir. Betimleme doğrulanana kadar boş kalır.
- Dış bağlantı/QR: PDF URI bağlantısı varsa ayrı bölgedir; QR'ın içeriği tahmin edilmez.
- Soru: Kaynaktaki gerçek soru metnidir. Çalışma modu öğrenci yanıtını otomatik puanlamaz;
  aynı sayfadaki kaynak paragraflarına yönlendirir. Yanıt taslağı sunucuya gönderilmez.
- Soru bankası: sağlandığında ders kitabından ayrı `question_bank` kaynağı, soru kökü,
  seçenekler, görsel/harita, alt yazı, çözüm ve kaynak koordinatlarıyla işlenecek.

## Sonraki kalite kapıları

1. Kullanıcı soru bankası PDF'sini sağlar; lisans ve okunabilir PDF/OCR durumu doğrulanır.
2. 40–43. sayfalardan başlayan, sonra tüm bölüm türlerine yayılan elle etiketlenmiş altın
   örnekler hazırlanır: bölge sınırları, okuma sırası, görsel-alt yazı/kaynak-soru ilişkisi.
3. Düzen modeli/çok kipli OCR yalnız PDF katmanının başarısız olduğu alanlarda çalışır;
   çıktısı sayfa görüntüsüyle karşılaştırılır. Sabit bir tek güven eşiği yerine hata türüne göre
   karar verilir; kritik harita betimlemesi ve cevap anahtarı insan doğrulamasından geçer.
4. Haritalar için yer adları, yön/konum, sembol ve lejant, renk/doku, verinin mesajı ayrı
   alanlarda betimlenir. Vizyon modeli önerisi kaynak görüntüsüne bağlanır; doğrulanmadan
   öğrenciye olgu olarak sunulmaz.
5. Sesli soru-cevap için mikrofon izni ve Türkçe konuşma tanıma ayrı, isteğe bağlı katmandır.
   Kaynaklı yanıt ipuçları ve insan tarafından doğrulanmış cevap anahtarı olmadan otomatik
   doğru/yanlış kararı verilmez. Ekran okuyucu/klavye kullanımı mikrofon gerektirmez.
6. Üretim yayını öncesi gerçek kimlik doğrulama/OIDC, telif erişim politikası, görsel
   betimleme editörü, sürümleme ve erişilebilirlik kullanıcı testi gerekir.

## Bugünkü çalışan dilim

Uygulama 263 sayfalık gerçek PDF'yi sayfa bazında açar. Bölge seçimi, Türkçe yerel ses,
görsel-alt yazı ayrımı ve kaynak sorusuyla çalışma mevcuttur. Bu, bütün kitabın görsellerinin
betimlendiği veya bütün sayfaların kalite testinden geçtiği anlamına gelmez.

Tam kitap üzerinde istisnasız geometri taraması yapıldı: 8.423 metin/görsel bölgesi,
771 büyük görsel adayı ve 192 PDF bağlantısı görüldü. 6. PDF sayfası metin/görsel
katmanında boş; 26, 27 ve 263. sayfalar yoğun parçalanma nedeniyle ayrıca incelenmeli.
Bu sayılar doğruluk puanı değil, denetim iş yükü envanteridir.
