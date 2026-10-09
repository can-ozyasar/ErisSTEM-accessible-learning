# Öğrenme atölyesi: uygulanan kapsam

Tarih: 9 Ekim 2026. Durum: çalışan geliştirme prototipi; uzman incelemesi ve
görme engelli kullanıcı pilotu yapılmadı. Genel öğrenme etkisi veya resmî sınav
uygunluğu iddiası yoktur.

Güncelleme: uzman inceleme, pilot kayıt, yayın kontrolü ve ayrı sınav erişim
provası ekranları uygulamaya bağlandı. Gerçek inceleme/görüşmeler otomatik
üretilmedi. Güncel birlikte çalışma akışı [işletim kılavuzundadır](tam-uygulama-isletim.md).

## Öğrenci deneyimi

Kütüphaneden **Öğrenme atölyesi** açılır; mevcut `?view=practice` adresi korunur.
Kullanıcı kümeler, çember veya uçak konusunu seçer. Konu ve sürüm bazında:

1. Ön bilgi yoklaması: kısa ilişki soruları. Açıklama/ipucu sunulmaz; ilk
   geçerli yanıt tutulur. Soruyu geçmek yanlış cevap veya başarı sayılmaz.
2. Rehberli çalışma: isteğe bağlı kısa açıklama, ayrıntılı ilişki açıklaması,
   nesne/liste/model keşfi yönergesi ve temsil sınırları. Yanlış yanıtta önceden
   yazılmış yardım; kümelerde belirli yanıt ilişkilerine uygun ipucu.
3. Aktarım: farklı sorularda tek ilk geçerli yanıt. Yardım sunulmaz; yanlış
   cevap geri bildirimi sonrası aynı soruyla sonucu değiştirme engellenir.
4. Gecikmeli deneme: önceki üç bölümün görevleri yanıtlanıp veya geçilip akış
   bitirildikten 24 saat sonra farklı sorular açılır. Erken tekrar gecikmeli
   başarı diye kaydedilmez. Devam eden gecikmeli deneme yeniden açılabilir.

Kümelerde 12, çemberde 7, uçakta 7 görev vardır. Bütün görevler sentetiktir;
kitap OCR'sinden veya resmî sınav bankasından gelmez. Çember ve uçak, araştırma
belgesindeki kavram/temsil ayrımlarının küçük uygulama örnekleridir.

Kısa/ayrıntılı anlatım, uygulama ses hızı ve büyük metin tercihleri değiştirilebilir.
Metin her zaman görünür/ekran okuyucuya açıktır; ses otomatik başlamaz. Yerel
Türkçe ses bulunmazsa başka dilde ses seçilmez. Öğrenci standart metin veya
cihazının Braille girişini kullanabilir; matematiksel Braille çıktısı sunulmaz.
Herhangi bir görme geçmişi veya tıbbi tanı sorulmaz.

## İçerik ve API sınırı

`apps/api/app/pipeline/learning_experience.py` içinde modül özeti, ders katmanları,
görev aşaması, yanıt türü ve ilgili ders kimliği ayrı sözleşmelerdir.
Soru seçeneklerinin doğruluk bilgisi ve ipuçları istemci bankasına eklenmez.
İpuçları yalnız rehberli yanlış yanıt kontrolünde döner. Ders açıklaması
öğretim içeriği olduğundan doğal olarak ilişkilerin doğruluğunu anlatır;
“cevap anahtarı gönderilmez” bu içeriğin gizli olduğu anlamına gelmez.

- `GET /v1/student/learning/modules`: konu kataloğu.
- `GET /v1/student/learning/modules/{module_id}`: sürümlü dersler ve görevler.
- `POST /v1/student/learning/modules/{module_id}/exercises/{exercise_id}/check`:
  sınırlı yanıt kontrolü. `answer` ve `attempt` kabul eder; doğruluk, biçim
  durumu ve uygunsa yardım döner. Yanıt saklamaz.

Kimlik/rol sınırı mevcut uygulama ile aynıdır. Üretimde OIDC kurulmadan
geliştirme `X-Role` başlıklarıyla erişim açılamaz. Eski kümeler API'si korunur.
LLM, öğrenci cevabını puanlamaz ve psikolojik/kavramsal teşhis üretmez.

## İlerleme ve ölçüm

