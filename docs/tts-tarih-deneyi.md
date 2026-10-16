# Tarih TTS akustik pilotu — 15 Ekim 2026

## Kapsam ve sonuç

MEB 9. sınıf tarih kitabının 40–42. sayfalarından seçilen 14 kısa, kaynak
temelli test cümlesi üzerinde yerel Piper `tr_TR-dfki-medium` ve private
Kaggle T4'te Chatterbox Multilingual V3 karşılaştırıldı. Bu cümleler yayın
içeriği veya eğitmen onaylı Gold değildir; PDF'deki bölünmüş sözcükler
akustik deneme için düzenlenmiştir. PDF veya tüm soru bankası Kaggle'a
yüklenmedi. Girdi SHA-256'sı, sentez raporları ve WAV checksum'ları eşleşti.

| Ölçüm | Piper | Chatterbox V3 |
|---|---:|---:|
| Üretilen WAV | 14/14 | 14/14 |
| Whisper large-v3 transkript | 14/14 | 14/14 |
| Ortalama normalleştirilmiş karakter eşleşmesi | 0,948 | 0,955 |
| Kritik ifade için birebir ASR-token uyuşmazlığı bulunan örnek | 7/14 | 7/14 |

Bu küçük örnekte Chatterbox'ın otomatik metin skoru yalnız 0,007 yüksek.
Bu fark doğal konuşma kalitesi, anlaşılabilirlik veya öğrenci güvenliği
açısından üstünlük kanıtı değildir. Uyuşmazlıkların bir kısmı ASR'nin
`birinci`/`1.`, `altıncı`/`6.` ve çekimli özel adları farklı yazmasından
kaynaklanabilir. Özellikle kaynak harfleri ve yabancı özel adlar insan
dinlemesinde kontrol edilmelidir.

## İlk kör insan dinlemesi

`history-listener-canoz.json` dosyasındaki 14/14 yanıt, kaynak manifesti ve
gizli A/B eşlemesiyle doğrulandı. Dinleyici **14 örneğin tamamında Chatterbox'ı
daha doğal** buldu ve hepsinin metni doğru okuduğunu işaretledi. Piper için
5 `evet`, 7 `hayır`, 2 `emin değilim` yanıtı var. Bu, yukarıdaki yakın ASR
puanlarının doğal ses tercihini açıklamadığını gösterir. Ancak bu **tek
dinleyicinin**, yalnız 40–42. sayfalardan seçilmiş 14 kısa örneğe dayanan
sonucudur; istatistiksel genelleme, tüm kitapta doğruluk veya öğrenci
erişilebilirliği kanıtı değildir. Serbest notlar boş olduğundan hangi
noktalama/duraklamaların sorunlu olduğu bu JSON'dan çıkarılamaz.

Tekrar üretilebilir çözümleme:

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_history_listening_results.py \
  --manifest data/private/eristem_history_tts_eval_v1/tts-history-eval-v1.json \
  --mapping data/private/tts_history_listening_v1/mapping.json \
  --responses data/private/tts_history_listening_v1/history-listener-canoz.json
```

## Noktalama karşılaştırması

`experiments/kaggle/tts_history_prosody.py`, beş kaynak cümle için özgün ve
yalnız noktalama/büyük harf farkı olan sürümleri aynı private Chatterbox
koşusunda üretir. Kod sözcük dizisinin değişmediğini doğrular; 10 WAV'ın
checksum'ları eşleşmeden dinleme paketi oluşturmaz. Bu deney akustik pilot
olarak kalır; tarih içeriğini veya canlı öğrenci sesini değiştirmez.

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_history_prosody.py prepare
apps/api/.venv/bin/python experiments/kaggle/tts_history_prosody.py run
apps/api/.venv/bin/python experiments/kaggle/tts_history_prosody.py status
apps/api/.venv/bin/python experiments/kaggle/tts_history_prosody.py fetch
```

`run` bir kez private Dataset yükler ve GPU notebook'unu başlatır. Dataset
yüklenip notebook gönderimi başarısız olursa `push` komutu yalnız notebook'u
yeniden gönderir; aynı veri kümesini tekrar yüklemez. `fetch` tamamlanmış
koşudan kör A/B dinleme sayfasını private klasöre çıkarır. Dinleyicilerden
her çift için somut duraklama/telaffuz notu istenir.

İlk koşuda **10/10 WAV** üretildi ve checksum doğrulamasından geçti.
Dinleme sayfası `data/private/tts_history_prosody_listening_v1/index.html`;
beş çiftte noktalama sürümü A'da üç, B'de iki kez yer alır. Henüz insan
dinleme yanıtı yoktur; bu nedenle noktalama değişikliğinin iyileşme sağladığı
iddia edilmez. Tek üretim/çift, modelin örnekleme rastlantısını da tamamen
ayıramaz.

