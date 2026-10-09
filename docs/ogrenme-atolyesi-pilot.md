# Öğrenme atölyesi kullanıcı pilotu

Durum: oturum hazırlığı; görüşme yapılmadı ve katılımcı verisi yok.
Araştırma temeli [kullanıcı anlayışı belgesinde](kullanici-anlayisi-ve-ogrenme-tasarimi.md),
uygulanan akış [uygulama notunda](ogrenme-atolyesi-uygulama.md) açıklanır.

## Amaç ve katılımcı seçimi

İlk tur, erişim ve temsil sorunlarını keşfetmek içindir. 6–8 yetişkin kullanıcı
ve 2–3 eğitim/erişilebilirlik uzmanı önerilir; bu sayı etkiyi kanıtlayan bir
istatistiksel örneklem değildir. Farklı görme deneyimleri, konu bilgileri ve
metin/ses/Braille araçları kapsanır. İnsanlar yalnız görme geçmişleriyle
gruplandırılmaz. Çocuk katılımı ayrı uygun rıza ve kurum süreci gerektirir.

## Katılımcıya okunabilecek oturum açıklaması

“ErişSTEM'in öğrenme atölyesini geliştiriyoruz. Bu çalışma sizin becerinizi
puanlamak için değil, uygulamada zorlanılan yerleri bulmak için yapılıyor.
Kendi cihazınızı ve alışık olduğunuz erişim araçlarını kullanabilirsiniz.
Bir soruyu geçebilir, mola verebilir veya katılımı sonlandırabilirsiniz.
Uygulamanın size yardım ettiği ve etmediği anları anlamak istiyoruz.
Ses veya ekran kaydı yalnız ayrıca kabul ederseniz yapılacak. Cevaplarınız
genel uygulama loguna kaydedilmiyor; bu tarayıcıda sınırlı çalışma geçmişi
tutuluyor ve silinebiliyor.”

Oturum öncesi amaç, kayıt seçimi, paylaşılacak anonim gözlemler, saklama süresi
ve geri çekme yöntemi açıkça anlaşılır. İsim/iletişim bilgileri görev gözlem
dosyasına eklenmez. Üniversitede araştırma olarak yürütülecekse ilgili etik ve
kurum süreci tamamlanır; bu metin o sürecin yerine geçmez.

## Görevler

| Görev | Gözlenecek davranış | Başarısızlık örneği |
| --- | --- | --- |
| Konuyu aç | Kütüphaneden atölyeye, oradan seçtiği konuya gider. | Menü veya konu düğmesi bulunamıyor. |
| Ön bilgi sorusu | Soru ve tüm seçeneklere erişir; yanıtlar veya geçer. | Yanıt girişi sorudan ayrılamıyor. |
| Tercih değiştir | Ayrıntılı açıklama veya büyük metin seçer. | Ayar değişimi odağı kaybettiriyor. |
| Kavramı keşfet | Kısa, ayrıntılı ve isteğe bağlı nesne yönergesini ayırır. | Fiziksel modelin özellikleri kavramın özellikleri sanılıyor. |
| Kümelerde giriş | Örnek biçimi izleyip bir küme yazar. | Biçim hatası matematik hatası sanılıyor. |
| Yanlışta yardım | İpucunu bulur ve ilişkiyi yeniden inceler. | İpucu cevabı doğrudan veriyor veya anlaşılmıyor. |
| Yardımsız görev | Yeni soruyu uygulama açıklaması almadan yanıtlar. | İlk yanıt sonrası geri bildirimle sonuç değiştiriliyor. |
| Yeniden aç | Sayfayı yenileyip aynı konuya geri döner. | İlerleme kayboluyor veya eski yanıtın saklandığı sanılıyor. |
| Sonucu incele | İlk yanıt, yardım ve geçilen soru ayrımını açıklar. | Tamamlanma, öğrenme garantisi sanılıyor. |
| Kaydı sil | Paylaşılan cihaz için atölye geçmişini siler. | Silme kapsamı anlaşılamıyor. |

Soruları çözmeyi zorunlu tutmayın; kullanıcı “Bu soruyu geç” seçeneğini kullanabilir.
Ses dinlerken eşzamanlı düşünmesini anlatması görevini bozuyorsa görüşme görev
sonunda yapılır. Araştırmacı yardım verdiğinde bunu ayrıca kaydeder; cihaz kaydı
bu dış yardımı kendiliğinden bilemez.

## Anonim gözlem şablonu

Her gözlem için şu alanlar yeterlidir; ham yanıt veya tanı istenmez:

```json
{
  "study_id": "learning-discovery-v1",
  "participant_code": "P01",
  "module_id": "circle",
  "module_version": "circle-learning-v1",
  "task_id": "explore-concept",
  "device_and_access_tool": "katılımcının izin verdiği genel araç bilgisi",
  "result": "completed_without_researcher_help",
  "researcher_help_count": 0,
  "issue_category": null,
  "severity": null,
  "observation": "kimlik veya ham cevap içermeyen davranış gözlemi"
}
```

Sonuç seçenekleri: `completed_without_researcher_help`, `completed_with_help`,
`not_completed`, `participant_skipped`. Sorun türleri: `access`,
`representation`, `concept`, `input_format`, `source_error`, `uncertain`.
`participant_skipped` tercihi otomatik başarısızlık sayılmaz; nedeni kişi
paylaşmak isterse alınır. “Kavram” etiketi tek yanlış cevaptan çıkarılmaz.
Dosyalar rızalı araştırmanın private alanında tutulur; gerçek kayıtlar Git'e eklenmez.

## Öğrenme etkisi için ayrı tur

Kullanılabilirlik sorunları giderildikten sonra uzman eşleştirilmiş görevlerle
başlangıç → çalışma → yeni yardımsız soru → 24–48 saat sonra yeni soru düzeni
incelenir. Uygulamadaki görevlerin tamamı aynı zorlukta kabul edilmez. Mevcut
erişilebilir çalışma yöntemiyle karşılaştırmada içerik, süre ve araçlar
denetlenir; sıra etkisi, başka çalışmalar ve dış yardım kaydedilir.

Uygulama saati/saklama düzeni araştırma ölçümünün yerine geçmez. Küçük örneklemde
görev/kişi bazında gözlem raporlanır; genel etki yüzdesi ilan edilmez. Güncel
çoktan seçmeli görevler ilişkileri ayırt etmeyi ölçer; açık uçlu açıklama ve gerçek
nesne üzerinde uygulama uzman gözlemiyle tamamlanmalıdır.

## Karar

Erişilemeyen soru/yanıt, odak kaybı, kritik yanlış ilişki veya yanıltıcı başarı
ifadesi varsa ilgili akış düzeltilip yeniden denenir. Başka bir modeli denemek
bu sorunları çözme kanıtı sayılmaz. Önce sorunun erişim, temsil, kavram veya giriş
biçimiyle ilişkisi anlaşılır; ardından değişiklik aynı görevle doğrulanır.
