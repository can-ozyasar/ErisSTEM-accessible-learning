# ErişSTEM: kullanıcıyı anlama ve öğrenme deneyimi tasarımı

Araştırma tarihi: 9 Ekim 2026. Durum: kaynak taramasına ve mevcut kodun
incelenmesine dayanan ilk tasarım; kullanıcı görüşmesi veya etki deneyi yapılmadı.
Bu belge, mevcut öğrenme mimarisini tamamlar. Aşağıdaki ürün önerileri uygulanmış
özellik değildir; kaynak bulguları, tasarım varsayımları ve açık sorular ayrılmıştır.

Uygulama güncellemesi: bu araştırmanın ardından önerilerin bir bölümü
[modüler öğrenme atölyesine](ogrenme-atolyesi-uygulama.md) taşındı. Bu belge
araştırma başlangıcını, uygulama notu güncel çalışan kapsamı anlatır.

## 1. Ürün amacı ve temel ayrım

ErişSTEM'in amacı, kişinin seçtiği bir bilgi veya beceriyi erişilebilir biçimde
öğrenmesini, uygulamasını ve ihtiyaç duyduğunda bağımsız kullanmasını sağlamaktır.
Başarı, dinletilen sayfa veya üretilen betimleme sayısıyla ölçülmez.

Bir kavramı anlamak için zihinde gören bir kişinin görüntüsünü oluşturmak zorunlu
bir ürün hedefi değildir. Kullanıcının zihnindeki deneyimi dışarıdan varsayamayız.
Çember, uçak veya grafik için önemli soru: kişi hangi özellikleri biliyor,
ilişkileri nasıl açıklıyor ve bu bilgiyi yeni bir görevde kullanabiliyor mu?

Doğuştan/erken dönemde görmeyen, sonradan görme kaybı yaşayan ve az gören kişileri
tek öğrenme profiline indirmeyin. Bu ayrımlar tek başına öğretim yöntemi de
belirlemez. Önceki deneyim, Braille ve dokunsal grafik becerisi, yardımcı teknoloji,
işitme, dil, konu bilgisi ve kişinin tercihi ayrıca anlaşılmalıdır.
RNIB, bilgiye erişim yöntemlerinin bireysel değerlendirilmesini ve farklı
ortamlarda uygun yöntem birleşimlerinin öğretilmesini önerir. [K1, K2]

**Tasarım varsayımı:** başlangıçta kısa, atlanabilir ve değiştirilebilir tercih
seçimi sunmak; tıbbi tanı veya görme kaybı geçmişiyle kullanıcıyı zorunlu olarak
sınıflandırmamak. Sorulacaklar: öğrenme amacı, tercih edilen metin/ses/Braille,
ayrıntı düzeyi ve mevcut araçlar. Cihazın ekran okuyucu kullanımını güvenilir
biçimde otomatik saptadığımız varsayılmayacak.

## 2. Araştırmadan çıkan kararlar

| Kaynak bulgusu | ErişSTEM için çıkarım | Henüz doğrulanmayan nokta |
| --- | --- | --- |
| Öğretmenlerle yapılan dokunsal materyal çalışmasında gerçek nesneler ve 3B modeller dokunsal grafiklere geçişte kullanılıyor. [K3] | Uygun kavramlarda nesne/model keşfi → sade temsil → soyut ilişki akışı tasarlamak. | Bu akışın Türkçe hedef grubumuzdaki öğrenme etkisi. |
| Perkins, somut modellerin kavram gelişiminde kullanımını örnekliyor. [K4] | Sesli anlatımı fiziksel materyal için erişilebilir keşif yönergesiyle tamamlamak. | Materyale erişim, maliyet ve kullanıcının keşif tercihi. |
| RNIB, dokunsal haritalar için tarama becerisi, sadelik ve kademeli çalışma üzerinde duruyor. [K5] | Bütün şekli tek uzun paragrafta anlatmak yerine bütün → parça → ilişki gezinmesi sunmak. | Sesli gezinmenin dokunsal materyale hangi görevlerde yettiği. |
| W3C karmaşık görsellerde kısa açıklama ve ayrıntılı bilgiye erişimi gösteriyor. [K6] | Kısa tanıtım, yapısal açıklama ve mevcutsa kaynak verisi ayrı erişilebilir katmanlar olmalı. | Kullanıcının katmanlar arasında ek yük yaşamadan ilerlemesi. |
| Genişletilmiş çekirdek müfredat akademik alanların yanında teknoloji, günlük yaşam ve öz belirleme gibi becerileri kapsıyor. [K7] | Mimariyi yalnız sınıf veya sınav türüne bağlamamak. | İlk akademik dilim dışındaki ihtiyaç öncelikleri. |

