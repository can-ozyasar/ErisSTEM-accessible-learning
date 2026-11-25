# Öğrenme, kalite yönetimi ve sınav provası

Son güncelleme: 25 Kasım 2026. Öğrenci, uzman, pilot ve yayın kontrolü akışları
uygulamaya bağlandı. Gerçek uzman incelemesi veya katılımcı çalışması otomatik
üretilmedi. Mevcut geliştirme kimlik doğrulaması nedeniyle kurulum yerel
kullanıma yöneliktir.

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

Etkin yerel aday paketi 81 metin tabanlı AYT Tarih sorusundan oluşur; bir
oturumda 81 soru gösterilir. Paket 63 lisans-kaydı bağlı yerel pilot sorusu ile
18 AI kaynak incelemeli aday sorusu içerir. Son 18 sorunun 13'ünde öğrenciye
gösterilen son kanıt demeti doğrulanmıştır; diğer 5 soru çözülebilir, ancak
kaynaklı koçluk güvenli biçimde çekimser kalır. AI incelemesi insan tarih
öğretmeni onayı değildir; paket resmî sınav veya öğretmen eşdeğerliği iddiası
taşımaz. Kullanım kaydı yalnız yerel pilotu doğrular; harici API işlemeye veya
genel yayıma izin vermez.

Kısa 1–60 dakikalık çalışma veya seçilen YKS profilinin tam süresi seçilebilir;
tam süre seçimi soru bankasını tam sınava dönüştürmez. Paket yalnız metin
sorularını kapsar; görsel ve tablo gerektiren sorular dışarıda bırakılmıştır.
Sınav sırasında doğru cevap, açıklama ve koçluk API yanıtında yer almaz. Yanlış
soruda ilk ipucu doğru yanıtı göstermez; öğrenci gerekçe verdikten sonraki
ikinci turda doğru seçenek ve kaynaklı açıklama açılır. Son kanıtı doğrulanmamış
beş soruda kaynaklı çözüm/koçluk da açılmaz.

Süre sunucu zamanına göre belirlenir. Aktif oturumda cevap anahtarı ve
açıklama dönmez. Yanıtlar değiştirilebilir; kayıt sonrası doğruluk bildirilmez.
Bitirilen veya süresi dolan oturum yeniden cevaplanamaz. Çözümler yalnız
sonuç ekranında açılır. Yenileme veya aynı sekmede geri dönüş sonrası
kaydedilmiş yanıt ve kalan süreyle devam edilir. Uygulama TTS'i insan
okuyucunun birebir karşılığı olarak tanıtılmaz.

Oturum kimliği tahmin edilmesi güç rastgele kimliktir ve sekme depolamasında
tutulur; öğrenme geçmişiyle veya katılımcı kimliğiyle bağlanmaz. Prova sırasında
seçenek kimlikleri sunucuda geçici saklanır. Bitişte genel cevap/işaret
haritaları temizlenir; yanlış seçim, yalnız o soruya yönelik koçluk tamamlanana
kadar ayrı tutulur ve ikinci turda silinir. Sonuç ve koç mesajı kullanıcı
silene veya yedi günlük bakım süresi dolana kadar kalabilir. Kullanıcı provanın
bütün sunucu verisini silebilir. Sekmeyi kapatmak sunucu verisini hemen silmez;
bakım süreci bırakılan oturumu sonlandırır.

### Ses ve cache davranışı

Öğrenci sorularının kök ve A–E şık sesleri, Docker iç ağındaki Piper
`tr_TR-dfki-medium` ile üretilip `tts_audio_cache` adlı yerel Docker volume'ünde
içerik özetine göre saklanır. 25 Kasım 2026 ölçümünde 81 soru için 486 ses
biriminin tamamı geçerli WAV verdi; cache'li API isteği p95'i 11,74 ms ölçüldü.
Fine-tune edilmiş V5 sesin aktif paketle eşleşen dosyası yoktur; öğrenci bu
sürümde Piper sesini duyar. Tarayıcı İngilizce sistem sesine sessizce düşmez;
yerel ses hizmeti yoksa metin ekran okuyucuda kalır.