Tarayıcıda yalnız görev kimliği altında deneme sayısı, ilk doğruluk, ilk yanıtta
uygulama yardımı olup olmadığı, herhangi bir yardım kullanımı, tamamlanma,
geçilme ve tamamlanma zamanı tutulur. Ham yanıt, ses veya kimlik saklanmaz.
Tercihler ayrı bir yerel anahtardır. Konu/sürüm anahtarı eski ilerlemeyi yeni
sorulara taşımayı engeller; eski ilk API ilerlemesi yeni yoklamaya kopyalanmaz.

İlk yanıttan sonra gelen ipucu, önceki ilk yanıtın yardım durumunu değiştirmez.
Yanıt gönderimi sırasında alınan yardım da ilk gönderim anının gözlemini
değiştirmez. Biçim hatası ve ağ hatası geçerli deneme sayılmaz. İlk yanlış yanıt,
sonradan rehberli başarıyla üzerine yazılmaz. Uygulama dışındaki yardımı bu
otomatik kayıt ölçemez; “yardımsız” burada uygulama içi yardımı anlatır.

Gecikmeli süre cihaz saatine dayanır. Yerel kayıt kullanıcı tarafından
değiştirilebilir; API'de kalıcı oturum/puan/süre zorlaması yoktur. Bu bir yüksek
güvenli sınav sistemi veya deneysel ölçüm altyapısı değildir. Başka çalışmaların
etkisini, soru güçlüğünü ve dış yardımı kullanıcı araştırması ayrıca kontrol eder.

Kayıt bozulursa biçimi doğrulanarak geçersiz alanlar reddedilir. Depolama
kullanılamıyorsa oturum devam eder ve kayıt sınırlaması bildirilir. Paylaşılan
cihaz için bütün atölye kayıtları ve tercihlerini silme düğmesi vardır; yeniden
başlatma yalnız seçili modülün mevcut sürüm kaydını temizler. Belge okuyucusunun
ayrı tekrar geçmişi atölye düğmesiyle silinmez.

## Doğrulama

API:

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

Arayüz (`apps/web` içinde):

```bash
npm ci
npm test
npm run lint
npm run build
npm run test:e2e
```

Tarayıcı testleri ayrı yerel portlarda (18765/18766) gerçek API ve Vite başlatır;
geçici SQLite veritabanı kullanır. API sanal ortamının `apps/api/.venv` altında
kurulu olması gerekir. Linux'ta `/usr/bin/google-chrome` varsa kullanılır;
başka ortamda `npx playwright install chromium` veya
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` gerekir. Kullanıcının çalışan sunucusu yeniden
kullanılmaz; test sunucuları koşum sonunda kapatılır.

Doğrulanan durumlar: seçenek/formül yanıt kontrolü, ipucu sınırı, eski API,
ilk gözlemin korunması, yardımın zamanlaması, biçim ve bağlantı hatası,
yenileme sonrası devam, 24 saat kapısı, yeni gecikmeli sorular, yerel veri silme,
dar ekranda sayfa taşması ve otomatik axe taraması.

İlk koşum: **161 API testi, 13 arayüz birim testi, 4 tarayıcı senaryosu** geçti;
arayüz lint ve üretim derlemesi geçti. Otomatik axe taraması katalog, seçenekli
görev, açık kavram keşfi ve sonuç ekranında ihlal bulmadı. Bunlar gerçek
NVDA/TalkBack/VoiceOver kullanıcı başarısı veya öğrenme etkisi anlamına gelmez.

## Sonraki kabul kapıları

- [Pilot protokolü](ogrenme-atolyesi-pilot.md) ile kullanıcının kendi araçlarında
  görev gözlemi; kritik erişim sorunu ilgili dilimi engeller.
- Özel eğitim/alan uzmanıyla kavram içeriği ve eşdeğer görev zorluğu incelemesi.
- Kaynak-bağlı gerçek ders içeriği için mevcut öğretmen/yayın kalite zinciri.
- Resmî sınav provası için sınav/yıl/aday düzenlemesi ve kurum kaynağı ayrıca
  doğrulanır. Bu atölye LGS/YKS/EKPSS provası diye sunulmaz.
- Araştırma verisi toplanacaksa ayrı rıza ve anonim araştırma kaydı; mevcut
  uygulamaya sessiz telemetri eklenmez.
