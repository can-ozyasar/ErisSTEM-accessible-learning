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
| Web/API regresyonları | Web: build, lint, 16 birim testi ve özel E2E geçti. API: 867 test geçti, 0 başarısız/atlanan | Ayrı koşular ve commit’ler; ayrıntı JSON kabul raporundadır |
| DeepSeek güvenlik kapısı | Varsayılan kapalı; kaynak işleme yetkisi varsayılan kapalı; öğrenci izni istenir | Gerçek öğrenci veya MEB içeriğiyle canlı kullanım etkin değildir |

## TTS ve model kararı

Aktif paketin 504 sabit ses birimi için önceki yerel ses adaylarında tam eşleşme
0/504 bulundu. Bu nedenle öğrenci yolunda yerel Piper korunuyor. Kaggle’daki
V5 sabit-ses üretim koşusu 25 Kasım 12:53 UTC kontrolünde hâlâ `RUNNING` idi;
çıktı alınmış veya kalite kapısından geçmiş sayılmamalıdır. V3 koşusunun girdisi
özel paket metaverisiyle sınırlandırılmıştır; öğrenci verisi ve kaynak PDF’leri
yüklenmemiştir. Üretilen her ses için eşleşme ve dinleme kapısı tamamlanmadan
çalışma zamanında kullanılmayacaktır.

QLoRA adaptörü ve RAG araştırması da öğrenci çalışma zamanında etkin değildir.
RAG karşılaştırması ayrı 24 sorgulu araştırma bölmesinde pooled-top-3
değerlendirmesidir; dense/RRF Recall@3 değeri BM25’ten 0,0417 yüksek olsa da bu
sonuç aktif 81 soruya veya tam korpusa genellenemez. Semantik yakın-kopya ve
insan alan uzmanı incelemesi tamamlanmamıştır.

## Açık kabul kapıları

- Kaggle V3 terminal durumunu beklemek; yalnız tamamlanırsa çıktıları indirmek,
  checksum/WAV/metin eşleşmesini doğrulamak ve dinleme onay kuyruğuna almak.
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