Bu kaynaklar aynı tür kanıt değildir: K3 öğretmen deneyimlerine dayalı araştırma,
K4 uygulama örneği, K1/K2/K5/K7 eğitim rehberi, K6 teknik erişilebilirlik rehberidir.
Hiçbiri ErişSTEM'in öğrenme etkisini kanıtlamaz. Görsel erişim veya tesadüfi öğrenme
fırsatının azalması, bilişsel kapasite eksikliği olarak yorumlanmayacak.

## 3. Kavram öğretimi: iki somut örnek

Bu örnekler önerilen öğretim taslaklarıdır. Özel eğitim öğretmeni ve kullanıcılarla
gözden geçirilmeden doğrulanmış ders içeriği olarak yayımlanmaz.

### Çember

1. Ön bilgi: “Çember sözcüğünü hangi bağlamda kullandın? İstersen bildiğin bir
   örneği anlat.” Öğrencinin zaten bildiği konu gereksiz yere baştan anlatılmaz.
2. Varsa halka veya sabitlenmiş kabartma çevre çizgisiyle keşif: çizgiyi izleme,
   köşe olup olmadığını ve başlangıca dönüp dönmediğini inceleme. Fiziksel halka
   yalnız modeldir; kalınlığı ve malzemesi matematiksel çemberin özelliği değildir.
3. Matematiksel açıklama: düzlemde sabit bir noktaya eşit uzaklıktaki noktalar
   çemberi oluşturur. Merkez ve çevredeki noktalar işaretlenmiş bir materyalde
   merkezden çevreye uzaklıkları karşılaştırmak. Merkez çevrenin parçası değildir.
4. Ayrımlar: çember çevredir; daire iç bölgeyi de içerir. Halka modeli, küre ve
   elips aynı kavram değildir. “Tabak gibi” benzetmesi bu ayrımları tek başına
   öğretmez. Elips de köşesiz ve kapalı olduğundan yalnız bu iki özellik yetmez.
5. Anlama görevi: “Merkezden bazı çevre noktalarına uzaklık farklıysa bu şekil
   çember olabilir mi? Neden?” Ardından farklı ölçekte veya yönde bir örnek.

Materyal yoksa erişilebilir tanım ve ilişki soruları kullanılabilir; uygulama
sesli anlatımın dokunsal deneyimle aynı sonucu verdiğini varsaymaz. Amaç görsel
hayali puanlamak değil, çemberi ayırt ettiren ilişkiyi kullanmayı değerlendirmektir.

### Uçak

Önce öğrenme amacı belirlenir: bir nesnenin yapısını öğrenmek, uçuşun temelini
anlamak veya havaalanındaki yolculuk adımlarını öğrenmek farklı görevlerdir.

Yapı öğretiminde erişilebilir bir model varsa önce bütün, ardından gövde,
kanatlar ve kuyruk keşfedilir. Yönler modelin burnuna göre tanımlanır; anlatıcının
sağı/solu kullanılmaz. Parçaların yerleşimi ve işlevi ayrı anlatılır. Modelin
ölçeği ve temsil etmediği ayrıntılar belirtilir; her uçağın aynı motor/kanat
yerleşimine sahip olduğu söylenmez. Motor sesi nesnenin sesini tanıtabilir,
ancak şeklinin yerine geçmez.