Canlı koç mesajları da aynı yerel Piper servisiyle seslendirilir. Bu makinede
TTS servisine 4 CPU birimi ayrıldığında aynı koç yanıtı için beş WAV isteğinin
p95'i 2,31 sn ölçüldü. Bu küçük, tek cihazlı örneklem genellenebilir performans
garantisi değildir. Cache normal `docker compose down`/yeniden başlatmada korunur;
`docker compose down -v` ses cache'i ve PostgreSQL verisini siler. Başka
makinede cache yoksa ilk ses üretimi daha uzun sürebilir. Ölçüm ayrıntıları
[özel pilot kabul raporundadır](../reports/ayt-private-pilot-acceptance-v1.json).

Soru metinlerini, öğrenci yanıtlarını veya kaynak kesitlerini Kaggle/DeepSeek'e
göndermeyin: mevcut kullanım kaydı harici işlemeyi yetkilendirmiyor. DeepSeek
varsayılan olarak kapalıdır. Kaynak izni ve öğrenciye açık rıza birlikte
doğrulanmadan çevrim içi koçluğu etkinleştirmeyin.

## Kurulum ve bakım

```bash
docker compose up --build -d
docker compose ps
```

API sağlık kontrolünden geçmeden web ve sınav bakım servisi başlamaz.
PostgreSQL migrasyonu `0008_learning_records.sql` yeni kayıt tablosunu
oluşturur; mevcut kitap/öğretmen tabloları silinmez. Web imajı kilitli npm
bağımlılıklarıyla `npm ci` kullanır. Web portu yalnız `127.0.0.1:5173`'tedir.

`exam-maintenance`, 30 saniyede bir bırakılan oturumların süresini kontrol eder;
ham yanıtları temizler ve yedi günden eski prova kayıtlarını siler. Pilot
kayıtlarını bu bakım silmez; araştırma süresi ve geri çekme süreci ayrı yönetilir.
Bakım yalnız sayıları loglar; cevap veya gözlem metni yazmaz.

Uygulamayı durdurup yeniden açmak için `docker compose down` ve sonra
`docker compose up -d` kullanın; named volume'ler korunur. Güncelleme sonrası
imajları yeniden derleyin: `docker compose up --build -d`. Sağlık durumunu
`docker compose ps` ile kontrol edin; ses sorununda
`docker compose logs --tail=100 api tts`, veritabanı/API sorununda
`docker compose logs --tail=100 api db` kullanın. Yedek almadan
`docker compose down -v` çalıştırmayın.

PostgreSQL yedeğini repository dışında ve korumalı bir konuma alın:

```bash
docker compose exec -T db pg_dump -U eristem -d eristem | gpg --symmetric --cipher-algo AES256 --output /korumali/yol/eristem.sql.gpg
```

GPG kurulu olsun; örnek hedef yolunu size ait güvenli dizinle değiştirin ve
parolayı komut satırına yazmayın. Kaynak PDF'leri ve `data/private` içeriğini
ayrıca erişimi kısıtlı, şifreli yedekleyin; `.env`, kaynaklar, cevap anahtarları
ve pilot kayıtlarını Git'e veya harici yedek servisine göndermeyin. Piper cache'i
yeniden üretilebilir ve veritabanı yedeklemesinin yerine geçmez.

Tek bakım geçişi (`apps/api` içinde, uygulamanın `DATABASE_URL` ortamıyla):

```bash
.venv/bin/python -m app.exam_maintenance
```

Sunucuya dış erişim için mevcut `X-Role` geliştirme başlıkları yeterli değildir.
`APP_ENV=production` kimlik sağlayıcısı bağlanana kadar API'yi kapatır. Bu
sürüm halka açık dağıtım, tam müfredat bankası veya gerçekleşmiş kullanıcı
araştırması iddiası taşımaz; ilgili akışları yerelde birlikte çalıştırır.

## Kontroller

