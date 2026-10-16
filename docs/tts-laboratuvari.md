# Sunum ve TTS laboratuvarı

Öğrenci uygulaması Kaggle oturumuna bağlı değildir. Web/API/Piper bu
bilgisayardaki Docker Compose ile çalışır; Kaggle yalnız **özel, süreli GPU
deneyi** yapar. Kaggle kapansa da yerel sesli okuma sürer. Chatterbox çıktıları
inceleme tamamlanmadan öğrenci sesine otomatik aktarılmaz.

## Bitirme projesini göstermek

Proje kökünde:

```bash
docker compose up -d --build
docker compose ps
```

Tarayıcı: `http://127.0.0.1:5173`. `api`, `tts`, `web` ve `db` servislerinin
çalıştığını doğrulayın. Sesli keşif için ekrandaki **Sesli keşfi başlat**
düğmesine bir kez basın; tarayıcılar kullanıcı etkileşimi olmadan ses açmaz.
İnternet bağlantısı gerekmez, ancak kaynak PDF'ler ve Docker imajları bu
bilgisayarda önceden bulunmalıdır. Günlük öğrenci akışında Kaggle hesabına
giriş yapılmaz.

## Kaggle ses deneyi: dört kısa komut

Proje kökünde, **tarih ses değerlendirmesi** için:

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py check
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py run
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py status
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py fetch
```

`check` yerel özel giriş dosyasını, kaynak PDF checksum'ını, private GPU
notebook paketini ve Kaggle kimliğini doğrular; GPU tüketmez. `run` açıkça
istendiğinde yalnız 14 kısa değerlendirme cümlesini private Dataset'e yükler,
tek dosyalık Chatterbox V3 notebook'unu gönderir ve GPU işini başlatır.
`status` yalnız durumu okur. Tamamlanan koşu için `fetch` içeriksiz raporları
ve SHA-256 ile doğrulanmış WAV'ları `data/private/` altına getirir; PDF'yi
veya kitabın tamamını indirmez. Notebook tamamlanmadan `fetch` çalıştırmak
kalite sonucu vermez. Aynı deneyi tekrar başlatmak Kaggle kotasını tüketir;
sunum için `run` komutuna gerek yoktur.

Piper karşılaştırma seslerini ve iki modeli kör dinleme sayfasını oluşturmak
için, `fetch` tamamlandıktan sonra:

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_history_local_baseline.py
apps/api/.venv/bin/python experiments/kaggle/tts_history_listening.py
```

İlk komut yalnız bir kez çalışır; var olan sesleri silip yeniden üretmez.
İkinci komut `data/private/tts_history_listening_v1/index.html` dosyasını
oluşturur. Sesler cihazda çevrimdışı dinlenir. Sayfadaki A/B ataması her
örnekte dengeli biçimde rastgeleleştirilir; `mapping.json` sonuçlar toplanana kadar dinleyicilerden
gizli tutulur. Tek dinleyici görüşü modelin öğrenciye yayımlanması için yeterli
değildir.

İsteğe bağlı telaffuz ön elemesi, aynı 28 WAV'ı tek özel Whisper koşusunda
transkribe eder. Bu aşama da yalnız `run` komutunda GPU kullanır:

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_history_asr.py run
apps/api/.venv/bin/python experiments/kaggle/tts_history_asr.py status
apps/api/.venv/bin/python experiments/kaggle/tts_history_asr.py fetch
```

`fetch`, her ses için harf doğruluğu ve kritik tarih/özel adların kaçırılıp
kaçırılmadığını private rapora kaydeder. Whisper hata yapabileceği için bu
puanlar yalnız dinlemede hangi örneğe öncelik verileceğini gösterir; otomatik
yayın eşiği veya dinleyici oyununun yerine geçmez.
[İlk tarih pilotu ve karar notu](tts-tarih-deneyi.md) sonuçları, sınırları ve
dinleme önceliğini kaydeder.

İlk kör dinleme JSON'u eklendiğinde modeli açığa çıkarıp sonuçları saymak için
`tts_history_listening_results.py` kullanılır; tek dinleyici tüm 14 örnekte
Chatterbox'ı tercih etmiştir. Bu sonuç noktalama iyileştirmesi veya öğrenciye
otomatik geçiş anlamına gelmez; ayrıntı ve komut karar notundadır.

Noktalama için ikinci, eşlenik özel deneyi `tts_history_prosody.py` yürütür.
İlk koşuda 10/10 ses doğrulanıp
`data/private/tts_history_prosody_listening_v1/index.html` sayfasına alındı.
Beş A/B çifti dinlendi: özgün noktalama 3, değiştirilmiş noktalama 2 kez
tercih edildi. İkinci yanıtla toplam tercih 5–5 oldu; tutarlı bir üstünlük
çıkmadı. Bu Kaggle koşusu canlı öğrenci
sesine bağlı değildir.

Kaynak harfleri ve kesme eki için sonraki dar kapsamlı Chatterbox deneyi
`experiments/kaggle/tts_history_pronunciation.py` ile üretildi. Üç çiftlik
kör sayfa `data/private/tts_history_pronunciation_listening_v1/index.html`
altındadır. Yerel uygulamada ise yalnız `Kaynak C` ve `Kaynak A'yı` için
ekranda özgün metin korunup ses girdisi ayrıştırılır. Yalın tüm `Kaynak
[harf]` etiketleri Türkçe harf adıyla açılır; ekli biçimler otomatik olarak
tahmin edilmez. Bu, Chatterbox'ın öğrenci uygulamasına geçirildiği anlamına
gelmez.

Eski matematik kalibrasyon koşusuna erişmek için her komuta `--profile stem`
eklenir. Tarih profilindeki 14 cümle kaynak temelli **akustik pilot**
verisidir; kitabın tüm türlerini veya soru bankası özel adlarının tamamını
temsil etmez ve öğretmen onaylı yayın içeriği değildir. Mevcut
[dinleme pilotu](tts-dinleme-pilotu.md) ve gerçek öğrenci görev testi geçilmeden
Chatterbox sesleri öğrenci uygulamasına yayımlanmaz. Model eğitimi/fine-tuning
bu komutların hiçbirinde yapılmaz.

## Ses yolunun sınırı

- Sesli keşif ve öğrenme/soru/yazma düğmeleri, geliştirme modunda yerel
  `interface-speech` API'si üzerinden Piper WAV alır. Uzun metinler kısa
  parçalara ayrılır; başarısızlık tarayıcı sesine sessizce geçmez.
- Doğrulanmış belge okuyucusu önce onaylı kayıt, sonra yerel Piper kullanır.
  Tablo hücresi de yerel API'den okunur. API veya Piper erişilemiyorsa metin
  ekranda ve ekran okuyucuda kalır.
- `interface-speech` üretim ortamında kapalıdır: geliştirme sunumundaki
  `X-Role` başlığı kimlik doğrulaması değildir. Sistemi internete açık
  sunucuya taşımadan önce gerçek kimlik doğrulama, kaynak kullanım izinleri
  ve ses yayın denetimi ayrıca tamamlanmalıdır.