Aktarım görevi: kişinin model üzerindeki parçaların birbirlerine konumunu
anlatması veya başka bir modelde aynı işlevi olan parçayı bulması. Havaalanı
becerisi için ise örnek görev, yardım talebi ve işlem sırasını açıklamak olabilir.
Bu, gerçek ortamda yönelim ve hareket eğitimini tamamladığı iddiası taşımaz.

## 4. Sınava hazırlanmak ve sınava girmek

Hazırlıkta hem konu bilgisi hem de sınavda kullanılacak erişim yöntemi çalışılır:
Braille/metin/sesle bilgiye erişme, soruyu ve seçenekleri ayrı inceleme, not alma,
istenen bölümü tekrar okutma, soru atlayıp geri dönme, yanıtı değiştirme ve süreyi
yönetme. Uygulamanın TTS'i insan okuyucunun birebir karşılığı sayılmaz.
RNIB, öğretimde kullanılan erişim yöntemlerinin sınavın değerlendirme biçimiyle
uyumunun erken kontrolünü önerir. [K5]

**Doğrulanmış Türkiye örneği:** 2026 LGS kılavuzunun 8.1 bölümünde total görme
yetersizliği olan öğrenciler için okuyucu ve kodlayıcı, tek kişilik salon,
20 dakika ek süre ve görsel sorular yerine eş değer sorular belirtiliyor;
soru muafiyeti yok. Az görenler için kitapçık ve yardım tercihlerine göre
düzenlemeler bulunuyor. Bu kurallar yalnız ilgili sınav ve yıl için aktarılır. [K8]

YKS ve EKPSS için ayrı resmî kaynaklar vardır. [K9, K10] LGS'nin süre veya soru
uyarlaması bu sınavlara kopyalanmaz. Üniversite ders sınavları için ilgili kurumun
engelli öğrenci birimi ve dersin sınav düzenlemesi ayrıca anlaşılmalıdır.

2026 YKS kılavuzunun 7.11.2 bölümündeki ek süre tanımı, okuyucu yardımı alan
görme engelli adaylar için TYT'de 30, AYT'de 50, YDT'de 60 dakika belirtiyor.
Aynı metinde diğer yardım/sağlık koşulları için farklı düzenlemeler de var;
7.11.3 bölümü yararlanma şartlarını açıklıyor. Bu nedenle yalnız “görme engelli”
etiketinden otomatik süre seçmek doğru bir ürün kuralı değildir. [K9]

**Önerilen iki mod:**

- Öğrenme: kavram keşfi, isteğe bağlı katmanlı açıklama, önceden doğrulanmış
  ipuçları, geribildirim ve yeni örnekle yardımsız deneme.
- Sınav provası: belirli sınav/yıl ve belgelenmiş düzenleme, soru/seçenek
  gezinmesi, yanıtı gözden geçirme, süre yönetimi; öğretim ipucu ve çözüm
  sınav sonunda açılır. Öğretim açıklamalarıyla erişim betimlemeleri ayrılır;
  betimleme cevap çıkarımını kullanıcı yerine yapmaz.

Sınav profili için en az şu bilgiler gerekir: kurum/sınav/yıl, resmî kaynak ve
doğrulama tarihi, adayın onaylı düzenlemesi, kitapçık/yardım biçimi, süre kuralı,
izinli araçlar, soru uyarlama yöntemi ve öğretmen incelemesi. Belirsiz profil
“gerçek sınavın birebir provası” diye sunulmaz. Resmî kararlar uygulama tarafından
verilmez. Adaya özel hak veya başvuru sonucu tahmin edilmez.

## 5. Mevcut projedeki karşılığı ve eksikler

İncelenen dosyalar: `apps/web/src/main.tsx`, `apps/web/src/SetPractice.tsx`,
`apps/api/app/pipeline/set_practice.py`, `docs/etkin-ogrenme-mimarisi.md`,
`docs/ogrenci-ogrenme-deneyimi.md`, `docs/evaluation_protocol.md`.
Depoda devam eden yerel değişiklikler var; bu belge onları değiştirmez.

