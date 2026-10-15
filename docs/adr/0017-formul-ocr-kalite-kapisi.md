# 0017 — Bütün formül OCR kalite kapısı

## Karar

Matematik formülleri sıradan paragraf OCR çıktısı olarak yayınlanmayacaktır.
İşlem hattı şu bağımsız aşamalardan oluşur:

`PDF sayfası → formül bölgesi → tek ifade OCR → normal gösterim → MathML → Türkçe okunuş → Gold + öğretmen denetimi → yayın`

Formül OCR adayı yalnız kaynak checksum'ı, sayfa ve dikdörtgeni kayıtlı private
crop'ları görür. Beklenen gösterim ve Türkçe okunuş ayrı private Gold dosyasında
kalır. Böylece aday model sonucu ezberleyemez ve gerçek formül doğruluğu ölçülür.

## Kalite kapısı

Bir aday, yalnız doğrulama kümesinde aşağıdaki koşulların tümünü sağlarsa
öğretmene öneri üretebilir:

- formül bölgesi bulma geri çağırımı en az `%95`;
- birebir normal gösterim doğruluğu en az `%98`;
- kesir/bölme, kök ve derece, üs/alt indis, ilişki işareti, sayı ve birim içeren
  kritik ifadelerde `%100` doğruluk.

Bu kapı geçilse dahi öğrenciye otomatik yayın yoktur. Her formül kaynak
koordinatında öğretmen tarafından onaylanır. Kapının altında kalan adaylar da
çalıştırılır ve kaynak görseliyle birlikte **deneysel öğretmen incelemesi**
kuyruğuna alınabilir; yalnız yüksek güven/otomatik öneri etiketi alamazlar.
Model güven puanı yayın kararı yerine geçmez.

## Sonuç

Ham PDF metin katmanındaki bölünmüş veya bozuk formüller öğrenciye ulaşmaz.
Özellikle şekil yanındaki ölçü birimi, yakındaki şekilden tahmin edilmez; bağlam
etiketi (ör. `AB kenarı`) öğretmen tarafından açıkça seçilmeden sesli okunuşa
eklenmez.
