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

Proje kökünde, mevcut özel benchmark profili için:

```bash
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py check
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py run
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py status
apps/api/.venv/bin/python experiments/kaggle/tts_lab.py fetch
```

`check` yerel özel giriş dosyasını, private GPU notebook paketini ve Kaggle
kimliğini doğrular; GPU tüketmez. `run` açıkça istendiğinde private Chatterbox
V3 notebook'unu gönderir ve GPU işini başlatır. `status` yalnız durumu okur.
`fetch` yalnız içeriksiz özet raporları `data/private/` altına getirir; WAV,
PDF veya ham ders metnini indirmez. Notebook tamamlanmadan `fetch` çalıştırmak
kalite sonucu vermez. Aynı deneyi tekrar başlatmak Kaggle kotasını tüketir;
sunum için `run` komutuna gerek yoktur.

Bu hazır profilin 60 örneği **matematik ağırlıklı sentetik kalibrasyon**
verisidir. Tarih kitabının veya soru bankasının ses kalitesini kanıtlamaz.
Tarih için kaynakça ve soru türleri dengeli, insan doğrulamalı ayrı bir
değerlendirme kümesi hazırlanacak; aynı özel Notebook ve dinleyici sürecinde
karşılaştırılacaktır. Mevcut [dinleme pilotu](tts-dinleme-pilotu.md) geçilmeden
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