| Mevcut temel | Boşluk | Önerilen değişiklik ve doğrulama |
| --- | --- | --- |
| Kaynak-bağlı içerik ve insan denetimi | Kaynak doğruluğu, kavram öğretiminin yeterliliğini göstermiyor. | İçerik onayına öğrenme amacı, ön koşul ve kavram yanılgısı incelemesi eklemek. |
| Türkçe okuma, semantik tablolar ve metin Braille akışı | Kullanıcı tercihleri ve gerçek araç deneyimi henüz ölçülmemiş. | Kullanıcının kendi cihazında görev testi; tercihlerin değiştirilebilir olması. |
| Kümeler için altı rehberli/aktarım sorusu | Başlangıç kavram yoklaması ve farklı temsil yolu yok. | İlk pilotta “ortak/yalnız A/en az birinde” ilişkilerini kısa ön görevlerle incelemek. |
| Yanlışta deneme sayısına göre üç ipucu | İpucu belirli kavram hatasını teşhis etmiyor. | Biçim hatası, konu yanılgısı ve erişim engelini ayırmak; teşhis yoksa kesin etiket koymamak. |
| Doğru sonuçla tamamlanma ve sonraki adıma geçiş | Tek doğru yanıt veya tekrar deneyerek başarı kalıcı öğrenme kanıtı değil. | İlk yanıt, yardım düzeyi ve gecikmeli yeni görev başarısını ayrı değerlendirmek. |
| Benzer yardımsız soruda yanlış/doğru geribildirimi | Yeniden deneme geribildirimi değerlendirme sonucunu etkileyebilir. | İlk yanıtı ayrı ölçmek; resmî prova sırasında anlık doğruluk göstermemek. |
| Hatırladım/tekrar çalışacağım seçimi | Öz bildirim, nesnel öğrenme ölçümü değil. | Öz bildirimi ayrı tutup yeni görev başarısıyla birlikte değerlendirmek. |
| OCR/sembol/TTS benchmark'ları | Görsel/işitsel temsil kalitesi ve bağımsız öğrenme aynı metrik değil. | Teknik doğruluk, erişim görevi, anlama ve öğrenme raporlarını ayırmak. |

“Sonucu kendiniz buldunuz” geribildirimi de yardım geçmişini dikkate almalıdır:
ipucuyla çözülen sorunun bağımsız başarı diye etiketlenmesi engellenmeli.

## 6. Kullanıcılarla birlikte araştırma protokolü

**İlk araştırma önerisi:** farklı görme deneyimleri ve erişim araçlarından
6–8 kişiyle keşif oturumu, ardından 2–3 uzman görüşmesi. Bunlar istatistiksel
temsil veya etkili örneklem büyüklüğü iddiası değildir. Aynı kişide farklı
deneyimler kesişebilir; kotaları birer tanı etiketi gibi kullanmayın.
Mümkünse yetişkinlerle ilk keşif, çocuklarla çalışma için uygun rıza ve kurum
süreci; katılım gönüllü, bırakılabilir ve erişilebilir olmalı. Kayıt ayrı tercihtir.

Katılımcı erişimi için GETEM, görme engelli örgütleri, özel eğitim öğretmenleri
ve üniversite engelli öğrenci birimleri olası kanallardır. GETEM'in mevcut
sesli/metin kitap hizmeti bir bağlam kaynağıdır. [K11] Bu belge ortaklık veya
iletişim kurulmuş olduğu anlamına gelmez.

### Görüşmede sorulacaklar

- Son çalıştığın konuyu veya girdiğin sınavı anlatır mısın? Kullandığın araçlarla
  çalışma sürecinin küçük bir bölümünü göstermek ister misin?
- En çok zaman hangi işte gidiyor: materyali bulma, anlama, not alma, soruya
  dönme, cevap verme? Yakın zamanda yaşadığın bir örnek var mı?
- Bir şeklin açıklaması sana hangi durumda yardımcı oluyor? Hangi durumda
  nesneye, dokunsal çizime, Braille'e veya daha farklı açıklamaya ihtiyaç duyuyorsun?
