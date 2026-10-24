# Türkçe TTS kalite araştırması ve deney planı

Bu plan, izinli tek konuşmacı verisiyle Chatterbox Multilingual V3 uyarlaması
içindir. Ham ses, transkript, izin mesajı ve dinleyici kimliği bu repoda
tutulmaz.

## Ne ölçmek istiyoruz

Ses kalitesi tek sayı değildir. Öğrencinin duyduğu deneyim için dört ayrı
boyut ölçülür:

| Boyut | Ölçüm | Karar rolü |
|---|---|---|
| Metin doğruluğu | Kapalı tarih kümesinde Whisper CER ve kritik terim hatası | Zorunlu kapı |
| Ses kimliği | Aynı izinli referansa göre konuşmacı gömme cosine benzerliği | Karşılaştırma ölçütü |
| Doğallık | Kör eşli A/B tercihi; doğallık, akıcılık ve artefact işaretleri | Birincil insan ölçümü |
| Kullanılabilirlik | Süre, gerçek zaman katsayısı, tekrarlı oynatmada önbellek gecikmesi | Dağıtım ölçütü |

Türkçe TTS üzerine güncel çalışma, doğal ses, anlaşılırlık, sinyal kalitesi ve
ses kimliğinin birbirinden farklı çok sayıda ölçüt gerektirdiğini gösterir.
Bu nedenle Whisper sonucu tek başına "iyi ses" ya da "kötü ses" kararı değildir.
Kaynak: [Özköse, Kahraman ve Haznedaroğlu, 2026](https://arxiv.org/abs/2610.06057).

## Uygulanan tasarım

1. **Ayrı referans koşullaması:** Her eğitim hedefi, aynı konuşmacının farklı
   bir kaydından çıkarılan konuşmacı gömmesi ve akustik prompt ile koşullandırılır.
   Üretimde de ses kimliği ayrı referans kayıttan gelir. Böylece eğitim ve
   gerçek kullanım aynı sözleşmeyi kullanır.
2. **Doğru otoregresif hedef:** T3, mevcut tokenı kopyalamak yerine sonraki
   metin ve konuşma tokenını, bitiş tokenı dahil, tahmin eder.
3. **Koruyucu uyarlama:** Çok dilli T3 eğitilir; ses kodlayıcı ve S3Gen
   dondurulur. Türkçe mevcut desteklenen bir dil olduğu için, bu ilk aşamada
   ses üretim zincirini yeniden öğretmekten daha düşük risklidir.
4. **Kademeli eğitim:** 200 adımlık pilot yalnız uyumluluğu doğrular. Tam koşu
   3 saat 15 dakikalık süzülmüş veriyle yapılır; doğrulama kaybı en iyi ara
   checkpoint'i seçer. Öğrenme oranı ısınma ve cosine azalma ile uygulanır.
5. **Referans kalite eşiği:** Tam koşuda referans havuzu en az altı saniyelik,
   clipping olmayan ve yeterli etkin konuşma oranına sahip kayıtlarla
   sınırlandırılacaktır. Bu eşik, modelin altı saniyelik referans penceresiyle
   uyumludur.

Chatterbox'ın resmî uygulaması, ses koşulu için referansın ilk altı saniyesini
ve tüm referans üzerinden konuşmacı gömmesini kullanır. Türkçe `tr` desteklenen
diller arasındadır. [Resmî üretim kodu](https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py), [resmî model açıklaması](https://github.com/resemble-ai/chatterbox/blob/master/README.md?plain=1).

## Kalibrasyon: eğitimden ayrı küçük tarama

Tam eğitim başarılı olursa, aynı kapalı 14 tarih metninde temel ve aday için
tek tek aşağıdaki üretim yapılandırmaları test edilir. Her varyant aynı referans
ve aynı tohumla üretilir.

| Varyant | CFG / pace | Sıcaklık | Exaggeration | Amaç |
|---|---:|---:|---:|---|
| K0 | 0,50 | 0,80 | 0,50 | Resmî varsayılan |
| K1 | 0,35 | 0,70 | 0,50 | Daha yavaş, dengeli anlatım |
| K2 | 0,30 | 0,65 | 0,60 | Biraz daha canlı fakat kontrollü anlatım |

Önce otomatik kapıdan geçen en fazla iki varyant insan dinlemesine gider. Bu,
çok sayıda sesi dinleyiciye yüklemeden üretim parametrelerinin etkisini ölçer.
Chatterbox dokümantasyonu hızlı referans konuşması için daha düşük CFG değerini
ve aşırı ifade düzeylerinin kararsız olabileceğini belirtir. [Resmî çok dilli
arayüz](https://github.com/resemble-ai/chatterbox/blob/master/multilingual_app.py).

## İnsan dinleme çalışması

Kör çalışmada A/B kimliği her metinde dengeli şekilde değiştirilir. Dinleyici
model ismini, eğitim durumunu veya hangi sesin aday olduğunu görmez. Her çift
için şunları yanıtlar:

1. Hangisi daha doğal ve rahat dinlenir? (A / B / eşit / ikisi de değil)
2. Her ses metni doğru okuyor mu? (evet / hayır / emin değilim)
3. Akıcılık ve artefact şiddeti (1--5)
4. İsteğe bağlı hata notu.

İlk proje sahibi dinlemesi kullanıcı kabul testi sayılır. Genel sonuç için en
az beş bağımsız dinleyici ve metin türüne göre dengelenmiş örneklem gerekir;
20 dinleyici hedefi daha güvenilir sıralama için tercih edilir. İnsan
değerlendirmesinde referans yanlılığı ve dinleyici yorgunluğu bulunduğundan,
tek bir MOS puanı yerine kör eşli tercih ve açık yönerge kullanılır. [Varadhan
ve ark., 2024](https://arxiv.org/abs/2411.12719).

## Karar kuralı

Bir aday ancak aşağıdakilerin tümü sağlanırsa öğrenci uygulamasında varsayılan
ses adayı olur:

- tüm kapalı test metinleri üretildi;
- Whisper CER, temel modele karşı 0,5 yüzde puandan fazla kötüleşmedi;
- kritik tarih terimi hatası temel modelden artmadı;
- kör A/B'de aday tercih oranı temel modelden anlamlı biçimde daha yüksek ya
  da en az eşit çıktı;
- ciddi gürültü, aşırı uzunluk veya bitiş tokenı hatası görülmedi.

Bu koşullar sağlanmazsa sonuç başarısızlık değil, ölçülen bir ablation sonucu
olarak rapora yazılır. CV ve sunumda yalnız tamamlanmış deneyin gerçek sayıları
kullanılır.

## Daha büyük veri ve LoRA ablation'ı

Üç saatlik tam koşu, sonraki genişletme için kontrollü temel deneydir. Sonraki
adım, izinli havuzun tamamını doğrudan kullanmak değildir. Önce tüm kayıtlarda
aynı kalite politikasının sonucu, süre dağılımı, ses seviyesi, clipping,
konuşma etkinliği, altı saniyelik referans uygunluğu ve metin uzunluğu
çıkarılır. Bu denetimden sonra yeterli temiz çeşitlilik varsa 6--8 saatlik
ayrı bir eğitim kolu açılır. Aynı kapalı tarih kümesi ve aynı insan dinleme
protokolüyle 3 saatlik koşuya karşı değerlendirilir.

İkinci araştırma kolu, T3 dikkat ve MLP izdüşümlerinde düşük-rank adapter
(LoRA) kullanır. Amaç, 0,5 milyar parametrenin tamamını değiştirmek yerine
az sayıda eğitilebilir parametreyle temel çok dilli davranışı korumaktır.
Bu yaklaşımın TTS uyarlamasında yararlı olduğuna dair yayınlar vardır; fakat
Chatterbox Multilingual V3 için resmî, doğrulanmış LoRA hattı bulunmadığından
bu kol üretim çözümü değil, karşılaştırmalı araştırma deneyi olarak ele
alınacaktır. Community Nano çalışması da bağımsız koşullama, üretimle uyumlu
nedensel hedef ve adapter geri yükleme denetiminin gerekli olduğunu bildirir.
Kaynaklar: [StyleSpeech](https://arxiv.org/abs/2408.14713), [LLM tabanlı
TTS'de veri çeşitliliği ve LoRA](https://arxiv.org/abs/2603.10904),
[Chatterbox Nano deney raporu](https://github.com/resemble-ai/chatterbox/issues/556).
