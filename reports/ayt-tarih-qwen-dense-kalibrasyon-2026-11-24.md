# Qwen dense kaynak bulma kalibrasyonu — 24 Kasım 2026

## Amaç ve sınır

Bu çalışma, kaynak kanıtı eksik olduğu için yerel pilotun dışında tutulan 84
OGM AYT Tarih sorusunda Qwen3 Embedding 4B dense retrieval'ın, önceki BM25
+ RRF challenger'a göre daha çok **tam kaynak demeti adayı** getirip
getirmediğini test eder. Bu bir cevap doğruluk, insan öğretmen onayı veya
öğrenciye yayın kararı değildir.

- Sorgular, cevap anahtarı ve çözüm metni kullanılmadan üretildi.
- Kaynak havuzu dört checksum-bağlı yerel MEB kitabından oluştu.
- GPU koşumu Kaggle T4 üzerinde tamamlandı; sonuç manifesti yerelde
  `ogm-ayt-abstained-qwen-dense-rankings-v1.json` olarak doğrulandı.
- Ardından aynı 12 soru, kaynak kesitleriyle ve cevap anahtarına erişim
  olmadan iki ayrı DeepSeek çağrısına sunuldu.

## Karşılaştırılabilir kalibrasyon sonucu

Her iki yöntem de aynı, önceden sıralanmış 12 adayda ve aynı top-12 aday
bütçesinde değerlendirildi.

| Yöntem | Tam kapsam | Çekimser | Not |
| --- | ---: | ---: | --- |
| Önceki BM25 + RRF challenger | 1 / 12 | 11 / 12 | İlk kaynak-kapsam kalibrasyonu |
| Qwen3 Embedding 4B dense | 4 / 12 | 8 / 12 | İlk DeepSeek incelemesi |
| Qwen3 Embedding 4B dense | 4 / 12 | 8 / 12 | İkinci DeepSeek incelemesi |

İki dense incelemesinin `coverage_complete` kararları 12/12 eşleşti. Tam
kapsam bulunan dört soruda seçilen kanıt kimlikleri de iki incelemede kesişti.
Bu, yalnız bu kalibrasyon örnekleminde dense retrieval'ın RRF challenger'dan
daha umut verici adaylar getirdiğini gösterir; 84 sorunun tamamına ya da
öğretim kalitesine genellenemez.

## Gecikme

Kaggle T4 koşumunun 84 sorgudaki ölçümü:

| Aşama | p50 | p95 |
| --- | ---: | ---: |
| BM25 | 70.105 ms | 152.181 ms |
| Qwen dense | 179.293 ms | 281.608 ms |
| RRF birleştirme | 8.019 ms | 8.835 ms |

Bu gecikmeler araştırma hattına aittir; öğrenci çalışma anındaki koçluk yolu
değildir.

## Karar

Kalibrasyondan sonra tüm 84 aday, cevap anahtarı erişimsiz ilk kaynak-kapsam
incelemesine alındı. Sonuç 19 tam kapsam / 65 çekimser oldu. Tam kapsam görünen
19 aday `deepseek-reasoner` ile ikinci kez incelendi: 18 tam kapsam / 1
çekimser. Tek anlaşmazlık için ayrı üçüncü karar alındı ve çekimserlik yönünde
sonuçlandı. Böylece iki–üç karar kuralıyla **18 aday**, kaynak kanıtı bakımından
AI uzlaşması sağladı; 1 aday dışarıda kaldı.

Bu uzlaşma insan öğretmen veya pedagojik yayın onayı değildir. 19 adayın tamamı
üçer checksum-bağlı MEB PDF kesitiyle yerel inceleme paketine dönüştürüldü
(`57` PNG kesiti). Bu paket, özellikle tek uyuşmazlık vakasının da yeniden
görülebilmesi için 19 adayı korur.

Dense retrieval, kalan adaylarda kaynak incelemesi için seçili araştırma
koludur. Ancak hiçbir aday otomatik olarak pilot pakete eklenmez. Sıradaki
kapılar şunlardır:

1. PDF kesitlerini kaynak metni ve soru için gerekli iddialarla karşılaştırmak;
   kanıt yetersizse soruyu dışarıda tutmak.
2. Yalnız PDF/kaynak doğrulaması tamamlanan adayları ayrı, sürümlü aday pakete
   koymak.
3. Bu paketi mevcut 63 soruluk yerel pilotla karıştırmadan önce kaynak,
   transkripsiyon ve erişilebilirlik kapılarını tekrar çalıştırmak.
4. PDF/kaynak doğrulaması tamamlanmadan runtime paketi, cevap anahtarı,
   koçluk verisi veya QLoRA verisini değiştirmemek.

İlgili private artefaktlar:

- `ogm-ayt-abstained-qwen-dense-rankings-v1.json`
- `ogm-ayt-abstained-qwen-dense-review-queue-v1.json`
- `deepseek-ogm-abstained-qwen-dense-calibration-v1.json`
- `deepseek-ogm-abstained-qwen-dense-calibration-second-v1.json`
- `deepseek-ogm-abstained-qwen-dense-first-pass-v1.json`
- `ogm-ayt-abstained-qwen-dense-ai-consensus-v1.json`
- `ogm-ayt-abstained-qwen-dense-pdf-review-v1/manifest.json`