- Anlatımı hangi noktada durdurup yeniden dinlemek veya parçalamak istersin?
- Sınavda okuyucuyla/diğer araçlarla nasıl çalışıyorsun? Hazırlık ve gerçek sınav
  arasındaki farklar neler?
- Uygulamanın senin yerine yapmasını istemediğin şeyler neler? Nasıl bir gelişme
  senin için anlamlı olurdu?

“Körler çemberi nasıl hayal eder?” gibi tek bir ortak cevap arayan sorular yerine
kişinin deneyimini ve somut görevini dinleyin. Göz bağlayarak yapılan geliştirici
deneyi, kör kullanıcı deneyiminin kanıtı değildir.

### Gözlenen görevler ve kayıt

Kişinin kendi cihazı ve alışık olduğu ayarlarla: ilgili içeriği bulma, sorunun
bir kısmını tekrar inceleme, tablo başlığına ulaşma, yanıt girme, yardımı seçme,
geri dönme ve yeni bir ilişkisel soruyu çözme. Aynı anda uzun açıklamalarla
düşünmesini istemek dinleme görevini zorlaştırıyorsa görüşmeyi görev sonuna bırakın.

Her görevde görev kimliği, cihaz/araç, içerik sürümü, tamamlanma, gereken yardım,
kritik hata ve kullanıcının açıklaması kaydedilir. Sorun sınıfları:
**erişim**, **temsil/anlatım**, **kavram**, **giriş biçimi**, **kaynak yanlışlığı**.
Gözlem yetersizse “belirsiz” olarak tutulur; yanlış cevap otomatik olarak kavram
eksikliği sayılmaz. Kimlik veya ham cevap/ses genel uygulama loguna eklenmez.

## 7. Gerçek faydayı kanıtlama

Üç ayrı sonuç ölçülür:

1. **Erişim:** görev bağımsız tamamlanabiliyor mu; hangi aşamada dış yardım gerekiyor?
2. **Anlama:** öğrenci ilişkiyi kendi yöntemiyle açıklayıp karşı örneği ayırt edebiliyor mu?
3. **Öğrenme:** başlangıca göre, yeni ve yardımsız görevde daha başarılı mı;
   bir süre sonra bu başarı korunuyor mu?

Önerilen küçük pilot: başlangıç yoklaması → mevcut erişilebilir çalışma yöntemi
veya yeni akış → hemen yeni sorular → 24–48 saat sonra farklı eşdeğer sorular.
Karşılaştırmada konu/soru zorluğu, çalışma süresi ve cihaz kontrol edilir;
eşdeğer soru setleri öğretmen tarafından incelenir. Her iki yöntemi aynı kişi
deneyecekse sıra etkisi ve öğrenmenin diğer koşula taşınması hesaba katılır.
Sonuçlar küçük örneklemde kişi/görev düzeyinde raporlanır; bütün görme engelli
kullanıcılara genellenmez. Gecikmeli test ve örneklem sayısı ürün araştırması
önerisidir, kanıtlanmış optimum değildir.

Kritik kaynak/operatör hatası, erişilemeyen soru veya yanıt, kaybolan kullanıcı
yanıtı, sınav provasında cevap sızması düzeltilmeden ilgili akış genişletilmez.
Yalnız süre kısalması öğrenme başarısı sayılmaz; doğruluk, yardım ve kullanıcı
tercihi birlikte değerlendirilir. ASR'nin sesi doğru yazması öğrencinin
matematiksel ilişkiyi anladığını göstermez.

## 8. İlk uygulanabilir geliştirme sırası

1. Keşif oturumlarını hazırlamak: erişilebilir davet/oturum metni, sentetik
   kümeler görevleri ve anonim gözlem şablonu. Görüşmeler henüz yapılmadı.
2. Mevcut kümeler diliminde ön koşul yoklaması, isteğe bağlı kısa kavram açıklaması
   ve önceden yazılmış hata türüne uygun yardım prototipi. Yeni açıklamalar
   içerik incelemesinden ve gerçek kullanıcı görevinden geçmeli.
