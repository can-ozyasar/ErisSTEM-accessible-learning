# ErişSTEM: okuma aracından etkin öğrenme koçuna

9 Ekim 2026 güncellemesi: öğrenci çalışma rotası artık modüler öğrenme
atölyesini açar. Aşağıdaki `sets-grade9-v1` notları ilk API dilimini anlatır;
bu API korunur. Yeni modüller, ayrı ön bilgi/rehberli/aktarım/gecikmeli görevler
ve yardım kayıtları [atölye uygulama notunda](ogrenme-atolyesi-uygulama.md)
tanımlanır. Gerçek kullanıcı ve uzman doğrulaması hâlâ beklenmektedir.

## Ürün kararı

Fikir değiştirilmez; başarı tanımı değiştirilir. PDF'yi seslendirmek bir erişim
önkoşuludur, öğrenme sonucu değildir. Öğrenci doğrulanmış kavramı dinlemeli,
küçük bir görevi bağımsız çözmeli, yanlışta cevabı görmeden uygun ipucu almalı,
sonra benzer soruyu yardımsız çözebilmelidir. Öğretmen içerik istisnasını
denetler; her öğrencinin her cevabını elle puanlamaz.

İlk dilim 9. sınıf kümeler için sentetik alıştırmalardır. Kitap OCR'sinden soru
veya cevap otomatik yayımlanmaz. Görsel/vektör-native kaynaklar, öğretmen
onayı ve Gold denetiminden sonra aynı kanonik soru sözleşmesine taşınabilir.

## Neden bu akış?

- Türkiye'deki lise bağlamında yapılan randomize çalışma, genel amaçlı bir
  GPT yardımcısının yardım sırasında performansı yükseltirken yardımsız
  sınav performansını düşürebildiğini; öğretmen tasarımlı ipucu akışının bu
  zararı sınırladığını gösterdi. Bu nedenle doğru yanıtı veren açık uçlu
  sohbet ilk sürümün merkezinde değildir.
  Kaynak: https://pmc.ncbi.nlm.nih.gov/articles/PMC12232635/
- Erişilebilir matematik öğretiminde karmaşık görevi küçük alt görevlere
  ayıran bir yaklaşım da araştırılmıştır. Tek sonuç alanı ilk dilimdir;
  sonraki dilimde işlem adımları ayrı değerlendirilebilir.
  Kaynak: https://pubmed.ncbi.nlm.nih.gov/28602433/
- Etiketli yanıt alanı, biçim talimatı ve durum mesajı, yardımcı teknoloji
  için temel tasarım kararıdır.
  Kaynaklar: https://www.w3.org/WAI/WCAG21/Understanding/labels-or-instructions
  ve https://www.w3.org/WAI/tutorials/forms/notifications/

## Teknik sınırlar

`sets-grade9-v1` bankası sunucudadır. İstemciye soru, Türkçe konuşma metni,
kaynak türü ve yanıt biçimi gider; beklenen sonuç ve ipuçları gönderilmez.
Tam sayı kümesi yalnız sınırlı bir sözdizimiyle ayrıştırılır; `eval`, LLM veya
OCR ile puanlama yapılmaz. Yinelenen eleman ve bozuk giriş ayrı biçim hatasıdır.
Doğru/yanlış yanıtı sunucu diske yazılmaz. Tamamlanma yalnız cihazda bankanın
sürüm anahtarıyla saklanır. Bu, sınav güvenliği veya kimlik doğrulamalı not
sistemi değildir; istemci yerel verisini silebilir.

Tarayıcı seslendirmesi yalnız yerel Türkçe ses mevcutsa açılır. Matematiksel
işlem işaretinin Türkçe sözcük karşılığı önceden yazılmıştır. Cihazın ekran
okuyucusu tüm soru ve geribildirim metnine erişebilir; uygulama TalkBack veya
VoiceOver hareketlerini taklit etmez. Braille girişi cihazın klavyesine
dayanır; matematiksel Braille çıktısı henüz bu modülde yoktur.

## Başarı kapısı ve sonraki işler

1. NVDA+Firefox, TalkBack+Chrome ve VoiceOver+Safari üzerinde kör/az gören
   öğrencilerle şu görevleri gerçek cihazda gözleyin: menüden alıştırmaya
   girme, soru/işlemi anlama, Braille veya standart klavyeyle yanıt girme,
   ipucu bulma, yardımsız benzer soruyu çözme, geri dönme. Kritik odak veya
   yanlış okunuş hatası varsa yayın alanını genişletmeyin.
2. Önceden belirlenmiş ölçütleri toplayın: ilk denemede doğruluk, ipucu
   sonrası doğruluk, 24 saat sonra yardımsız benzer soruda doğruluk,
   görev tamamlama süresi, öğretmen müdahale sayısı ve kritik erişilebilirlik
   hatası. Değerlendirmede öğrencinin özel yanıt metnini merkezi loga
   almayın; rızalı çalışma için ayrı anonim olay şeması tasarlayın.
3. Formül/tablo/grafik için ayrı, kaynak-bağlı alıştırma sözleşmeleri ve
   puanlayıcılar geliştirin. Matematiksel açıklamada LLM ancak doğrulanmış
   bilgi grafiğinden sınırlı ipucu *adayı* üretir; cevap ve kritik işlemler
   deterministik motor/Gold ile denetlenmeden öğrenciye çıkmaz.
4. Yerel/kuantize model ve özel TTS yalnız gerçek görev ölçümünde anlamlı
   iyileşme gösterirse eklenir. Baseline ile aynı soru bankası, gecikme,
   donanım, hata ve yardımsız öğrenme metriği karşılaştırılır. Sırf model
   kullanılmış olması ürün başarısı sayılmaz.

Bu ilk dilim, tüm müfredatın veya kör kullanıcı testlerinin bittiği iddiası
değildir. Güvenilir alıştırma döngüsünü üretimde kullanılabilecek mimariyle
kanıtlayan sınırlı bir prototiptir.
