# ADR 0016: Türkçe STEM TTS için katmanlı aday seçimi

Durum: Kabul edildi.

## Bağlam

ErişSTEM'in hedefi, PDF'den ham metni konuşmak değil; doğrulanmış kanonik
erişilebilirlik bloğunun tür-özel sesli temsilini sunmaktır. Bir paragraf,
formül, tablo veya grafik için ses motorunun girdi metnini değiştirmesine ya da
yeni açıklama uydurmasına izin verilmez. Ses motoru yalnız yayıma uygun
`spoken_text` birimini ses dosyasına dönüştürür.

Yerel geliştirme makinesi AMD Ryzen 7 5700U, yaklaşık 13 GiB RAM ve NVIDIA
CUDA GPU'su olmadan çalışmaktadır. Bu makine web/API geliştirmesi, tarayıcı
TTS'i ve küçük ONNX çıkarımı için uygundur; büyük çok dilli TTS modellerini
eğitmek veya düşük gecikmeyle çalıştırmak için uygun kabul edilmez.

## Karar

TTS üç ayrı katmanda ele alınacaktır:

1. **Geliştirme erişilebilirliği — tarayıcı/işletim sistemi sesi.** Mevcut
   öğrenci okuyucusundaki Web Speech kullanımı yalnız doğrulanmış okuma
   planındaki birimleri konuşur. Bu katman ücretsiz işlevsel tabandır; ses
   kalitesi veya matematik sesletimi için yayın onayı değildir.
2. **Yerel, hafif aday — Türkçe Piper/ONNX.** Türkçe desteği bulunan bir Piper
   sesi, ayrı bir yerel HTTP/ONNX servisinde yalnız benchmark adayı olarak
   denenir. Her sesin model kartı ve kullanım lisansı tek tek incelenmeden
   dağıtıma alınmaz. Güncel Piper kodu GPL-3.0-or-later olduğundan uygulamaya
   gömülmez ve lisans incelemesi tamamlanmadan ürün varsayılanı seçilmez.
3. **Kalite adayı — Chatterbox Multilingual.** Türkçe (`tr`) destekleyen
   0.5B çok dilli model yalnız Kaggle T4 veya CUDA'lı geçici altyapıda
   karşılaştırma için çalıştırılır. İlk tekrarlanabilir PyPI baseline'ı V2
   varsayılanını kullanır; V3, ancak kaynak sürümü ve API'si ayrıca pinlenmiş
   bir deneyde değerlendirilir. Bu aday daha doğal ses potansiyeli taşır;
   ancak ağırlık/model kartı, ses klonlama güvenliği, filigran ve gecikme
   sonuçları ayrıca kabul edilmelidir. Kod lisansının MIT olması, model
   ağırlıklarının veya ses verisinin otomatik olarak ürün için uygun olduğu
   anlamına gelmez.

Varsayılan ürün mimarisi istemci cihazında büyük model çalıştırmaz:

```
doğrulanmış okuma planı
          -> tür-özel spoken_text
          -> seçilmiş TTS adaptörü
          -> checksum'lı, private ses önbelleği
          -> öğrenci oynatıcısı
```

Ses önbelleği kaynak blok kimliği, sözleşme sürümü, ses motoru sürümü ve ayar
profiline bağlı olur. Kanonik içerik veya konuşma sözleşmesi değiştiğinde eski
ses kullanılmaz. Ham MEB içeriği ya da öğrenci verisi dış bir TTS API'sine
gönderilmez.

## Fine-tuning kararı

Fine-tuning **başlatılmamıştır**. Mevcut `tts-gold-v1`, aday sesleri sınamak
için yazı-temelli sesletim referansıdır; eğitim verisi değildir. Eğitim için
aşağıdakilerin tamamı gerekir:

- yazılı kullanım izni olan, tekil ve yetişkin bir konuşmacı;
- konuşmacıya ait temiz kayıtlar, transkriptler ve geri çekme/silme prosedürü;
- Türkçe matematik, tablo ve grafik konuşmasını kapsayan ayrı eğitim/validation
  bölümleri;
- ses klonlamayı önleyen veya açık rıza ile sınırlayan ürün politikası;
- mevcut baseline'a göre kör dinleyici testinde ölçülebilir iyileşme.

Bu koşullar sağlanmadan fine-tuning, faydadan çok gizlilik, lisans ve kalite
riski yaratır.

## Ölçüm ve kabul sırası

1. Private `tts-gold-v1` en az 50 örneğe çıkarılır: doğrudan metin, formül,
   tablo gezinmesi, grafik özeti ve alıştırma dengeli temsil edilir.
2. Aynı Gold üzerinde tarayıcı sesi, lisansı uygun Piper adayı ve CUDA'da
   Chatterbox adayı karşılaştırılır.
3. Otomatik kapı: en az %98 sesletim doğruluğu ve kritik matematik
   belirteçlerinde %100 doğruluk. Eksik örnek de başarısızlıktır.
4. Otomatik kapıyı geçen aday NVDA+Firefox ve TalkBack+Chrome ile kör görev
   testine girer; öğrencinin formül/tablo/grafiği anlayabilmesi ölçülür.
5. Ancak iki kapıyı geçen aday ses adaptörü ve önbelleğiyle ürünleştirilir.

TTS, içerik doğruluğunun yerine geçmez: kaynak/şema/render/Goldu geçmeyen blok
seslendirilmez.

## Donanım sonucu

Şimdi GPU satın alma veya bulma kararı verilmemiştir. Önce iki aday aynı Gold
ile ölçülür. Yerelde küçük ONNX adayını deneyip ses önbelleği geliştirmek için
mevcut bilgisayar yeterlidir. 0.5B çok dilli adayın karşılaştırması ve olası
ince ayarı için CUDA GPU gerekir; Kaggle T4 bunun kısa süreli benchmark
ortamıdır, üretim sunucusu değildir. Yerel CUDA'lı altyapı gerekecekse önce
hedef eşzamanlı kullanıcı sayısı ve ölçülen gecikme belirlenecek; bu bilgi
olmadan VRAM kapasitesi satın alma kriteri yapılmayacaktır.

## Kaynaklar

- [Piper sesleri ve model kartı/lisans notu](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md)
- [Piper paket lisansı](https://github.com/OHF-Voice/piper1-gpl/blob/main/setup.py)
- [Chatterbox Multilingual V3 özellikleri](https://github.com/resemble-ai/chatterbox/blob/master/README.md)
- [Chatterbox açık kaynak Türkçe dil kodu](https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py)
- [Chatterbox kod lisansı](https://github.com/resemble-ai/chatterbox/blob/master/LICENSE)
