# Öğrenme, kalite yönetimi ve sınav provası

Tarih: 9 Ekim 2026. Öğrenci, uzman, pilot ve yayın kontrolü akışları uygulamaya
bağlandı. Gerçek uzman incelemesi veya katılımcı çalışması otomatik üretilmedi.
Mevcut geliştirme kimlik doğrulaması nedeniyle kurulum yerel kullanıma yöneliktir.

## Açılacak ekranlar

| İş | Adres |
| --- | --- |
| Öğrenci kütüphanesi | `http://localhost:5173/` |
| Öğrenme atölyesi | `http://localhost:5173/?view=practice` |
| Sınav erişim provası | `http://localhost:5173/?view=exam` |
| Uzman içerik incelemesi | `http://localhost:5173/?mode=learning-review` |
| Kullanıcı pilotu | `http://localhost:5173/?mode=pilot` |
| Öğrenme yayın kontrolü | `http://localhost:5173/?mode=learning-release` |

## Uzman, pilot ve yayın zinciri

1. Uzman, bir öğrenme konusunun açıklamalarını, temsil sınırlarını, bütün soru
   ve cevap anahtarlarını inceler. Tamamlanan kontrolleri, uzmanlık alanını
   ve private değerlendirme kaydı referansını girer. Düzeltme isteğinde açıklama
   gerekir; eksik kontrolle onay verilemez.
2. Araştırmacı, prova veya gerçek yetişkin katılımcı oturumu açar. Gerçek
   oturum için bilgilendirilmiş rıza ve private rıza kaydı referansı gerekir.
   Sistem kod üretir; isim, iletişim, tanı ve ham cevap için alan yoktur.
3. Sekiz gözlem görevi ayrı kaydedilir. Dış yardım sayısı ve bağımsızlık
   durumu tutarlı olmalıdır. Sorun türü ve önem düzeyi birlikte belirtilir.
   Görev geçilmesi, yanlış cevap ve erişim sorunu ayrı değerlendirilir.
4. Tamamlanmış gerçek oturumda soru erişimi, yanıt girişi ve gezinme
   araştırmacı yardımı olmadan tamamlanmış olmalıdır. Güncel gerçek oturumlardan
   herhangi birindeki kritik sorun yayın kontrolünü engeller.
5. Onaylayıcı, güncel uzman onayı ve uygun gerçek pilot kanıtını kontrol edip
   yayını onaylar. Uzman rolü bu yayını kendi başına yapamaz. Araştırmacı
   provası, kaç görev tamamlanırsa tamamlansın gerçek kullanıcı kanıtı değildir.

İçerik checksum'ı anlatımları, soruları, seçenekleri, doğru cevapları ve ipuçlarını
kapsar. Bunlardan biri değişirse eski uzman/pilot kanıtı yeni içeriğe geçmez.
Eşzamanlı düzenlemeler sürüm kontrolüyle 409 alır; eski form yeni kaydı ezmez.
Tamamlanmış pilotun gözlemleri değiştirilemez. Veri geri çekildiğinde pilot
ve rıza referansları silinir, ilgili yayın yeniden kontrol gerektirir.

Bu ilk kabul kapısı geniş örneklemde öğrenme etkisinin kanıtı değildir.
[Pilot protokolü](ogrenme-atolyesi-pilot.md) ile katılımcının kendi araçlarında
gözlem ve uzman içerik incelemesi gerçekten yapılmalıdır. Uzman kaydı referansı
private kanıta işaret eder; uygulama bu kişinin diplomasını veya mesleki yetkisini
otomatik doğruladığını iddia etmez. Geliştirme kayıtlarında aktör rolü tutulur;
üretimde kişi bazında kimlik doğrulama ayrıca gerekir.

Varsayılan geliştirme modunda sentetik içerikler bekleyen inceleme bilgisiyle
görünebilir. `LEARNING_REQUIRE_RELEASE=true` ayarlanırsa öğrenci kataloğu ve
yeni/eski kümeler uç noktaları yalnız güncel yayın kontrolünü geçen konulara
açılır. Bu değişken API ortamına verilmelidir; bir yayın kaydı üretmez.

## Sınav erişim provası

2026 yılı için dört kaynak-bağlı düzenleme bulunur:

| Profil | Temel süre ve ek süre |
| --- | --- |
| LGS total görme yetersizliği | Sözel 75 + 20, sayısal 80 + 20 dakika |
| YKS okuyucu yardımı alan görme engelli aday | TYT 165 + 30, AYT 180 + 50, YDT 120 + 60 dakika |
| EKPSS kitapçığı okuyamayan, okuyucu yardımı alan aday | 60 + 40 dakika |
| EKPSS soruları kendisi okuyabilen alt grup | 60 dakika; bu alt grupta ek süre yok |

Kaynaklar 9 Ekim 2026 tarihinde kontrol edildi. Profiller diğer yıllara,
diğer yardım/sağlık koşullarına veya bütün az gören adaylara otomatik uygulanmaz.
Adayın kendi onaylı düzenlemesi ve ilgili yılın kılavuzu esastır. Uygulama
başvuru/sağlık değerlendirmesi yapmaz.

