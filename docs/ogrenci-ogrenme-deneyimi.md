# Öğrenciye gerçek fayda: erişilebilir çalışma döngüsü

## Araştırmadan ürün kararına

- Hatırlama alıştırması, yalnız tekrar okumaya göre gecikmeli öğrenmede yararlı
  olabilir. Bu sonuç kör/Türkçe STEM öğrencileri için doğrudan kanıt değildir;
  pilotta görev başarısı ve öğrenci geri bildirimiyle doğrulanacaktır.
  Kaynak: Karpicke & Blunt (2011), https://pubmed.ncbi.nlm.nih.gov/21252317/.
- Ekran okuyucuların tablo hücresiyle doğru başlık ilişkisini kurabilmesi için
  `caption`, `th` ve uygun `scope`/`headers` gerekir. Kaynak:
  https://www.w3.org/WAI/tutorials/tables/two-headers/.
- Grafiklerde tek kelimelik alternatif metin yeterli değildir; kısa açıklama,
  ayrıntılı betimleme ve mümkünse veriye erişim gerekir. Kaynak:
  https://www.w3.org/WAI/tutorials/images/complex/.
- Durum değişiklikleri odak zorla taşınmadan ekran okuyucuya iletilmelidir.
  Kaynak: https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA22.html.
- VLM'ler tablo/formül/grafik tanımaya adaydır ama genel benchmark üstünlüğü
  bu projedeki Türkçe matematik sembol doğruluğunu kanıtlamaz. Kaynak:
  https://arxiv.org/abs/2510.14528. Üretken açıklamaların yanlış olma riski
  için ayrıca https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958388.

## Bu sürümde uygulanan dikey dilim

1. Yalnız yayımlanmış `reading-plan` birimleri isteğe bağlı “Kendini yokla”
   akışına girer. Önce birim gizlenir; öğrenci hazır olunca doğrulanmış kaynak
   metni açar, “Hatırladım” veya “Tekrar çalışacağım” seçer. Sistem bilgi
   sorusu, yanıt veya başarı puanı uydurmaz.
2. Tekrar aralığı basit ve denetlenebilirdir: hatırlamada 1, 3, 7, sonra 14
   gün; hatırlayamamada hemen tekrar listesi. Bu aralıklar pedagojik optimum
   iddiası değildir, pilotta ayarlanacak ürün varsayımıdır.
3. Yerel depolamada yalnız birim kimliği, deneme sayısı ve sonraki tekrar
   zamanı tutulur. Anahtar belge kimliği ve `published_revision` içerir;
   yayımlanan yeni sürüm eski ilerlemeyi yeniden kullanmaz. İçerik, ses,
   öğrenci yanıtı veya kimlik sunucuya gönderilmez. Paylaşılan cihaz için
   silme düğmesi vardır. Hesaplar arasında senkronizasyon yoktur.
4. Yayımlanmış basit tablolarda her hücre odaklanabilir düğmedir; satır/sütun
   ve yayımlanmış sütun başlığı ekran okuyucu etiketine eklenir. Öğrenci bir
   önceki/sonraki hücreye geçebilir veya seçili hücreyi cihazdaki Türkçe sesle
   dinleyebilir. Bilinen küme sembolleri sözcüğe çevrilir; bilinmeyen işarete
   uygulama TTS'i anlam uydurmaz; öğretmen istisna hücreye doğrulanmış Türkçe
   okunuş yazabilir. Hücre metni değişirse bu okunuş temizlenir. Bu,
   matematiksel Braille veya bütün
   notasyonlar için doğruluk iddiası değildir. Çok düzeyli veya birleşik
   başlıklı tablo için bu basit görünüm yeterli sayılmaz.
5. Öğretmenin kaynak PDF'yle karşılaştırıp Türkçe okunuşunu onayladığı ve
   bağımsız onaylayıcının yayımladığı MathML'nin desteklenen alt kümesi
   deterministik Türkçe okunuşa derlenip mevcut okuma planına eklenir.
   Desteklenmeyen yapı gizlice TTS'e verilmez; eksik birim olarak bildirilir.
   Bu akış hâlen kaynakla insan karşılaştırması ve öğrenci görev testi ister.

