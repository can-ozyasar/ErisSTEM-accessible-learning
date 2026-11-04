# AYT Tarih kaynak etiketleme kılavuzu

Bu kılavuz özel OGM soru pilotundaki MEB kesitleri içindir. Soru ve kitap
metinleri Git'e yazılmaz. Ajan kararı yalnız ön incelemedir; öğrenci RAG'ı,
graf kenarı, Gold değerlendirme ve QLoRA için insan öğretmen onayı gerekir.

## Karar birimi

Bir etiket, **soru iddiası × kaynak kesiti** çiftine verilir. Soru kökü,
şıkların ayırt edici iddiaları ve istenen ilişki (kişi–olay, tarih–olay,
yer–olay, kronoloji, neden–sonuç, özellik veya karşıtlık) ayrı okunur.
Kaynağın konuyla ilgili olması tek başına yeterli değildir.

| Ön inceleme etiketi | Gereken durum |
| --- | --- |
| `direct` | Kaynaktaki kısa birebir alıntı, sorulan özne–ilişki–nesne bağını açıkça kurar. Hangi iddiayı desteklediği gerekçede belirtilir. |
| `partial` | Aynı olayın bağlamını veya zincirin yalnız bir halkasını verir; ayırt edici ilişkiyi tek başına kanıtlamaz. |
| `irrelevant` | Aynı dönem veya ad geçse bile sorunun ilişki ve şık ayırımı için işe yaramaz. |
| `uncertain` | OCR, kırpım, zamir bağlamı veya tarihsel anlam belirsizdir; PDF sayfasında yeniden bakılması gerekir. |

“Hangisi **değildir**?” sorusunda kaynakta bir özelliğin geçmemesi, o
özelliğin bulunmadığını kanıtlamaz. Doğrudan olumsuzluk veya kaynaklı,
tamamlayıcı bir karşıtlık gerekir. İki sayfadaki tarihleri sıralamak mümkün
olabilir; bu sıralama kendiliğinden neden–sonuç ilişkisi kurmaz.

## Denetim sırası

1. PDF checksum'ı, sayfa, koordinat ve kesit metni otomatik karşılaştırılır.
   Bu yalnız **konum doğrulamasıdır**.
2. Soru OCR'ında kök, olumsuzluk, tarih, kişi ve şıklar okunur. Şüpheli
   OCR sorusu kanıt değerlendirmesine alınmaz.
3. Kesitteki birebir kısa alıntı ve sorulan ilişki ayrı yazılır. Aynı
   başlık/kişi/dönem eşleşmesi doğrudan kanıt sayılmaz.
4. İlk adaylarda kaynak yoksa diğer bölüm ve sınıf kitapları, ardından
   `manual_review` statülü parçalar **yalnız private PDF keşfi** için aranır.
   Bu parçalar otomatik olarak onaylı kaynak havuzuna aktarılmaz.
5. Ajan çıktısında her `direct` yeniden okunur; farklı konu ve soru türlerinden
   örneklemde `partial` ve `irrelevant` kararları da ters yönden denetlenir.
   Genel/tekrarlı gerekçe bir kalite bulgusudur; Gold etiketi değildir.
6. İnsan öğretmen tüm gerekli iddiaların kaynakla karşılandığını ve PDF
   kırpımlarını doğrularsa Gold kaydı açılır. Kaynak bulunamayan soru için
   çekimserlik açıkça kaydedilir. Eksik kanıtı cevap anahtarıyla tamamlamayız.

## Ürün sınırı ve ölçüm

Gold şablonunda `reviewed`, `crop_checked` ve `coverage_complete` alanları
yalnız gerçek insan öğretmen incelemesi sonunda işaretlenir;
`reviewer_kind=human_teacher` zorunludur. Ajanın PDF ve alıntı kontrollerinden
geçmesi bu alanları değiştirmez. Kaynağı olmayan veya çelişkili soru öğrenci
koçunda güvenli geri dönüş alır.

Deney raporu ayrı ayrı soru düzeyinde `Hit@3`, kanıt düzeyinde `Recall@3`,
tam demet, yanlış kanıt, belirsiz etiket, doğru çekimserlik ve p50/p95 süreyi
gösterir. Ajan ön incelemesinin yüzdeleri ürün doğruluğu veya CV başarım
metriği diye sunulmaz.
