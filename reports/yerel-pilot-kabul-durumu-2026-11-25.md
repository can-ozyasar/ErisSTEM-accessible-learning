# ErişSTEM yerel pilot kabul durumu — 25 Kasım 2026

Bu rapor, 24 Kasım tarihli 63 soruluk durum özetinin yerine geçen güncel teknik
kayıttır. Kontrollü yerel pilot kapsamındadır; bağımsız kullanıcı başarısı,
öğrenme etkisi veya insan öğretmen eşdeğerliği iddiası değildir.

## Doğrulanan teknik kanıt

| Alan | Sonuç | Sınır |
| --- | --- | --- |
| Aktif AYT Tarih paketi | 81 soru; kök/5 şık eşleşmesi 81/81, cevap anahtarı tutarlılığı 81/81; görsel bağımlılık işareti 0 | Sağlanan anahtarın tarihsel doğruluğunu veya öğretmen onayını kanıtlamaz |
| PDF metin/kırpım denetimi | 619 soru metni karşılaştırması; en düşük token geri çağırımı 0,9167; 165 kanıt kesitinde eşik altı 0 | Kayıtlı sayfa/bbox içindeki PDF metin katmanı denetimidir; insan görsel incelemesi değildir |
| Uçtan uca özel paket E2E | 4/4 senaryo geçti; klavye ile sınav→koç→silme; axe ihlali 0 | NVDA/TalkBack veya katılımcı testi yerine geçmez |
| Oturum güvenilirliği | 100 stres oturumu; 100 cevap tekrarının reddi; 100 idempotent teslim; geçici oturumlar silindi | Bu otomatik test koşusunun kapsamıdır |
| Canlı soru sesi | Gerçek 81 soruluk oturumda Piper rotası HTTP 200; geçerli WAV 320.044 bayt; geçici oturum HTTP 204 ile silindi | Tek soru kökü isteği; paket genelinde insan telaffuz değerlendirmesi değildir |
| Koçluk TTS gecikmesi | Yerel Ryzen 7 5700U üzerinde 5 örnek; tam WAV yanıtı p50 1.928 ms, p95 2.315 ms | Küçük örnek, tek cihaz; akışta ilk ses süresi değildir |
| Fine-tune sabit ses adayı | Kaggle T4: 387/387 WAV checksum ve çözümleme geçti; üretim süresi metin başına p50 3.766 ms, p95 20.216 ms; sessiz/kırpılmış kayıt 0 | Teknik dalga biçimi taraması telaffuz/doğallık değildir; V5 kapalı ve dinleyici incelemesi bekliyor |
| Yerel ses inceleme sayfası | 387 ses kontrolü; filtre eşleşme/temizleme akışı ve yerel WAV metadata yüklemesi geçti; axe WCAG taramasında ihlal 0 | Otomatik Chrome testi; ekran okuyucu veya dinleyici onayı değildir |
| Web/API regresyonları | Web: build, lint, 16 birim testi ve özel E2E geçti. API: 867 test geçti, 0 başarısız/atlanan | Ayrı koşular ve commit’ler; ayrıntı JSON kabul raporundadır |
| DeepSeek güvenlik kapısı | Varsayılan kapalı; kaynak işleme yetkisi varsayılan kapalı; öğrenci izni istenir | Gerçek öğrenci veya MEB içeriğiyle canlı kullanım etkin değildir |

## TTS ve model kararı

Aktif paketin 504 sabit ses birimi için önceki yerel ses adaylarında tam eşleşme
0/504 bulundu. Bu nedenle öğrenci yolunda yerel Piper korunuyor. Özel Kaggle V3
koşusu 25 Kasım 13:03:51 UTC’de tamamlandı. Yalnız minimize özel manifest
yüklendi; öğrenci verisi ve kaynak PDF’leri yüklenmedi. Beklenen 387 benzersiz
rakam içermeyen metin için 387/387 WAV üretildi; SHA-256, dosya boyutu ve
mono 24 kHz PCM çözümlemesi doğrulandı. Bu teknik kontroller telaffuz veya
doğallık onayı değildir. Kayıtlar 487 statik birime bağlandı ve kapalı aday
paketinde tutuluyor. Dalga biçimi taramasında sessiz veya eşik üstü kırpılmış
kayıt bulunmadı; bu yine de doğru telaffuz anlamına gelmez. Yerel dinleme sayfası
`data/private/tts-v5-ayt-static-candidate-2026-11-25/listener-review-v2.html`.
Dinleyici incelemesi ve lisans kontrolü tamamlanmadan çalışma zamanında
kullanılmayacak.

QLoRA adaptörü ve RAG araştırması da öğrenci çalışma zamanında etkin değildir.
QLoRA'nın önceki 11-vaka sentetik base/adaptör taramasındaki iki adaptör dosyasının
SHA-256 değerleri güncel artefakt manifestiyle şimdi doğrulandı. Adaptör erken
cevap ifşasında 0/8 olsa da kanıt yokken çekimserlik 0/1 olduğu için kabul
edilmedi; aynı ayrılmış 144 geliştirme örneğindeki tam karşılaştırma hâlâ
bekliyor. Bu örnekler gözlemlenmiş öğrenci yanıtları değildir.
RAG karşılaştırması ayrı 24 sorgulu araştırma bölmesinde pooled-top-3
değerlendirmesidir; dense/RRF Recall@3 değeri BM25’ten 0,0417 yüksek olsa da bu
sonuç aktif 81 soruya veya tam korpusa genellenemez. Semantik yakın-kopya ve
insan alan uzmanı incelemesi tamamlanmamıştır.

## Açık kabul kapıları

- Hazır dinleme sayfasında istenen V5 kayıtlarını dinleyip anlaşılabilirlik,
  telaffuz ve artefakt alanlarını işaretlemek; tamamlanan JSON'u daha sonra
  onay aracına vermek. İncelenmeyen sesler ve rakamlı 17 birim Piper'da kalacak.
- NVDA+Firefox ve TalkBack+Chrome üzerinde görev listesini gerçek cihazlarda
  tamamlamak. Mevcut geliştirme makinesinde Firefox/NVDA ve bağlı Android cihaz
  yoktur.
- Görme engelli katılımcıyla erişilebilir başlangıç, soru çözme, gezinme, teslim
  ve koçluk görevlerini gözlemlemek; katılımcı çalışması olmadan kullanıcı
  başarısı iddia etmemek.
- Kaynak kullanım yetkisi ve veri işleme temeli belgelenmeden gerçek MEB
  içeriğini DeepSeek’e göndermemek; mevcut dış model kapısı kapalı kalmalıdır.

## İzlenebilirlik

- Makinece okunur ayrıntı: `reports/ayt-private-pilot-acceptance-v1.json`
- Aktif paket SHA-256: `a36ffb0331cc42d4ad138a996cee722bec62cd73ac92bbb6093e349f2fd052e3`
- PDF soru kaynağı SHA-256: `6ec38cd1be903f51c60e4f7f8829a7a88c5da79d0a4ec2c7ae00e3e3c5aac959`
- Kanıt kesitleri PDF denetim raporu SHA-256: `1cc5d9c6d43c432443a19ec5cd199da8a8484faec4f1e6c804b18f19c243eb8d`
- Otomatik özel-paket E2E kaynak commit’i: `7d57cf236f74e8b9e218c734e91217a1d0694498`
- Gerçek Piper soru isteği API kaynak commit’i: `7d57cf236f74e8b9e218c734e91217a1d0694498`

Özel veri içerikleri ve `.env` bu rapora veya Git’e eklenmemiştir.