9 Ekim 2026 temel doğrulaması: 172 API testi, 13 web birim testi ve 7
uçtan uca tarayıcı senaryosu geçti. API Ruff denetimi, web derlemesi ve ESLint
denetimi geçti. Docker API, web ve bakım servisleri çalıştırıldı; PostgreSQL'de
yeni tablo ve altı ekranın açılması, ilgili API yanıtları ve tarayıcı çalışma
hataları ayrıca kontrol edildi. Bu sonuçlar insan katılımcı doğrulaması değildir.
25 Kasım 2026 ek doğrulaması, API testlerini geçici Python 3.12.3 ortamında
846 geçti / 5 atlandı / 0 başarısız olarak yeniden çalıştırdı; web derlemesi,
ESLint ve 16 web birim testi de geçti. Ruff 0.17.6 ilk taramada 79 bulgu verdi;
canlı API'deki tek biçim bulgusu davranış korunarak düzeltildi ve ilgili 26 test
ile tam API paketi yeniden geçti. Güncel taramada pipeline dosyalarında 50,
testlerde 28 bulgu kaldı; pipeline dışındaki API uygulama dosyaları temiz.
Ekimdeki Ruff sonucu tarihsel bir çalıştırmadır. Kalan farklı dosya bulguları
bu kabul turunda otomatik toplu düzeltilmedi; ayrıntı kabul raporundadır.

API testleri; yetkisiz erişim, eksik rıza, prova/gerçek katılım ayrımı, eski
içerik kanıtı, kritik pilot engeli, yayın rolü, eşzamanlı kayıt çatışması,
sunucu süresi, sonuç gizleme, yanıt değişikliği, bitiş sonrası ham cevap silme,
geri çekme ve bakım süresi gibi davranışları kapsar.

Tarayıcı testleri; mevcut öğrenme akışlarının yanında sınav gezinmesi,
yenileme sonrası devam, sonuç açma/silme, uzman düzeltme kaydı, pilot görevlerini
tamamlama ve rıza olmadan katılımcı oturumu açamama durumlarını kapsar.
Test kanıtları ayrı geçici veritabanına yazılır; gerçek araştırma kanıtı sayılmaz.
Otomatik axe taraması gerçek ekran okuyucu kullanıcı denemesinin yerine geçmez.
25 Kasım 2026 ek doğrulamasında 81 soruluk gerçek yerel paket, 486 soru/şık ses
rotası, aktif sınav cevap/koçluk gizliliği ve klavyeyle deneme→iki koçluk turu→
veri silme akışı kontrol edildi. NVDA+Firefox, TalkBack+Chrome ve görme engelli
katılımcı görevleri hâlâ bekliyor; sonuçlar kabul raporunda açıkça ayrılmıştır.

## Resmî kaynaklar

- [MEB 2026 LGS kılavuzu](https://odsgm.meb.gov.tr/meb_iys_dosyalar/2026_04/69cfb9daaf8f2557696260_LGS_Basvuru_ve_Uygulama_K%C4%B1lavuzu_2026.pdf): genel açıklamalar ve 8.1.2.
- [ÖSYM 2026 YKS kılavuzu](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/basvuru_kilavuz06022026.pdf): sınav süreleri ve 7.11.2–7.11.3.
- [ÖSYM 2026 EKPSS kılavuzu](https://dokuman.osym.gov.tr/pdfdokuman/2026/EKPSS/kilavuz_ekpd0402026.pdf): 1.2, 1.4 ve 3.1 süre tablosu.
# DeepSeek coach (optional outbound access)

The default Compose stack keeps the API on the isolated `internal` network.
To use the experimental DeepSeek coach, first set `DEEPSEEK_COACH_ENABLED=true`
and `DEEPSEEK_API_KEY` in the private `.env` file, then start the API with the
opt-in overlay:

```sh
docker compose -f docker-compose.yml -f docker-compose.deepseek.yml up -d api
```

This gives the API outbound network access but does not publish its port on the
host. The model is still called only for a post-exam coaching turn when that
student request carries explicit external-processing consent. Active-exam
answers are never sent. Do not use this mode for real student data until the
privacy notice and retention behavior have been reviewed. Return to the
offline/default network with:

```sh
docker compose -f docker-compose.yml up -d api
```

The default offline stack remains the supported local-pilot configuration;
DeepSeek is an optional external candidate and falls back to deterministic
coaching on provider, parsing, or safety-check failure.