## En yüksek etkili sonraki işler ve kabul kapıları

| Öncelik | İş | Ölçülebilir çıkış | Güvenlik kapısı |
| --- | --- | --- | --- |
| P0 | Gerçek PDF'de tür yönlendirme ve metin otomatik kalite | Sayfa/blok türleri için private Gold karışıklık matrisi; doğrulanmış doğrudan metnin yayımlanabilir oranı ve öğretmen dakika/sayfa | Sembol, formül, tablo, grafik şüpheliyse otomatik yayımlama yok |
| P0 | Kör öğrenciyle 5–8 görevlik kullanılabilirlik pilotu | Metin bulma, tablo başlığına ulaşma, kaldığı yere dönme, tekrar çalışması: tamamlama, süre, yardım/hata sayısı ve SUS yerine kısa anlaşılabilirlik görüşmesi | Başarısız görevler release engeli; yalnız otomatik axe testi yeterli değil |
| P1 | Doğrulanmış alıştırma modeli | Soru/seçenek/çözüm ayrımı, göster-gizle ve öğretmen onaylı cevap; Gold'da kritik ifade kaybı sıfır | Çıkarımdan uydurulmuş doğru cevap yok |
| P1 | Grafik ve formülün çok katmanlı açıklaması | Kaynağa bağlı veri/MathML, kısa + ayrıntılı okuma, kritik eksen/operatör Gold; kör öğrenciyle anlama görevi | Kaynaksız yorum ve belirsiz değer seslendirilmez |
| P1 | Yayımlanmış içerikte kaynak-bağlı soru-cevap aday araştırması | Kapalı Gold'da kaynak gösterme, cevapsız kalma, çelişki/hallüsinasyon oranı; kullanıcı görev testi | LLM çıktısı doğrulanmadan ders gerçeği veya cevap anahtarı olamaz |
| P2 | Yerel Türkçe TTS/ince ayar | Mevcut sistem sesiyle kör dinleyici karşılaştırması: matematik anlaşılırlığı, gecikme, CPU/RAM, çevrimdışı kullanım | V3 puanlamasında 2 aday yalnız düz metin için dinleyici testine giriş hakkı kazandı; ses kalitesi geçmeden dağıtım yok |
| P2 | Güvenli cihazlar arası ilerleme | Açık rıza, kimlik/erişim kontrolü, dışa aktarma ve silme | Yerel geçmiş varsayılan; belgesiz analitik/telemetri yok |

### Mimari ilke

PDF metin katmanı ve vektör geometri önce; CV/OCR/VLM yalnız ilgili bölge
için aday üretir. Her türün ayrı şeması, kaynak koordinatı ve Gold metriği
vardır. LLM, varsa, doğrulanmış bloklara bağlı arama/açıklama adayı üretir;
kritik matematiksel bilgi veya cevap anahtarını tek başına yayımlamaz.
Ses ve Braille de aynı yayımlanmış kanonik içerikten türetilir. Öğretmen
her bloğu baştan yazmaz; düşük güvenli istisnaları inceler. Bu yaklaşımın
başarısı model sayısıyla değil, bağımsız kaynak doğruluğu, görev başarısı,
öğretmen yükü ve öğrencinin öğrenme etkisiyle ölçülür.

### Pilot protokolü

Geliştirme ve Gold sayfaları ayrılır. Model/kurallar Gold'a bakılarak
ayarlanmaz. En azından metin, sembol, tablo, formül, grafik ve alıştırma
ayrı raporlanır; örnek sayısı küçükse başarı yüzdesi yerine belirsizlik
bildirilir. Önce sentetik uçtan uca test, sonra private kaynak karşılaştırması,
son olarak öğrencinin kendi ekran okuyucusu ve cihazıyla gözlenen görev testi
yapılır. Pilot katılımcısının ses/öğrenme verisi açık rıza olmadan kaydedilmez.