3. Kavram içeriği sözleşmesi: amaç, ön koşullar, doğrulanmış özellik/ilişkiler,
   temsil seçenekleri, model sınırlamaları, bilinen yanılgılar, erişim betimlemesi,
   öğretim ipucu, anlama/aktarım görevleri ve kaynak/onay sürümü. Temsil ile
   pedagojik yardım farklı alanlarda tutulur.
4. Pilotun kanıtına göre çember için fiziksel materyal yönergesi ve katmanlı
   açıklama eklemek; materyal bulunmadığında kullanıcının seçeneklerini açıkça sunmak.
5. Tek bir belgelenmiş sınav profiliyle prova prototipi. Tüm sınavları aynı
   zaman/soru uyarlamasıyla desteklediğimizi ilan etmemek.
6. Akademik dilim doğrulandıktan sonra üniversite, mesleki öğrenme ve gündelik
   beceriler için ayrı ihtiyaç keşfi. Veri modeli sınıf/sınav zorunluluğu taşımaz.

Yapay zekâ öncelikle kaynak çıkarımı, konuya erişim ve doğrulanmış ilişkilerden
anlatım/yardım adayları üretmede değerlendirilebilir. Kullanıcının bilmediği
kavramı, zihinsel deneyimini veya sınav hakkını kesin olarak çıkarsayan bir
otorite olarak kullanılmaz. Model seçimi, kullanıcıya ölçülen katkıya dayanır.

## Kaynaklar

K1. [RNIB — Making learning accessible](https://www.rnib.org.uk/professionals/education-professionals/making-learning-accessible-information-for-teachers-and-teaching-assistants/).

K2. [RNIB ve ortakları — Curriculum Framework for Children and Young People with Vision Impairment](https://www.rnib.org.uk/documents/428/CFVI-Framework_Nov_22.pdf), özellikle bilgiye erişim ve dokunsal grafik becerileri.

K3. [Phutane ve diğerleri (2022) — Tactile Materials in Practice](https://arxiv.org/abs/2202.12280).

K4. [Perkins — Accessibility and learning in three dimensions](https://www.perkins.org/accessibility-and-learning-in-three-dimensions/).

K5. [RNIB — How to adapt maps for learners with vision impairment](https://www.rnib.org.uk/professionals/research-and-data/reports-and-insight/how-to-adapt-maps-for-learners-with-vision-impairment/).

K6. [W3C WAI — Complex Images](https://www.w3.org/WAI/tutorials/images/complex/).

K7. [TSBVI — Expanded Core Curriculum / Programs](https://www.tsbvi.edu/programs).

K8. [MEB — 2026 LGS Başvuru ve Uygulama Kılavuzu](https://odsgm.meb.gov.tr/meb_iys_dosyalar/2026_04/69cfb9daaf8f2557696260_LGS_Basvuru_ve_Uygulama_K%C4%B1lavuzu_2026.pdf), bölüm 8.1, basılı sayfa 7–8.

K9. [ÖSYM — 2026 YKS Kılavuzu ve engelli başvuru kaynakları](https://www.osym.gov.tr/2026yuksekogretim-kurumlari-sinavi-yks-kilavuzu).
Ek süre için [kılavuz PDF'si](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/basvuru_kilavuz06022026.pdf),
bölüm 7.11.2–7.11.3, basılı sayfa 41–42 incelendi. PDF web aracına büyük geldiği
için geçici indirme ve yerel metin çıkarımıyla kontrol edildi; depoya alınmadı.

K10. [ÖSYM — Görme engelli adaylar için hazırlanmış 2026 EKPSS ve Kura Kılavuzu](https://www.osym.gov.tr/gorme-engelli-adaylar-icin-hazirlanmis-2026-ekpss-ve-kura-kilavuzu).

K11. [Boğaziçi Üniversitesi GETEM E-Kütüphane](https://www.getem.boun.edu.tr/).