`history-prosody-canozyasar.json` yanıtı kaynak checksum'ı ve A/B eşlemesiyle
çözümlendi: özgün noktalama 3/5, değiştirilmiş noktalama 2/5 kez tercih
edildi. Metne sadakat özgün için 4/5, değiştirilmiş için 3/5 `evet` olarak
işaretlendi. Noktalama için tutarlı bir üstünlük yok. Somut notlarda `Kaynak
C` harfi bazen `ci/ji/çi` gibi, `Kaynak A'yı` ise `ayı` gibi duyuluyor.
İkinci soru için formda iki ses de doğru işaretli olsa da serbest not yalnız
B'nin doğru olduğunu söylüyor; bu kayıt kesin telaffuz puanı sayılmaz.
Sorun, noktalama yerine **kaynak etiketi ve kesme eki için konuşma metni
normalizasyonu** gerektiriyor.

16 Ekim'de eklenen `history-prosody-canoz.json` aynı **noktalama** paketinin
ikinci yanıtıdır; yeni telaffuz paketine ait değildir. İki yanıt birlikte
çözümlendiğinde tercih **5 özgün / 5 değiştirilmiş**, metne sadakat işareti
özgün için 5/10, değiştirilmiş için 6/10 `evet` olur. İki dinleyici kodunun
bağımsız iki kişi olduğu doğrulanmadığından örneklem büyüklüğü diye
yorumlanmaz. Yeni formdaki `history-caption-02` notu, seçilen A ile
çelişerek “B daha iyi” diyor; böyle kayıtlar kesin tercih kanıtı değildir.
Her iki formda da `Kaynak C` ve `Kaynak A'yı` telaffuzuna dair olumsuz notlar
bulunur.

Geliştirme okuyucusuna yalnız gözlenen iki kalıp için dar kapsamlı bir
konuşma biçimi eklendi: ekranda `Kaynak C` kalırken ses girdisi `Kaynak ce`,
`Kaynak A'yı` kalırken `A kaynağını` olur. Başka harfler, yabancı özel adlar
ve ekler tahmin edilmez. Bu değişiklik yerel Piper yolundadır; Chatterbox
pilotunda düzelmenin dinleyici tarafından doğrulandığı anlamına gelmez.

Bu nedenle `tts_history_pronunciation.py` ile aynı Chatterbox modelinde
ayrı bir 3 çift/6 seslik özel telaffuz pilotu hazırlanır. İki farklı `Kaynak
C` bağlamı ve bir `Kaynak A'yı` sorusunda özgün ve yalnız konuşma için
normalleştirilmiş metin aynı GPU koşusunda sentezlenir. Ses dosyaları
doğrulanmadan dinleme sayfası açılmaz; A/B kimlik eşlemesi sayfadan ayrıdır.
Bu deney sonucu ve dinleyici doğrulaması olmadan Chatterbox canlı ses yapılmaz.
İlk koşu 6/6 WAV üretti; kaynak hash'i ve her WAV checksum'ı eşleşti.
Kör dinleme sayfası:
`data/private/tts_history_pronunciation_listening_v1/index.html`.
Üç çiftte normalleştirilmiş ses iki kez A, bir kez B olarak gizlendi.
Dinleyici formunda kaynak harfi ve anlam doğruluğu ayrı işaretlenir;
her örnek için somut telaffuz notu gerekir. Sonuç JSON'u eklendiğinde
`tts_history_pronunciation_results.py` yalnız eşleşen manifest ve A/B
haritasıyla puanlar.

İlk telaffuz yanıtında normalleştirilmiş sürüm 2/3 kez tercih edildi;
doğruluk işareti normalleştirilmişte 2 `evet`, 1 `emin değilim`, özgün
sürümde 1 `evet`, 2 `hayır` oldu. `Kaynak C` için sonuç bağlama göre
değişti: ikinci soruda normalleştirilmiş ses doğru duyuldu, başlıktaki kısa
etikette ise kararsız kaldı. `A kaynağını` ifadesi `Kaynak A'yı` sorununu
azalttı fakat cümle sonunda akıcılık notu aldı. Bu üç kayıt model değişimi
için yeterli değildir.

Yerel okuyucuda ayrı bir güvenli iyileştirme uygulanır: yalın `Kaynak
[harf]` etiketleri (A–Z ile Ç, Ğ, I, İ, Ö, Ş, Ü) ses girdisinde Türkçe harf
adıyla açılır. Kesme eki içeren biçimler (`Kaynak H'den` gibi) otomatik
tahmin edilmez; yalnız doğrulanmış `Kaynak A'yı` kalıbı dönüştürülür. Görsel
metin her durumda kaynağın özgün biçiminde kalır.