Bu sürüm **altı özgün sentetik soruyla prosedür çalışmasıdır**: soru bulma,
tekrar dinleme, atlama, geri dönme, yanıt değiştirme, gözden geçirme işareti,
zaman yönetimi ve bitirme. Kısa 1–60 dakikalık çalışma veya seçilen profilin
tam süresi seçilebilir; tam süre seçimi soru bankasını tam sınava dönüştürmez.
Sorular konu/öğrenim düzeyine göre resmî LGS/YKS/EKPSS denemesi olarak
doğrulanmış değildir; sınav puanı veya başarı tahmini üretilmez.

Süre sunucu zamanına göre belirlenir. Aktif oturumda cevap anahtarı ve
açıklama dönmez. Yanıtlar değiştirilebilir; kayıt sonrası doğruluk bildirilmez.
Bitirilen veya süresi dolan oturum yeniden cevaplanamaz. Çözümler yalnız
sonuç ekranında açılır. Yenileme veya aynı sekmede geri dönüş sonrası
kaydedilmiş yanıt ve kalan süreyle devam edilir. Uygulama TTS'i insan
okuyucunun birebir karşılığı olarak tanıtılmaz.

Oturum kimliği tahmin edilmesi güç rastgele kimliktir ve sekme depolamasında
tutulur; öğrenme geçmişiyle veya katılımcı kimliğiyle bağlanmaz. Prova sırasında
seçenek kimlikleri sunucuda geçici saklanır. Bitişte ham seçimler ve işaretler
temizlenir; soru düzeyinde doğru/yanlış/boş ve çözüm bilgisi kalır. Kullanıcı
provanın bütün sunucu verisini silebilir. Sekmeyi kapatmak sunucu verisini
hemen silmez; bakım süreci bırakılan oturumu sonlandırır.

## Kurulum ve bakım

```bash
docker compose up --build -d
```

API sağlık kontrolünden geçmeden web ve sınav bakım servisi başlamaz.
PostgreSQL migrasyonu `0008_learning_records.sql` yeni kayıt tablosunu
oluşturur; mevcut kitap/öğretmen tabloları silinmez. Web imajı kilitli npm
bağımlılıklarıyla `npm ci` kullanır. Web portu yalnız `127.0.0.1:5173`'tedir.

`exam-maintenance`, 30 saniyede bir bırakılan oturumların süresini kontrol eder;
ham yanıtları temizler ve yedi günden eski prova kayıtlarını siler. Pilot
kayıtlarını bu bakım silmez; araştırma süresi ve geri çekme süreci ayrı yönetilir.
Bakım yalnız sayıları loglar; cevap veya gözlem metni yazmaz.

Tek bakım geçişi (`apps/api` içinde, uygulamanın `DATABASE_URL` ortamıyla):

```bash
.venv/bin/python -m app.exam_maintenance
```

Sunucuya dış erişim için mevcut `X-Role` geliştirme başlıkları yeterli değildir.
`APP_ENV=production` kimlik sağlayıcısı bağlanana kadar API'yi kapatır. Bu
sürüm halka açık dağıtım, tam müfredat bankası veya gerçekleşmiş kullanıcı
araştırması iddiası taşımaz; ilgili akışları yerelde birlikte çalıştırır.

## Kontroller

9 Ekim 2026 yerel doğrulaması: 172 API testi, 13 web birim testi ve 7
uçtan uca tarayıcı senaryosu geçti. API Ruff denetimi, web derlemesi ve ESLint
denetimi geçti. Docker API, web ve bakım servisleri çalıştırıldı; PostgreSQL'de
yeni tablo ve altı ekranın açılması, ilgili API yanıtları ve tarayıcı çalışma
hataları ayrıca kontrol edildi. Bu sonuçlar insan katılımcı doğrulaması değildir.

API testleri; yetkisiz erişim, eksik rıza, prova/gerçek katılım ayrımı, eski
içerik kanıtı, kritik pilot engeli, yayın rolü, eşzamanlı kayıt çatışması,
sunucu süresi, sonuç gizleme, yanıt değişikliği, bitiş sonrası ham cevap silme,
geri çekme ve bakım süresi gibi davranışları kapsar.

Tarayıcı testleri; mevcut öğrenme akışlarının yanında sınav gezinmesi,
yenileme sonrası devam, sonuç açma/silme, uzman düzeltme kaydı, pilot görevlerini
tamamlama ve rıza olmadan katılımcı oturumu açamama durumlarını kapsar.
Test kanıtları ayrı geçici veritabanına yazılır; gerçek araştırma kanıtı sayılmaz.
Otomatik axe taraması gerçek ekran okuyucu kullanıcı denemesinin yerine geçmez.

## Resmî kaynaklar

- [MEB 2026 LGS kılavuzu](https://odsgm.meb.gov.tr/meb_iys_dosyalar/2026_04/69cfb9daaf8f2557696260_LGS_Basvuru_ve_Uygulama_K%C4%B1lavuzu_2026.pdf): genel açıklamalar ve 8.1.2.
- [ÖSYM 2026 YKS kılavuzu](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/basvuru_kilavuz06022026.pdf): sınav süreleri ve 7.11.2–7.11.3.
- [ÖSYM 2026 EKPSS kılavuzu](https://dokuman.osym.gov.tr/pdfdokuman/2026/EKPSS/kilavuz_ekpd0402026.pdf): 1.2, 1.4 ve 3.1 süre tablosu.