### Kitap geneli risk envanteri

Yerel MEB PDF'sinin 10–263. sayfalarına kaynak SHA-256'sına bağlı, yalnız
private bir metin örüntüsü taraması uygulandı. Sonuç
`data/private/tts_history_lesson_coverage_v2.json` içindedir. `Kaynak
[harf]` biçimi 73 sayfada 222 kez görünür ve A–Z yanında Ç, Ğ, I, İ, Ö,
Ş, Ü gibi Türkçe harfler içerir. 213 sayfada kesme eki örüntüsü, 169 sayfada
yıl/yıl aralığı, 129 sayfada kısaltma örüntüsü bulunur. Bu sayılar **ses
hatası sayısı değildir**; PDF metin katmanında yanlış karakter ve sayfa
mobilyası kalabildiği için örnekler görselle doğrulanmadan TTS Gold olamaz.
Bu envanter, sonraki değerlendirme kümesini farklı harfler, ekler, tarihler,
Romen rakamları ve özel adlardan dengeli seçmek içindir. Kitabın tamamına
yalnız iki telaffuz kuralını yaymak yeterli kabul edilmez.

### Deneyin sınırı

Metindeki tarihsel bilgiye dokunmadan, yalnız **okuma metninin** noktalama ve
duraklama biçimini karşılaştırıyoruz: kaynak etiketi (`Kaynak C.` / `Kaynak C:`),
soru başlangıcı (`Birinci soru.` / `Birinci soru:`), uzun cümlede nefes
grupları ve yabancı özel ad. Her çift aynı model, referans ses ve metin
sözcükleriyle üretilmeli; yalnız noktalama değişmeli. A/B sırası kör ve
dengeli olmalı, telaffuz doğruluğu ile doğallık ayrı sorulmalı, her örnek için
somut hata notu istenmeli. Kontrol sürümü aynı koşuda yeniden üretilmeli;
ayrı GPU koşularındaki ses farkı noktalama etkisi sanılmamalı. Başarılı bir
değişiklik, yeni dinleyici sonuçları olmadan üretim okumasına taşınmamalı.

## Dinleme ve karar

Kör dinleme sayfası:
`data/private/tts_history_listening_v1/index.html`.
Her örnekte A/B sırası dengeli rastgeleleştirilmiştir; kimlik eşlemesi ayrı
private `mapping.json` dosyasındadır. Dinleyici ses doğallığını ve metne
sadakati ayrı işaretler. En az birkaç bağımsız dinleyicinin yanıtı ve
ekran okuyucu kullanan bir öğrenci görevi olmadan ses varsayılanı değişmez.

Önce `history-caption-01`, `history-caption-02`, `history-question-01`,
`history-question-04` ve `history-name-01` dinlenmelidir. Bunlar harf, tarih
veya özel ad açısından uyarı veren örneklerdir. Dinleyici sonucunda baskın
sorun telaffuz değilse, fine-tune gereksiz olabilir; metin normalizasyonu,
doğru referans ses ve okuma biçimi ayarları daha az riskli ilk düzeltmedir.

## Fine-tune kararı

Bu pilot **fine-tune başlatmaz**. Chatterbox V3'ün açık deposu Türkçe
çıkarımı ve referans ses kullanımını belgeler, ancak resmî, tekrarlanabilir
Türkçe fine-tune hattı ürün varsayılanı olarak kabul edilmemiştir. Açık
Türkçe [Common Voice verisi](https://commonvoice.mozilla.org/cnh/datasets)
CC0 olarak listelenir; çok konuşmacılı ASR klipleri, tek ve duygulu anlatıcı
verisiyle eşdeğer değildir. Gerekirse izinli yetişkin tek-konuşmacı kayıtları,
ayrı eğitim/değerlendirme bölümleri ve önce/sonra kör dinleme karşılaştırması
ile eğitim denenecektir. Mevcut referans sesinin
[veri kartı](https://huggingface.co/datasets/omersaidd/tts_nisan_kumru_tur)
MIT etiketi taşısa da kartın içerik ve ses rızası açıklaması sınırlıdır;
öğrenciye yayımlanacak bir ses kimliği olarak otomatik kabul edilmez.

Private çalışma artefact'ları `data/private/eristem_history_tts_eval_v1/`,
`data/private/tts_history_piper_v1/`, Kaggle çıktı klasörü ve
`data/private/tts_history_asr_scores_v1.json` altında kalır. Ses modelini
değiştirmek için öğrenci uygulamasında bu pilotun çıktısı kullanılmaz.
