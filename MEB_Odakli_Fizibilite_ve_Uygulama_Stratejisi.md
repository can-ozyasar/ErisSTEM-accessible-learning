# MEB Odaklı Erişilebilir STEM Projesi: Fizibilite ve Uygulama Stratejisi

**Karar özeti:** Hedefi İngilizce akademik makalelerden MEB ortaöğretim STEM ders kitaplarına çevirmek, proje etkisini ve gerçek kullanıcının ürünü kullanabilme olasılığını artırır. İlk teslim, **9. sınıf Matematik** kitabının seçilmiş ünitelerini; ikinci doğrulama alanı ise bir **9. sınıf Fizik** ünitesini kapsamalıdır. Bu seçim, Türkçe matematik okunuşu ve erişilebilir STEM materyali boşluğuna doğrudan odaklanır.

Bu belge, `Tam_Kapsamli_Proje_Plani.md` içindeki geniş araştırma programını, 30 saat Kaggle T4 GPU ile teslim edilebilir ve ölçülebilir bir ürüne dönüştürür. Özellikler iptal edilmemiş, çekirdek ürün ve sonraki fazlar olarak sıralanmıştır.

---

## 1. MEB kitabı mı, akademik makale mi?

| Ölçüt | MEB STEM ders kitabı | İngilizce akademik makale |
|---|---|---|
| Hedef kullanıcıyla bağ | Çok yüksek: öğrenci doğrudan kendi müfredatındaki içeriği kullanır. | Orta: üniversite/araştırma kullanıcısı için değerlidir. |
| Türkçe matematik okunuşu katkısı | Çok yüksek; projenin özgün yönünü görünür kılar. | Düşük; ana dil İngilizcedir. |
| Kullanıcı araştırması | Okul öğrencisi, öğretmen ve özel eğitim uzmanıyla yapılabilir. | Hedef kitleye ulaşmak daha zordur. |
| Belge çeşitliliği | Ders anlatımı, formül, tablo, grafik, etkinlik ve soru içerir. | Karmaşık iki sütunlu düzen ve yoğun atıf içerir. |
| Teknik zorluk | Yönetilebilir; PDF kalitesi ve yayın yılı değişebilir. | Daha yüksek; formül/tablolar zengindir ancak İngilizce ağırlıklıdır. |
| Etki hikâyesi | Türkiye’de kapsayıcı eğitime doğrudan katkı. | Bilimsel bilgiye erişim açısından güçlü ancak dolaylı. |
| Telif / dağıtım | Kontrollü erişim gerekir. | Her makalenin lisansı ayrı incelenmelidir. |

**Sonuç:** Bitirme projesinin ana uygulama alanı MEB kitapları olmalıdır. Akademik makaleler, sadece genel teknik benchmark için küçük ve açık lisanslı bir karşılaştırma kümesi olarak tutulabilir.

MEB ve EBA, ders kitaplarını öğrenci ve öğretmenlerin erişimine sunmaktadır. MEBİ de ortaokul, lise ve mezun öğrenciler için ücretsiz öğrenme içerikleri sağlar. Buna rağmen erişilebilir sürümde matematiksel yapı, tablo ilişkileri, grafik verisi ve ekran okuyucuyla formül keşfi ayrı bir problemdir. Eğitimde Görme Engelliler Derneği, MEB’e ders kitapları için ayrı erişilebilirlik kriterleri içeren bir rapor sunmuştur. Bu, problemin varsayımsal değil, sahada tanımlanmış olduğunu gösterir.

- EBA ders kitabı erişimi: <https://eba.gov.tr/yardim/articles/untitled-article-95>
- MEBİ platformu: <https://mebi.eba.gov.tr/>
- EGED erişilebilir ders kitabı kriterleri: <https://www.eged.org/sayfa/gorme-engelli-ogrenciler-icin-ders-kitaplarinda-erisilebilirlik-kriterleri-ve-ders-kitaplarinda>
- MEB’in görme yetersizliği olan öğrenciler için sesli kütüphane çalışması: <https://www.meb.gov.tr/gorme-yetersizligi-olan-ogrenciler-icin-sesli-kutuphane-olusturuldu/haber/28068/tr>

---

## 2. Ürün tanımı ve özgün katkı

> **ErişSTEM**, MEB STEM PDF’lerini kaynak konumunu ve güven düzeyini kaybetmeden erişilebilir, öğretmen tarafından denetlenebilir öğrenme materyaline dönüştüren açık kaynaklı bir sistemdir.

Bu ürün bir model/API sarmalayıcısı değildir. Özgün mühendislik ve yapay zekâ katkısı dört katmandadır:

1. **Kaynak izlenebilir belge modeli:** Her öğe; PDF sayfası/kutusu, ham kaynak, dönüşmüş semantik içerik, model sürümü, işlem adımı ve güven skoru ile saklanır.
2. **Çok sinyalli güven motoru:** Model olasılığı tek başına karar vermez. Render eşdeğerliği, kural denetimleri, birden çok çıkarıcının uyuşması ve insan düzeltmeleriyle kalibre edilmiş skor kullanılır.
3. **Türkçe matematik erişilebilirliği:** MathML yapısı, Türkçe matematik okunuş kuralları, Braille/gezinti çıktısı ve referans test kümesi üretilir.
4. **İnsan-döngüde veri iyileştirme:** Öğretmenin düzeltmesi kaynak koordinatına ve hata türüne bağlanır; sonraki değerlendirme ya da uyarlama verisine dönüşür.

MathCAT, MathML’i konuşma, Braille ve matematik gezinmesine dönüştüren MIT lisanslı bir altyapıdır; NVDA ve JAWS gibi yardımcı teknolojilerle kullanılır. Türkçe için testli bir kural katkısı, projenin en savunulabilir açık kaynak çıktılarından biridir.

- MathCAT: <https://github.com/daisy/MathCAT>

---

## 3. Çekirdek ürün kapsamı

### P0 — Bitirme projesi teslimi

- MEB 9. sınıf Matematik kitabından 4 seçilmiş konu/ünite ve yaklaşık 80–120 sayfalık kaynak havuzu.
- Ayrı yayınevi/sürümden 9. sınıf Fizik seçilmiş 20–30 sayfa: genelleme testi.
- PDF, kaynak varsa HTML/LaTeX için kaynak-öncelikli giriş yönlendiricisi.
- Başlık, paragraf, formül, basit tablo ve temel grafik tespiti.
- Kaynak koordinatlı ortak belge ara gösterimi.
- Formülün MathML görünümü, klavyeyle keşfi ve tanımlı Türkçe çekirdek okunuş kümesi.
- Düşük güvenli çıktıyı yayımlamayan öğretmen denetim kuyruğu.
- Öğretmenin LaTeX/MathML/metin/tablo düzenleyebildiği PDF üstü kutu katmanı.
- Erişilebilir web okuyucu; EPUB3 + MathML dışa aktarımı.
- NVDA + Firefox ile görev testi, otomatik erişilebilirlik kontrolleri ve tekrar üretilebilir değerlendirme.

### P1 — Çekirdekten sonra

- Karmaşık tablo ARIA grid gezintisi.
- Grafik verisini çıkarma, yeniden çizme doğrulaması ve sonifikasyon.
- Chart2Music için Türkçe yerelleştirme katkısı.
- Yer imi, arama, kişiselleştirilmiş kısayollar, MP3 ve BRF çıktısı.

### P2 — Yalnızca yeterli düzeltme verisi oluşursa

- Grafik→tablo için QLoRA uyarlaması.
- Türkçe alan çevirisi için LoRA.
- Layout modeli fine-tune.

---

## 4. Önerilen mimari

```text
MEB PDF / kaynak HTML
        ↓
Kaynak-öncelikli giriş + sayfa envanteri
        ↓
Ortak belge modeli (içerik + bbox + provenance + güven)
        ↓
Metin · düzen · formül · tablo · grafik çıkarıcıları
        ↓
Doğrulama kuralları + kalibre güven skoru
        ↓
Öğretmen denetim kuyruğu ve sürüm geçmişi
        ↓
Erişilebilir web okuyucu / EPUB3-MathML
```

### Başlangıç teknoloji seçimi

| İhtiyaç | İlk tercih | Karar / neden |
|---|---|---|
| PDF yapılandırma | Docling | Yerel çalışır; düzen, okuma sırası, tablo, OCR ve formül zenginleştirme için güçlü baseline’dır. |
| Türkçe basılı metin | Docling OCR + PaddleOCR karşılaştırması | Küçük altın kümede CER/WER ile seçim yapılır; iki motoru kalıcı zincir yapmak zorunlu değildir. |
| Formül | Kaynak-LaTeX → görüntü tabanlı ikinci görüş | Kaynak mevcutsa OCR kullanılmaz; değilse render denetimi yapılır. |
| Tablo | Docling/TableFormer baseline | TEDS yanında başlık-hücre ilişkisi ayrıca denetlenir. |
| Raster grafik | Qwen3-VL 2B, yalnızca fallback | Önce PDF vektör nesneleri ve gömülü veri aranır; VLM uydurma yapmamalıdır. |
| Matematik erişilebilirliği | MathML + MathCAT | Türkçe kural alt kümesi için birim testleri yazılır. |
| Arayüz | React/TypeScript + FastAPI | API ve işlem kuyruğu model katmanından ayrılır; demo canlı GPU’ya bağlı olmaz. |

Docling, karmaşık belgeleri yapılandırılmış veriye dönüştürmek için açık kaynak bir altyapıdır. Qwen3-VL 2B Apache-2.0 lisanslıdır ve küçük görsel-dilsel fallback denemeleri için uygundur. Nougat, İngilizce bilimsel PDF benchmark’ında kullanılabilir; ancak model ağırlıkları CC-BY-NC olduğundan ürünün ana yolu olmamalıdır.

- Docling: <https://docling.ai/>
- Qwen3-VL 2B model kartı: <https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct>
- Nougat lisansı: <https://github.com/facebookresearch/nougat>

---

## 5. Veri stratejisi

### 5.1 Veri setleri

| Küme | Amaç | Boyut / içerik | Kullanım biçimi |
|---|---|---|---|
| **MEB-STEM-Source** | Gerçek kaynak havuzu | 2 kitap, 100–150 seçilmiş sayfa | Sadece yetkili geliştirme ortamı; herkese açık veri seti değildir. |
| **MEB-STEM-Gold** | Nihai değerlendirme | 30–40 sayfa; 150 formül, 25 tablo, 20 grafik, 300 metin bölgesi hedefi | Çift anotasyon + uyuşmazlık çözümü; eğitimden tamamen ayrıdır. |
| **MEB-STEM-Dev** | Eşik ayarı ve geliştirme | 40–60 sayfa | Model/kurallar bu kümede ayarlanır. |
| **Synthetic-Chart-TR** | Grafik veri çıkarma denemesi | Matplotlib/Plotly ile üretilmiş Türkçe etiketli grafikler | Veri ve doğru tablo otomatik üretilir; eğitim için güvenlidir. |
| **MathTR-Readings** | Türkçe matematik okunuşu | En az 150 referans MathML → Türkçe okunuş çifti | Kural birim testi ve uzman değerlendirmesi. |

**Altın küme kuralı:** Aynı kitap, sayfa veya neredeyse aynı şablon hem geliştirme hem testte bulunamaz. Mümkünse test kitabı farklı yayınevi/sürümden seçilir. Böylece sistemin yalnızca sayfa şablonunu ezberlemesi engellenir.

### 5.2 Etiketleme şeması

- Bölge türü: `heading`, `paragraph`, `formula-inline`, `formula-display`, `table`, `chart`, `figure`, `caption`, `exercise`.
- Her bölge için: sayfa, bounding box, okuma sırası, ham metin/LaTeX/MathML, insan doğruluk etiketi, hata türü ve kaynak kanıtı.
- Tablo için: hücre koordinatı, satır/sütun başlığı ilişkisi, hücre metni.
- Grafik için: grafik türü, eksen başlığı/birimleri, seri adları, doğrulanmış veri tablosu mümkünse kaynak bağlantısı.
- Matematik için: referans Türkçe okunuş, tercih edilen konuşma stili ve Braille beklentisi.

Etiketleme, en az iki değerlendiriciyle örneklem bazında kontrol edilmeli; anlaşmazlık oranı raporda verilmelidir. Etiketleyici kılavuzu, testlerde kullanılan örneklerden ayrı yayımlanabilir.

### 5.3 Telif ve etik sınırları

MEB PDF’sinin çevrimiçi erişilebilir olması, onu serbest lisanslı açık veri yapmaz. Türkiye’de 5846 sayılı Fikir ve Sanat Eserleri Kanunu Ek Madde 11; erişilebilir nüsha yoksa ders kitapları dâhil yayımlanmış yazılı eserlerin engelliler için, ticari amaç olmadan ve belirtilen koşullarla erişilebilir formatta çoğaltılmasına izin verir. Aynı madde, bu nüshaların satılamayacağını, amacı dışında kullanılamayacağını ve hak sahibi/amaç bilgisini taşıması gerektiğini söyler.

Bu nedenle:

1. GitHub/Hugging Face’e MEB PDF’lerini, sayfa görsellerini veya dönüştürülmüş tam kitabı koyma.
2. Açık kaynak olarak kodu, sentetik veriyi, şemayı, değerlendirme komutlarını, anonimleştirilmiş hata istatistiklerini ve MathCAT kural katkısını yayımla.
3. Gerçek içerikten oluşan erişilebilir çıktıyı sadece hukuken uygun hedef kullanıcı/kurum akışıyla ve üniversite danışmanı ile telif biriminin yazılı görüşü alındıktan sonra sun.
4. Demo için izinli kısa alıntı, tamamen sentetik sayfa veya kamu izni bulunan materyal kullan.
5. Kullanıcı araştırmasında öğrenci verisi, engel durumu ve ses kayıtları için üniversitenin etik kurul prosedürünü takip et; ham kayıtları depoya koyma.

Kaynak: <https://aile.gov.tr/eyhgm/mevzuat/ulusal-mevzuat/kanunlar/fikir-ve-sanat-eserleri-kanunu/>

---

## 6. 30 saatlik Kaggle GPU planı

30 saat, prototip ve kontrollü bir uyarlama deneyi için yeterlidir; üç farklı modeli fine-tune etmek için yeterli değildir. Kaggle’ın resmî belgeleri 12 saatlik GPU oturum sınırını belirtir; gerçek kota ve kullanılabilir donanım hesap ayarından doğrulanmalıdır.

| İş | GPU saati | Çıkış kapısı |
|---|---:|---|
| Ortam, bellek/hız pilotu | 2 | Aynı notebook temiz oturumda tekrar çalışır. |
| Docling / OCR / formül baseline toplu koşusu | 5 | Altın kümenin ilk ölçüm raporu oluşur. |
| Grafik VLM inference ve sentetik veri değerlendirmesi | 4 | Sayısal hata ile no-answer eşiği belirlenir. |
| QLoRA pilotu — yalnızca baseline eşiği geçmezse | 8 | Held-out sentetik kümede baseline’ı anlamlı geçmelidir. |
| En iyi koşunun tekrar üretimi | 3 | Sabit sürüm/model/veri ile aynı sonuç elde edilir. |
| Hata analizi / ablation | 4 | En az üç hata kategorisi raporlanır. |
| Pay ve tampon | 4 | Kesinti, indirilen model veya tekrar koşusu riski. |

Toplam: **30 GPU saati**.

Kaggle kaynakları: <https://www.kaggle.com/docs/notebooks>

**Zorunlu karar kapısı:** QLoRA, ancak grafik baseline’ı hedef ölçüte ulaşmadığında başlar. Layout fine-tune ve çeviri LoRA bu proje döneminde başlatılmaz; yeterli insan düzeltmesi olmadan yapılmaları bilimsel olarak anlamlı değildir.

---

## 7. Etki ve kullanılabilirlik araştırması

### Hedef katılımcılar

- 3–5 görme yetersizliği olan ortaöğretim STEM öğrencisi veya öğrenci adayı.
- 2 STEM öğretmeni.
- 1 özel eğitim öğretmeni ya da erişilebilirlik uzmanı.

Katılımcı sayısı nicel genelleme için değil, en kritik kullanım sorunlarını bulmak için tasarlanmıştır. Katılımcıya erişim mümkün değilse uzman değerlendirmesi ikame değil, açıkça “sınırlılık” olarak raporlanır.

### Görev senaryoları

1. Belgedeki bir başlığa gitme ve altındaki formülü anlama.
2. Bir formülü klavyeyle parçalara ayırarak dinleme.
3. Bir tablonun satır/sütun başlığını ve belirli hücresini bulma.
4. Düşük güvenli formülü fark etme ve kaynağına dönme.
5. Öğretmen rolünde hatalı formülü düzeltip yeniden yayımlama.
6. EPUB çıktısını hedef okuyucuda açıp aynı içeriğe erişme.

### Ölçümler

| Alan | Ölçüm | Başarı eşiği |
|---|---|---|
| Teknik doğruluk | Metin CER/WER, formül sembol hatası, render eşdeğerliği, TEDS | Eşikler geliştirme verisiyle önceden kaydedilir. |
| Güvenlik | Yüksek güven etiketinin precision’ı; yanlış çıktıyı düşük güvene alma recall’ı | “Yüksek güven” yanlış bilgi vermemelidir; eşik test kümesinde seçilir. |
| Kullanılabilirlik | Görev tamamlama oranı, süre, hata sayısı, SUS | Görevlerde gözlenen engeller nitel olarak da raporlanır. |
| Erişilebilirlik | NVDA + Firefox görev testi, klavye erişimi, axe-core | Kritik ihlal sıfır; gerçek ekran okuyucu senaryosu zorunlu. |
| Öğretmen yükü | Belge başına denetim/düzeltme süresi | Ham PDF’ye kıyasla süre ve hata azalması aranır. |
| Etki | Öğrencinin bağımsız çalışma algısı ve öğretmenin materyal hazırlama yükü | Ön/son görüşme ve açık uçlu geri bildirimle desteklenir. |

### Ön kayıt / rapor disiplini

Ölçümler, hedefler, dışlama kuralları ve test ayrımı uygulamadan önce `evaluation_protocol.md` içinde sabitlenmelidir. Nihai rapor; başarıları, başarısızlıkları, düşük güvene düşen öğeleri ve kullanıcıların çözemediği görevleri birlikte yayımlar.

---

## 8. 16 haftalık teslim takvimi

| Hafta | Teslim |
|---|---|
| 1–2 | Telif/etik kontrolü, iki kitabın sürüm sabitlemesi, kullanıcı görüşme planı, repo/CI ve belge şeması. |
| 3–4 | MEB-STEM-Dev/Gold örneklemi ve anotasyon kılavuzu; Docling/OCR/formül baseline. |
| 5–6 | Ortak belge modeli, doğrulama kuralları, ilk ölçüm raporu. |
| 7–8 | Erişilebilir okuyucu ve Türkçe MathCAT çekirdek kuralları. |
| 9–10 | Öğretmen denetim ekranı, güven kuyruğu, grafik fallback değerlendirmesi. |
| 11 | QLoRA karar kapısı; gerekliyse yalnızca pilot eğitim. |
| 12 | EPUB3/MathML, NVDA görev senaryoları. |
| 13 | Kod ve değerlendirme protokolü dondurma. |
| 14–15 | Kullanıcı/uzman testi, hata düzeltme, tekrar üretilebilir final koşusu. |
| 16 | Rapor, demo, model/veri kartları, lisans ve sınırlılıklar belgesi. |

---

## 9. Başarı tanımı

Proje; “PDF’i dönüştürdüm” denildiğinde değil, aşağıdakiler kanıtlandığında başarılı kabul edilir:

1. Seçilmiş MEB STEM içeriği ekran okuyucu ve klavye ile mantıksal sırada gezilebilir.
2. Formüller Türkçe çekirdek kapsamda anlaşılabilir biçimde okunur ve kaynak görseline geri bağlanır.
3. Sistem emin olmadığı yerde cevap uydurmak yerine öğretmene denetim görevi açar.
4. Öğretmen, hatayı kaynak üzerinde düzeltebilir; düzeltmenin sürümü ve gerekçesi korunur.
5. Test kümesi, geliştirme kümesinden ayrıdır; sonuçlar tekrar üretilebilir.
6. Gerçek kullanıcı veya ilgili uzmanlar, görev bazlı testte ürünün işe yarayıp yaramadığını değerlendirmiştir.

Bu biçimde proje; erişilebilirlik, belge yapısı, Türkçe matematik dili, güvenilir yapay zekâ ve insan denetimini birlikte ele alan; Türkiye’de doğrudan kullanılabilir bir bitirme projesi olur.

---

## 10. Yapay zekâ teknoloji kararları

Teknoloji seçimi, “en çok yapay zekâ bileşeni” hedefiyle değil; her bileşenin ölçülebilir bir hata sınıfını azaltmasıyla yapılır. Modelin adı kullanıcıya gösterilmez; kullanıcıya gösterilen şey kaynağı, doğrulanma durumu ve gerektiğinde düzeltme yoludur.

| Katman | Kullanılacak teknoloji | Sistemdeki görevi | Güvenlik sınırı |
|---|---|---|---|
| Belge AI / OCR | Docling, PaddleOCR karşılaştırması, PDF metin katmanı | Metin, düzen, okuma sırası ve öğe kutularını çıkarmak | Metin katmanı varsa OCR çalışmaz; sonuç kaynak kutusuna bağlı kalır. |
| Görüntü anlama | Tablo için TableFormer/Docling; grafik için vektör çıkarma + Qwen3-VL fallback | Tablo yapısı ve yalnızca raster grafikte olası veri/etiket çıkarımı | Grafik verisi üretilemezse “doğrulanamadı” denir; tahmini sayı yayımlanmaz. |
| Formül AI | Kaynak-LaTeX, Pix2Text/Pix2TeX ikinci görüşü, LaTeX→MathML | Formülü makinece okunabilir ve gezilebilir yapmak | Render, sembol ve MathML şema kontrolü geçmeden yayınlanmaz. |
| LLM | Yerel/açık ağırlıklı küçük model (Qwen3-VL 2B veya eşdeğeri) | Belirsiz görsel öğe sınıflama, kontrollü kısa açıklama adayı, yapılandırılmış hata sınıflama | LLM kaynak otoritesi değildir; JSON şeması, kanıt bağlantısı ve doğrulama olmadan içerik yayınlayamaz. |
| Klasik ML | Logistic Regression / LightGBM kalibratörü | OCR, formül, tablo ve grafik sinyallerinden güven olasılığı hesaplamak | Sadece altın kümede kalibre edilir; skor, insan denetiminin yerini almaz. |
| Kural tabanlı zeka | SymPy/LaTeX derleme, MathML doğrulama, birim/sayı denetimleri | Anlamsal olarak yanlış veya bozuk çıktıyı yakalamak | Kurallar geçmezse içerik bloke edilir. |
| Türkçe dil katmanı | MathCAT Türkçe kural seti, terim sözlüğü | Matematik okunuşu, Braille ve yapısal gezinme | Her kural referans cümle ve birim testi taşır. |

### LLM nerede kullanılacak, nerede kullanılmayacak?

LLM, bu projenin merkezi ama tek karar vericisi değildir.

- **Kullanılacak:** raster grafik/şekil türünü tanıma; öğretmene kısa, kaynak bağlantılı açıklama taslağı önerme; hata kaydını sınıflandırma; yalnızca izinli bir şemaya uygun JSON üretme.
- **Kullanılmayacak:** formülün doğru olduğunu ilan etme; kaynakta olmayan matematiksel veri üretme; öğretmen onayı olmadan ders içeriğini değiştirme; güvenlik skorunu tek başına belirleme.

Bu ayrım, halüsinasyonun erişilebilirlikte “yanlış ama ikna edici” bir sesli çıktıya dönüşmesini önler.

### Reinforcement Learning (RL) kararı

İlk sürümde çevrim içi RL **kullanılmayacaktır**. Öğrenci üzerinde deneme-yanılma yapan veya modelin yanlış içeriği ödül olarak öğrenebildiği bir RL sistemi, bu ürünün doğruluk gereksinimiyle uyumlu değildir.

RL ancak aşağıdaki önkoşullar sağlanırsa P2 araştırma deneyi olarak eklenir:

1. En az 500–1.000 insan doğrulamalı düzeltme ve hata önceliği kaydı vardır.
2. Ödül tanımı sabittir: doğrulanmış hata yakalama, öğretmen düzeltme süresini azaltma ve yanlış yüksek-güven etiketini cezalandırma.
3. Eğitim tamamen **offline** yapılır; öğrenci veya canlı içerik üzerinde keşif yapılmaz.
4. Yeni politika, kilitli altın kümede mevcut kural/ML baseline’ını geçmeden yayına alınmaz.

Bu veri oluştuğunda RL’nin doğru kullanım alanı, **hangi öğenin önce öğretmen incelemesine gideceğini sıralamak** olacaktır. İçeriği üretmek veya matematiksel doğruluğu belirlemek değildir. İlk sürümde aynı problem kalibre edilmiş denetimli öğrenme ile çözülür; daha az karmaşık ve daha denetlenebilirdir.

---

## 11. Kullanıcı deneyimi: ürün nasıl kullanılacak?

### Öğrenci akışı

```text
Giriş / öğretmenin paylaştığı bağlantı
        ↓
Kitap → sınıf → ünite → konu seçimi
        ↓
Erişilebilir okuyucu (varsayılan odak: içerik)
        ↓
Başlık, paragraf, formül, tablo veya şekle klavyeyle gitme
        ↓
Dinleme / Braille / yüksek kontrast / yazı boyutu tercihleri
        ↓
Gerekirse “kaynağı ve doğrulama durumunu göster”
        ↓
Kaldığı yer, not veya öğretmene geri bildirim
```

Öğrencinin PDF yüklemesi, model seçmesi veya “OCR başlatması” gerekmez. Öğrenci için ürün bir **erişilebilir ders okuyucusudur**; yapay zekâ arka planda çalışır.

Öğrenci ekranında zorunlu bileşenler:

- `Alt+H`: başlıklar, `Alt+F`: formüller, `Alt+T`: tablolar, `Alt+G`: grafik/şekiller arasında gezinme.
- Formülde “kısa okunuş”, “ayrıntılı okunuş” ve klavyeyle parça parça keşif.
- Tablo için hücre değeri ile birlikte satır ve sütun başlığının seslendirilmesi.
- Grafik için önce kısa özet, sonra doğrulanmış veri tablosu; veri güvenilmezse açık uyarı.
- “Bu içerik doğrulandı / öğretmen denetimi bekliyor” bilgisi; bu uyarı ana okuma akışını kesmez.
- Ekran okuyucu, klavye, yüksek kontrast, düşük görme için büyütülmüş metin ve fare/touch kullanımını aynı anda destekleme.

Klavyeyle tüm işlevlerin yapılabilmesi temel gereksinimdir; WCAG bunu açık bir başarı kriteri olarak tanımlar. <https://www.w3.org/WAI/WCAG20/versions/understanding/wcag20-understanding-20081211-letter.pdf>

### Öğretmen akışı

```text
Yetkili kaynak listesinden kitap/bölüm seçimi
        ↓
Sistem belgeyi arka planda işler ve taslak oluşturur
        ↓
“Önce incelenecekler” kuyruğu: düşük güven × öğrenci etkisi
        ↓
PDF üzerindeki kaynak kutusu + erişilebilir çıktı yan yana
        ↓
Metin / LaTeX / MathML / tablo hücresi düzeltme
        ↓
Önizleme: ekran okuyucu metni + render + sürüm farkı
        ↓
Yayınla veya iade et
        ↓
Öğrenciler için sürümlenmiş erişilebilir ünite
```

Öğretmenin öncelik sırası, yalnızca düşük model skoruna göre belirlenmez. Aşağıdaki etki skoru kullanılır:

`inceleme önceliği = hata olasılığı × içerik etkisi × öğrenci erişim riski`

Örneğin bir konu başlığındaki düşük güvenli formül, dekoratif bir görselden önce denetime gider. Bu karar açıklanabilir olarak panelde gösterilir.

### Yönetici / proje ekibi akışı

- Kitap sürümü, erişim yetkisi ve içerik telif notunu tanımlar.
- İşleme kuyruğunu, başarısız işleri ve model sürümlerini görür.
- Sadece onaylanmış model/veri sürümünü üretime alır.
- Anonim kalite metriklerini izler; öğrenci içeriğini veya hassas kullanıcı kayıtlarını gereksiz görmez.

---

## 12. Stabilite, kalite ve doğruluk tasarımı

Şirket kalitesinde sistem, başarılı demo değil; hata oluştuğunda güvenli davranan, sonucu yeniden üretebilen sistemdir. NIST AI RMF’nin geçerli/güvenilir, güvenli, hesap verebilir, açıklanabilir ve mahremiyeti koruyan sistem ilkeleri bu tasarıma rehber olur. <https://www.nist.gov/itl/ai-risk-management-framework/ai-risk-management-framework-faqs>

### 12.1 Dört savunma hattı

1. **Girdi koruması:** Dosya tipi/boyut/sayfa sınırı, virüs taraması, şifreli PDF bildirimi, sayfa görüntü hash’i, kaynak sürümü ve işlem kimliği.
2. **Çıktı koruması:** Pydantic/JSON Schema, MathML şeması, LaTeX derleme, izinli HTML, XSS temizliği, tablo boyut/koordinat denetimi.
3. **Anlam koruması:** Render karşılaştırması, sembol/birim/numerik tutarlılık, kaynak-model uyuşmazlığı ve güven kalibrasyonu.
4. **Yayın koruması:** Düşük güveni otomatik yayımlamama, öğretmen onayı, sürüm geçmişi, geri alma ve hata kaydı.

### 12.2 Güven skoru

Her öğe için ham model confidence yerine özelliklerden oluşan bir skor üretilir:

```text
güven = kalibratör(
  model_confidence,
  kaynak_uyuşması,
  render_skoru,
  şema_geçti_mi,
  OCR_kararlılığı,
  içerik_türü,
  insan_düzeltme_geçmişi
)
```

Çıktı üçe ayrılır:

- **Yayınlanabilir:** yüksek güven + tüm zorunlu denetimler geçti.
- **Uyarıyla yayınlanabilir:** içerik öğrenci için güvenli fakat açıklama/şekil ayrıntısı eksik; durum görünürdür.
- **Denetim bekliyor:** formül, tablo veya grafik açısından yanlış bilgi riski vardır; öğrenciye kesin bilgi olarak gösterilmez.

### 12.3 MLOps ve işletim güvenilirliği

| Alan | Uygulama |
|---|---|
| Kod | Git, pull request kontrolü, unit/integration/e2e testleri, bağımlılık kilit dosyası. |
| Veri | DVC ile PDF hash’i, anotasyon sürümü ve veri bölünmesi izlenir; gerçek MEB verisi özel depoda kalır. |
| Deney | MLflow ile veri sürümü, kod commit’i, model, parametre, metrik ve artefact birlikte kaydedilir. |
| İşleme | FastAPI + arka plan iş kuyruğu; idempotent işler, tekrar deneme, timeout, önbellek ve başarısız iş kuyruğu. |
| Yayın | Staging → gold-set kalite kapısı → production; başarısız metrikte önceki sürüme geri dönüş. |
| Gözlemleme | Yapılandırılmış log, işlem kimliği, süre/hata oranı, model sapması ve düşük güven oranı paneli. |
| Güvenlik | Rol tabanlı erişim, şifreli gizli anahtarlar, izinli dosya türleri, denetim günlüğü, indirme/paylaşma kısıtı. |

DVC veri ve işlem hattını sürümlemeye; MLflow parametre, metrik, kod sürümü ve model artefact’larını izlemeye yarar. Bu ikisi “hangi model daha iyi?” sorusunun tekrarlanabilir yanıtını verir.

- DVC: <https://doc.dvc.org/user-guide>
- MLflow Tracking: <https://mlflow.org/docs/latest/ml/tracking/>

### 12.4 Yayın kalite kapısı

Yeni model veya kural sürümü, aşağıdaki kapılar geçmeden öğrenci içeriğini değiştiremez:

1. Birim ve kontrat testleri geçer.
2. Kilitli MEB-STEM-Gold test kümesinde mevcut üretim sürümünden kötü değildir.
3. Kritik hata sınıfında (formül operatörü, eksi işareti, kesir çizgisi, tablo başlığı, eksen birimi) gerileme yoktur.
4. Yüksek güvenli yanlış çıktı oranı önceden belirlenen üst sınırı aşmaz.
5. NVDA + Firefox görev senaryosu ve axe-core denetimi geçer.
6. Öğretmen rolüyle düzeltme-yayınlama-geri alma senaryosu çalışır.

Bu kapılardan biri geçmezse sürüm yayına alınmaz; hata kaydı ve karşı örnek değerlendirme setine eklenir.

---

## 13. Gerçek fayda üreten ileri teknoloji yol haritası

Bu bölümdeki bir teknoloji, yalnızca aşağıdaki üç soruya olumlu cevap veriyorsa ürüne girer:

1. Hangi kullanıcı görevini daha doğru, hızlı veya bağımsız yapar?
2. Bu iyileşmeyi hangi metrikle gösterebiliriz?
3. Hata verdiğinde öğrenciyi yanlış yönlendirmeden nasıl geri çekilir?

### 13.1 Quantize modeller: maliyet azaltma değil, yerel ve mahrem çalışma

| Kullanım | Karar | Uygulama | Kabul ölçütü |
|---|---|---|---|
| Kaggle’da eğitim | 4-bit NF4 QLoRA | Sadece QLoRA deneyi gerektiğinde; temel ağırlıklar dondurulur. | Held-out grafik kümesinde BF16 baseline’dan anlamlı kötü değildir. |
| Sunucuda görsel-dilsel çıkarım | 8-bit veya AWQ-4bit | Qwen3-VL küçük model yalnızca seçili kırpılmış bölgelere uygulanır. | Altın kümede doğruluk, gecikme ve GPU belleği birlikte ölçülür. |
| CPU/yerel metin yardımcıları | GGUF Q4/Q5 | Sadece öğretmen yardımcısı veya kaynaklı arama özeti için; kritik dönüşüm hattında değil. | Türkçe STEM test setinde kaynaklı yanıt doğruluğu korunur. |

Quantization körü körüne 4-bit’e indirme değildir. Türkçe STEM kalibrasyon metniyle AWQ/importance-matrix denenir; seçilen quantize model, aynı kilitli testte BF16 sürümüyle karşılaştırılır. Qwen’in kendi dokümantasyonu da düşük bit hassasiyetinin kalite düşürebileceğini ve alan kalibrasyon verisiyle bunun ölçülmesi gerektiğini belirtir. <https://github.com/QwenLM/Qwen3/blob/main/docs/source/quantization/llama.cpp.md>

**Ürün değeri:** Kitap ve öğrenci verisini dış API’ye göndermeden yerelde çalıştırma, daha düşük gecikme ve düşük işletim maliyeti. **Sınır:** Formül ve grafik doğruluğu düşerse quantize sürüm otomatik olarak reddedilir.

### 13.2 RAG: sohbet botu değil, kaynaklı ders kitabı gezgini

RAG eklenebilir; fakat “PDF’i vektör veritabanına atıp chatbot yapmak” doğru ürün değildir. Doğru kullanım, öğrenciye ders kitabındaki onaylı bilgiyi buldurmaktır.

```text
Öğrenci sorusu
   ↓
Niyet: tanım / örnek / formül / tablo / konu bulma
   ↓
Hibrit arama: Türkçe BM25 + semantik embedding + başlık/ünite filtresi
   ↓
Reranker ve kaynak yeterliliği kontrolü
   ↓
Önce kaynak parça, sayfa ve “buraya git” bağlantısı
   ↓
Yalnızca yeterli kanıt varsa kısa, kaynaklı açıklama
```

RAG yalnızca **öğretmen tarafından yayımlanmış erişilebilir içerik** üzerinde çalışır. Ham OCR, düşük güvenli formül, dış internet ve öğrencinin kişisel notları ilk sürümde indekslenmez.

RAG kalite metrikleri:

- `Recall@k`: doğru ders parçası ilk sonuçlarda mı?
- Kaynak uygunluğu: cevap gerçekten gösterilen pasajla destekleniyor mu?
- Atıf doğruluğu: sayfa/başlık bağlantısı doğru mu?
- Cevap vermeme doğruluğu: kaynak yoksa sistem “kitapta doğrulanmış cevap bulunamadı” diyebiliyor mu?
- Görev süresi: öğrenci aradığı konuya klasik PDF’den daha hızlı ulaşıyor mu?

LLM ile serbest cevap üretimi, kaynak yetersizse kapalıdır. Bu yaklaşım RAG’i gerçek öğrenme erişimi için kullanır; halüsinasyon üreten ikinci bir ders kitabına dönüştürmez.

### 13.3 Jev AI: deneysel karar katmanı, çekirdek bağımlılık değil

Jev, metin üretmek yerine seçenek, skor veya evet/hayır gibi tipli kararlar ve olasılık döndüren yeni bir karar modelidir. Bu, denetim kuyruğu veya RAG kanıt yeterliliği gibi ikili kararlar için kavramsal olarak uygundur. <https://jev-ai.org/>

Ancak bu proje için Jev **zorunlu değildir** ve üretim hattının çekirdeği olmamalıdır:

- Harici ve yeni bir API’dir; erişilebilir kitap içeriğini üçüncü tarafa göndermek telif/mahremiyet açısından istenmez.
- Kalibrasyon iddiası, bizim MEB-STEM-Gold testimizde ayrıca doğrulanmalıdır.
- Aynı iş; başlangıçta yerel Logistic Regression/LightGBM, kurallar ve öğretmen denetimiyle daha şeffaf yapılabilir.

İsterseniz yalnızca sentetik/izinli test verisinde A/B deneyi yapılır: `Jev karar skoru` ile `yerel kalibratör`ün yanlış yüksek-güven oranı, gecikmesi ve maliyeti karşılaştırılır. Yerel çözümü açıkça geçmezse projeye alınmaz.

### 13.4 Görüntü işleme: en yüksek kaldıraçlı optimizasyonlar

Çoğu hata büyük bir VLM seçilmediği için değil, yanlış sayfa ve yanlış kırpım modele verildiği için oluşur. Bu nedenle aşağıdaki sıralama uygulanır:

1. **Doğrudan PDF çıkarımı:** Metin katmanı, vektör çizgiler, gömülü görseller ve font bilgisi önce alınır. OCR son seçenektir.
2. **Sayfa kalite sınıflaması:** Sayfa dijital-doğumlu, taranmış, eğik, düşük çözünürlüklü veya karma içerik olarak sınıflanır.
3. **Uyarlanabilir rasterleştirme:** Sadece sorunlu sayfa/bölge 200–300 DPI’da rasterleştirilir; tüm kitabı yüksek DPI’da işlemek yasaktır.
4. **Bölge tabanlı işleme:** Düzen tespitinden sonra metin, formül, tablo ve grafik ayrı kırpılır; modele tam sayfa verilmez.
5. **Ön işleme:** Eğiklik düzeltme, kenar boşluğu temizleme, adaptif kontrast/binarization; özgün görsel ve işlenmiş görsel birlikte saklanır.
6. **Belgeye özgü tekrar kullanımı:** Aynı kitap fontu, sayfa şablonu ve tekrar eden başlık/altbilgiler için cache ve şablon kuralları kullanılır.
7. **Vektör grafiği önceliği:** Eksen, çizgi ve metin PDF vektöründen alınabiliyorsa VLM çağrısı yapılmaz.

Bu yaklaşım GPU tüketimini azaltır, OCR doğruluğunu artırır ve hata kaynağını öğretmen için açıklanabilir yapar.

### 13.5 TTS: önce matematik dili, sonra ses modeli

Seslendirmede en kritik konu “insan gibi ses” değil, matematiğin doğru ve anlaşılır söylenmesidir. Bu yüzden hat şu sıradadır:

```text
MathML
  → MathCAT Türkçe konuşma kuralı
  → Türkçe metin normalleştirici (sayı, birim, kısaltma, sembol)
  → SSML (durak, vurgu, hız)
  → TTS motoru
  → ses + zaman damgalı transkript
```

İlk sürümde iki yerel Türkçe TTS motoru, 100 ifadeli `MathTR-Readings` kümesinde karşılaştırılır. Değerlendirme; öğretmen/öğrencinin doğru anlama oranı, tercih, gecikme ve hata türleriyle yapılır. MP3 önbelleği yalnızca onaylı içerik için üretilir; öğrenci her seferinde tekrar beklemez.

TTS fine-tune **ancak** mevcut motorlar matematiksel telaffuz hedefini karşılamazsa yapılır. Gerekenler:

- Açık lisanslı ya da açık rızayla kaydedilmiş, ticari kullanım izni net Türkçe ses verisi.
- Genel ses klonlama değil; sayı, birim, matematik terimi ve SSML prosodisi için dar kapsamlı LoRA/adaptasyon.
- Ayrı tutulan konuşmacılar ve ifadelerle anlaşılabilirlik testi.
- Ses kimliği, rıza ve silme prosedürü için etik kayıt.

Bu sınırlar önemlidir: güncel bazı Türkçe uyarlamalar dahi yabancı aksan ve ham sayılarda hatalar bildirmektedir; yalnızca modeli fine-tune etmek problemi otomatik çözmez. <https://huggingface.co/hcfk/qwen3-tts-turkish>

### 13.6 Öğrenme teknolojisi: erişilebilir okuyucudan öğrenme aracına geçiş

Bu katman, belge dönüşümü güvenilir hâle geldikten sonra eklenir.

- **Yapısal öğrenme haritası:** Ünite → kavram → formül → örnek → alıştırma ilişkileri ortak belge modelinden çıkarılır. Öğrenci “bu formülün ön koşulu nedir?” diye gezebilir.
- **Kaynaklı mikro tekrar:** Yalnızca yayımlanmış tanım/formül ve öğretmen onaylı örneklerden erişilebilir kartlar oluşturulur. Kart, her zaman kaynak sayfasına geri gider.
- **Aralıklı tekrar:** Öğrencinin isteğe bağlı ilerlemesiyle basit SM-2 benzeri plan; ilk sürümde kara kutu “öğrenme tahmin modeli” kullanılmaz.
- **Erişilebilir alıştırma:** Formül cevabı için klavyeyle yazılabilir MathML/LaTeX alanı, anında yapısal geri bildirim ve öğretmenin eklediği çözüm yolu.
- **Öğretmen görünümü:** Sadece toplulaştırılmış, rızaya dayalı ilerleme sinyalleri; öğrenci davranışını gizlice profilleme yoktur.

Bu özelliklerin faydası; konu bulma süresi, bağımsız tamamlanan görev sayısı ve öğrencinin geri dönme/tekrar kullanma oranıyla ölçülür.

### 13.7 Active learning: eğitim verisini gerçekten değerli kılma

Öğretmenin her düzeltmesini rastgele saklamak yerine sistem, en bilgi değeri yüksek örnekleri ister:

```text
düşük güven + model anlaşmazlığı + öğrenci açısından kritik öğe
                         ↓
                 öğretmen inceleme kuyruğu
                         ↓
        doğrulanmış düzeltme + hata sınıfı + kaynak konumu
                         ↓
          gold set genişletme / bir sonraki offline eğitim
```

Bu, 30 saatlik GPU hakkını gerçek hata dağılımına ayırır. Önce ölçüm kümesi genişler, sonra yalnızca metrikle kanıtlanan model uyarlaması yapılır.

---

## 14. Teknoloji alma karar matrisi

| Teknoloji | İlk sürüm | Sonraki faz | Neden |
|---|---|---|---|
| Docling + PDF kaynak çıkarımı | Evet | — | Temel belge yapısı için zorunlu. |
| OCR benchmark ve bölge ön işleme | Evet | — | Türkçe PDF doğruluğunu doğrudan artırır. |
| MathCAT Türkçe kuralları | Evet | — | En güçlü erişilebilirlik ve özgün katkı. |
| Güven kalibrasyonu / kurallar | Evet | — | Yanlış bilginin yayımlanmasını önler. |
| Quantized VLM inference | Evet, benchmark sonrası | — | Yerel çalışma ve maliyet için faydalıysa. |
| Kaynaklı hibrit RAG | Hayır, çekirdek sonrası | Evet | Onaylı içerik yeterince oluşunca öğrenci aramasını iyileştirir. |
| TTS motor benchmarkı + SSML | Evet | — | Sesli erişim kalitesini ölçer. |
| TTS LoRA/fine-tune | Hayır | Koşullu | Mevcut motorlar matematik anlaşılabilirliğini geçmezse. |
| Grafik QLoRA | Hayır | Koşullu | Vektör+baseline ölçümde yetersiz kalırsa. |
| RL | Hayır | Koşullu | Sadece offline denetim sıralaması için yeterli düzeltme verisinde. |
| Jev AI | Hayır | Deneysel | Yerel kalibratörü açıkça geçerse. |
| Aralıklı tekrar / kartlar | Hayır, dönüşümden sonra | Evet | Doğrulanmış içerik üzerinde gerçek öğrenme değeri sağlar. |

Bu matris dışındaki yeni teknoloji önerileri de aynı kuraldan geçer: kullanıcı görevi, ölçüm, güvenli geri çekilme. Bunlardan biri yoksa projeye eklenmez.

---

## 15. Doğrulanmış platform ve kullanıcı deneyimi kararı

### Karar: tek kod tabanlı, iki ayrı deneyimli responsive web/PWA

İlk ürün **öğrenci için mobil öncelikli Progressive Web App (PWA)**, **öğretmen için masaüstü öncelikli web paneli** olarak geliştirilecektir. Ayrı Android ve iOS native uygulaması ilk fazda yapılmayacaktır.

Bu kararın gerekçesi:

- W3C, mobil erişilebilirliğin ayrı bir standart değil, WCAG ile web uygulamalarında da kapsanan bir alan olduğunu belirtir. Aynı erişilebilir HTML/ARIA ve MathML; telefon, tablet ve masaüstünde kullanılabilir. <https://www.w3.org/WAI/standards-guidelines/mobile/>
- Android TalkBack; Chrome/web içeriği, fiziksel Braille ekranı ve Braille girişini destekler. Apple VoiceOver da iPhone/iPad/Mac ve Braille ekranlarında çalışır. Uygulamanın görevi bu yardımcı teknolojilerin anlayacağı doğru semantiği sağlamaktır. <https://support.google.com/accessibility/android/answer/3535886?hl=en> ve <https://developer.apple.com/documentation/accessibility/braille-displays>
- Öğretmen denetimi; PDF üstü kutular, iki panel karşılaştırması, tablo düzenleme ve klavye/fare birlikteliği gerektirir. Bu görev 10 inç altı ekranda verimsizdir; masaüstü web daha doğrudur.
- PWA, tek dağıtım hattı, hızlı güvenlik güncellemesi, düşük cihaz gereksinimi ve önceden onaylanmış üniteleri çevrimdışı önbelleğe alma imkânı verir.

Native uygulama ancak kullanıcı testleri web’in çözemediği bir sorunu gösterirse değerlendirilir: örneğin güvenilir arka plan indirme, cihaz düzeyinde Braille yönlendirme veya erişilebilirliğe zarar vermeden gereken işletim sistemi entegrasyonu.

### Platform haritası

| Kullanıcı | Birincil cihaz | Ürün yüzü | Tasarım ilkesi |
|---|---|---|---|
| Tam görmeyen öğrenci | Android telefon/tablet veya iPhone/iPad | Mobil PWA + TalkBack/VoiceOver | Tek elle/gesture ve ekran okuyucu akışı; gereksiz görsel kalabalık yok. |
| Az gören öğrenci | Tablet, Chromebook veya bilgisayar | Responsive öğrenci webi | Büyük metin, yüksek kontrast, yeniden akış, büyütme ve dokunma hedefleri. |
| Braille ekranı kullanan öğrenci | Telefon/tablet/PC + fiziksel Braille ekranı | Aynı öğrenci webi | Semantik metin/MathML; Braille dönüşümünü yardımcı teknoloji yapar. |
| STEM öğretmeni | Dizüstü/masaüstü | Öğretmen paneli | Görsel PDF denetimi + klavye kısayolu + ekran okuyucu eşdeğeri. |
| Özel eğitim uzmanı | Masaüstü/tablet | Öğretmen paneli + test modu | Okunuş, sıralama ve öğrenci deneyimini doğrulama. |

### Öğrenci arayüzü: TalkBack/VoiceOver uyumlu, “TalkBack benzeri” değil

Yeni bir ekran okuyucu veya Android Accessibility Service yazmak doğru yatırım değildir. TalkBack/VoiceOver kullanıcılarının kas hafızasını bozmamak gerekir. Uygulama şunları yapar:

- Yerel HTML anlam öğelerini (`main`, `nav`, `article`, `h1-h6`, `table`, `button`) önceliklendirir; ARIA sadece gerekli boşluğu doldurur.
- Sayfa değiştiğinde odağı başlığa taşır; modal açıldığında odağı modal içinde hapseder ve kapanınca çağıran öğeye geri döndürür.
- Swipe sırasını belge okuma sırasıyla aynı tutar; sadece CSS ile görsel sıralama değiştirilemez.
- Öğeler için kısa ve eylem odaklı ad kullanır: “Formül ayrıntısını aç”, “Tablo satır 3 sütun 2”.
- Canlı bölgeleri (`aria-live`) yalnızca işleme bitti, taslak kaydedildi gibi kısa durumlar için kullanır; uzun ders içeriğini asla tekrar okutmaz.
- Dokunma hedeflerini en az 24×24 CSS px, tercihen 44×44 yapar; odak göstergesi görünür kalır.
- Hız, ses, Braille tercihi gibi ekran okuyucu ayarlarını ele geçirmez; kullanıcı cihaz ayarını kullanır.

WCAG 2.2 özellikle mobil, az gören ve bilişsel/öğrenme farklılığı olan kullanıcıları kapsayacak ek başarı kriterleri getirir. Hedef uyumluluk: **WCAG 2.2 AA**, fakat gerçek cihaz testi bunun yerine geçmez. <https://www.w3.org/TR/WCAG22/>

### Braille stratejisi

Braille, ekranda altı nokta çizmek demek değildir. Fiziksel Braille ekranı kullanan kişi, işletim sisteminin erişilebilirlik ağacı üzerinden metni ve MathML’i kendi cihazında okur veya girer. Bu nedenle:

1. Arama alanı standart, etiketli HTML input olur; Android/iOS Braille klavyesi veya fiziksel klavyeden gelen metni normal biçimde kabul eder.
2. Uygulama, özel bir “Braille arama klavyesi” zorlamaz. Böyle bir klavye yalnızca Braille öğrenme modunda, isteğe bağlı eğitim aracı olabilir.
3. Formülün MathML yapısı ve mümkün olan yerlerde MathCAT Braille çıktısı sağlanır; hedef donanım/ülke kodu kullanıcı testiyle doğrulanmadan kesin Türkçe Braille desteği iddia edilmez.
4. Öğretmen onaylı içerik için indirilebilir BRF, ikinci faz özelliğidir; gerçek Braille kullanıcı testi olmadan yayımlanmaz.

### Görsel kullanıcı arayüzü de gereklidir

“Ekran okuyucu uyumlu” olmak görsel arayüzü terk etmek değildir. Az gören öğrenciler ve öğretmenler için:

- Üç görünüm: **Odak okuma**, **yan yana kaynak**, **yüksek kontrast**.
- Kullanıcı kontrollü yazı boyutu; iki sütunlu içeriğin dar ekranda tek sütuna yeniden akması.
- Renk tek bilgi taşıyıcısı değildir; güven durumu ikon + metin + desenle belirtilir.
- Grafiklerde renk yanında seri etiketi, çizgi tipi ve veri tablosu sağlanır.
- Öğretmen panelinde PDF kaynağı solda, erişilebilir çıktı sağda; farklar odaklanabilir liste olarak da sunulur.

### Minimum cihaz/tarayıcı test matrisi

| Senaryo | Zorunlu doğrulama |
|---|---|
| Android telefon | TalkBack + Chrome: başlık, formül, tablo, arama ve yayımlanmış ünite. |
| iPhone/iPad | VoiceOver + Safari: aynı görevler ve yeniden akış. |
| Windows | NVDA + Firefox; NVDA + Chrome: öğretmen/öğrenci temel görevleri. |
| Masaüstü düşük görme | %200 tarayıcı zoom, yüksek kontrast, yalnız klavye. |
| Braille | Mümkünse en az bir gerçek Braille ekranı kullanıcısıyla arama ve formül görevleri. |
| Öğretmen | Fare + klavye ile düzeltme, önizleme, yayın ve geri alma. |

NVDA’nın browse mode’u web sayfalarında başlık ve tek-harfli gezinme gibi belge gezinme işlevleri sunar; semantic heading yapısı bu nedenle yalnız tasarım detayı değil, temel üründür. <https://download.nvaccess.org/releases/beta/documentation/en/userGuide.html>

---

## 16. Güvenlik, stabilite ve işletim değerlendirmesi

### Mimari sınırlar

```text
Öğrenci PWA / Öğretmen web paneli
              ↓ HTTPS + OIDC oturum
API Gateway / rate limit / RBAC
      ↓                    ↓
İçerik ve sürüm API      Ayrık iş kuyruğu
      ↓                    ↓
PostgreSQL + nesne depo   İzole belge işleme worker'ları
                              ↓
                    yerel model servisi / doğrulama
```

Okuma deneyimi senkron ve hızlıdır; ağır PDF/model işleme öğrenci isteği içinde çalışmaz. Böylece model sunucusu yavaşlasa bile daha önce yayımlanmış ders içeriği kullanılabilir kalır.

### Rol ve yetki modeli

| Rol | Yetkiler | Yapamayacağı |
|---|---|---|
| Öğrenci | Yayımlanmış üniteleri okuma, kişisel yer imi/isteğe bağlı ilerleme | Kaynak PDF görme, taslak değiştirme, başka kullanıcının verisine erişme. |
| Öğretmen | Kendine atanmış içerikte taslak inceleme, düzeltme ve yayın önerisi | Model yapılandırması değiştirme, kurum dışı içeriğe erişme. |
| Onaylayıcı | Yayın/geri alma ve sürüm karşılaştırması | Altyapı veya ham kişisel veri yönetimi. |
| Yönetici | Yetki, kaynak sürümü, denetim kaydı ve sistem sağlığı | Ders içeriğini LLM’e dışarı aktarma yetkisi varsayılan değildir. |

Öğretmen/yönetici için OIDC tabanlı giriş, mümkünse okul/üniversite kimlik sağlayıcısı; yüksek yetkiler için MFA uygulanır. Yetki kontrolü yalnız arayüzde değil her API çağrısında yapılır.

### PDF, dosya ve model güvenliği

- Öğrenciler kaynak PDF yüklemez; yükleme yalnız yetkili öğretmen/yönetici akışındadır.
- Sunucu tarafında dosya uzantısı değil magic-byte/MIME, boyut, sayfa sayısı ve şifreli PDF kontrol edilir.
- Yüklenen PDF, antivirüs ve mümkünse Content Disarm & Reconstruct işleminden geçer; doğrudan webden sunulmaz.
- Ayrıştırıcılar ağ erişimi olmayan, CPU/RAM/süre limitli izole worker konteynerlerinde çalışır. Çıktı, ayrı nesne deposuna yazılır.
- Model, adapter ve veri paketleri sürüm sabiti, checksum ve lisans kaydıyla indirilir; rastgele Hugging Face `main` dalından üretime yükleme yapılmaz.
- Model çıktısı HTML olarak doğrudan render edilmez; izinli şema, temizleme ve server-side doğrulama zorunludur.

OWASP, dosya yüklemelerinde PDF/DOCX gibi türler için CDR ve çalıştırmadan önce tarama önerir. <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>

### LLM/RAG güvenliği

RAG veya LLM eklenirse, belge metni **talimat değil veri** olarak işlenir. LLM’in; yayın yapma, kullanıcı verisi okuma, dosya indirme, ağ isteği atma ya da yetki değiştirme aracı yoktur.

- Sistem ve kullanıcı istemleri ayrı tutulur; modelden gelen JSON şemayla doğrulanır.
- RAG yalnız yayınlanmış, checksum’lı ve insan onaylı içerik indeksinden getirir.
- İçeriğe gömülü “önceki talimatları yok say” gibi prompt injection metinleri modelin talimat kanalı olamaz.
- Araç çağrısı yoktur; öğretmen onayı ve normal API yetkisi olmadan model hiçbir yan etki oluşturamaz.
- Kullanıcı sorguları/yanıtları için istek limiti, token limiti, zaman aşımı ve maliyet kotası uygulanır.
- Prompt injection, kaynak zehirleme, hassas bilgi sızıntısı, model tedarik zinciri ve sınırsız tüketim için adversarial test seti tutulur.

OWASP’ın 2025 LLM risk listesinde prompt injection, hassas bilgi sızıntısı, tedarik zinciri, veri/model zehirleme ve sınırsız tüketim ayrı riskler olarak tanımlanır. <https://genai.owasp.org/llm-top-10/?cat=44>

### Stabilite/SRE hedefleri

| Alan | Hedef / mekanizma |
|---|---|
| Okuma kullanılabilirliği | Yayımlanmış içerik API’si aylık %99,5 hedef; PWA son açılan üniteyi çevrimdışı açabilir. |
| İşleme dayanıklılığı | Idempotency anahtarı, iş durumu, üstel backoff, maksimum deneme, dead-letter queue. |
| Model hatası | Zaman aşımı/circuit breaker; mevcut yayımlanmış sürümü bozmaz, iş “denetim bekliyor”a düşer. |
| Veri dayanıklılığı | Şifreli günlük yedek, geri yükleme tatbikatı, nesne deposu sürümleme, silme saklama politikası. |
| Yayın güvenliği | Staging, kalite kapısı, canary yayın, tek tık geri alma. |
| Gözlemlenebilirlik | Trace ID, metrikler, hata oranı, kuyruk yaşı, kaynak tüketimi, düşük güven oranı; içerik/kişisel veri loglanmaz. |
| Erişilebilirlik regresyonu | Her değişiklikte axe-core/playwright; sürüm öncesi ekran okuyucu duman testi. |

OWASP ASVS; yetkilendirme başarısızlıklarının ve güvenlik olaylarının kaydını, ayrıca hassas verinin loglarda korunmasını doğrulama gereği olarak ele alır. <https://github.com/OWASP/ASVS/blob/master/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.json>

### Teslim öncesi yeniden doğrulama listesi

1. 9. sınıf Matematik pilotu için seçilen PDF sürümü, lisans/telif notu ve hash sabittir.
2. Gold test kümesi geliştirme verisinden ayrıdır; metrikler tekrar koşuda aynı üretilir.
3. Android TalkBack, iOS VoiceOver, NVDA/Firefox ve NVDA/Chrome görevleri kayda geçirilmiştir.
4. Bir Braille ekran kullanıcısıyla en az bir formül ve arama senaryosu denenmiştir; mümkün değilse bu açık sınırlılıktır.
5. OWASP dosya yükleme ve LLM/RAG tehdit modeli üzerinden kontrol edilmiştir.
6. Öğretmen düzeltme → önizleme → yayın → geri alma zinciri test edilmiştir.
7. Ağ/model sunucusu kapalıyken yayımlanmış içeriğin okunabilirliği test edilmiştir.
8. Tüm açık kaynak bileşenleri için lisans, sürüm, checksum ve kullanım amacı içeren yazılım/model envanteri vardır.

---

## 17. Model seçimi: görev başına en küçük yeterli model

### Temel karar

Tek, çok büyük bir model bütün hattı çalıştırmayacaktır. Belgede her görevün hata türü farklıdır; doğru yaklaşım **göreve uzmanlaşmış küçük model + doğrulama + gerektiğinde daha güçlü fallback** yapmaktır. Büyük genel VLM’i her sayfaya çağırmak; yavaş, pahalı ve denetlenmesi güçtür. Çok küçük genel modeli her karmaşık göreve zorlamak ise formül/grafik hatalarını artırır.

Bu nedenle önerilen nihai aday dizisi şöyledir:

| Görev | Birincil aday | İkinci aday / fallback | Eğitim kararı |
|---|---|---|---|
| Dijital-doğumlu PDF metni | PDF metin katmanı + PyMuPDF/Docling | — | Eğitim yok. |
| Taranmış metin, düzen, tablo, formül bölgeleri | **PaddleOCR-VL 1.5 (0.9B)** | Granite-Docling 258M + Docling klasik hat | Eğitim yok; önce benchmark. |
| Belge ayrıştırma güven çapraz kontrolü | **Granite-Docling 258M** | PaddleOCR-VL sonucu ile uyuşmazlık kontrolü | Eğitim yok. |
| Formül görseli → LaTeX/MathML | Pix2Text/Pix2TeX + render doğrulama | Kaynak-LaTeX ve insan denetimi | Eğitim yok. |
| Raster grafik → sıkı JSON veri şeması | **Qwen3-VL 4B Instruct** | Qwen3-VL 2B Instruct hızlı/ucuz baseline | Yalnız bu görevde koşullu QLoRA. |
| Kaynaklı ders içi arama/RAG | Çok dilli embedding + BM25; küçük quantize metin modeli | Kaynak yetersizse cevap yok | Eğitim yok. |
| Türkçe ses | Mevcut yerel TTS + MathCAT/SSML benchmarkı | İkinci TTS motoru | Başta eğitim yok; test başarısızsa dar LoRA. |

### Neden bu boyutlar?

**PaddleOCR-VL 1.5 — belge hattı için birincil aday.** 0.9B parametre olmasına rağmen belge ayrıştırma için özel tasarlanmıştır; dinamik çözünürlüklü görsel kodlayıcı kullanır, 111 dili desteklediğini belirtir ve Apache-2.0 lisanslıdır. Bu iş için 7B/8B genel VLM’den daha doğru başlangıçtır; çünkü amacı OCR, düzen, tablo ve formül öğesidir. <https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html>

**Granite-Docling 258M — küçük ama anlamlı karşılaştırma ve fallback.** End-to-end belge dönüşümü için özel üretilmiş, DocTags ile düzen/tablo/formül hiyerarşisini koruyan ve Apache-2.0 lisanslı bir modeldir. 258M olduğu için “kesin ana model” değil; MEB testinde PaddleOCR-VL’e yeterince yakın kalırsa hızlı/ekonomik fallback ve çapraz denetimdir. <https://www.ibm.com/granite/docs/models/docling>

**Qwen3-VL 4B — grafik eğitim modeli için önerilen boyut.** 2B, ilk inference baseline’ı için değerlidir ama grafiklerde eksen, seri, birim ve sayısal ilişkiyi aynı anda anlamak için gereksiz risk taşır. 4B, 2B’ye göre görsel belge ve grafik muhakemesinde belirgin daha güçlü bir ara boyuttur; 8B ise 30 saat T4 bütçesinde QLoRA, görüntü çözünürlüğü ve tekrar deneyleri için gereksiz bellek/latency riski oluşturur. Qwen3-VL ailesi 2B, 4B, 8B ve daha büyük yoğun modeller sunar. <https://github.com/QwenLM/Qwen3-VL>

**8B/32B neden seçilmiyor?** Bunlar kalite oracle’ı olarak az sayıda offline örnekte karşılaştırılabilir; fakat ilk sürümün sürekli işleyen hattında seçilmez. 8B QLoRA T4 üzerinde teknik olarak mümkün olsa bile batch boyutu, görüntü tokenı ve deney sayısı düşer. 32B ise ürünün gecikme, maliyet ve yerel çalıştırma hedefini bozar. Büyük modelle alınan küçük bir benchmark artışı, öğrenci deneyimindeki gerçek hata oranını düşürmüyorsa değer üretmez.

### 2B, 4B ve 8B için açık seçim eşiği

Grafik altın kümesinde aynı prompt, aynı kırpım ve aynı JSON şemasıyla aşağıdaki karşılaştırma yapılır:

| Ölçüt | 2B seçilir | 4B seçilir | 8B yalnız değerlendirilir |
|---|---|---|---|
| Sayısal değer hatası | 4B’den en fazla %5 göreli kötü | 2B’ye göre anlamlı iyileşme sağlar | 4B’ye göre önceden belirlenen anlamlı artış sağlarsa. |
| Seri/eksen/birim doğruluğu | Kritik hata yok | Kritik hata oranını düşürür | 4B’de kalan kritik hatayı azaltırsa. |
| T4 bellek ve hız | Hedefin altında | Hedefin altında | Hedefi bozmadığı kanıtlanırsa. |
| Fine-tune verimi | QLoRA sonrası yeterli | **Varsayılan eğitim adayı** | 4B hedefi geçemezse, kalan GPU ile küçük pilot. |

Varsayılan karar: **Qwen3-VL 4B Instruct + 4-bit NF4 QLoRA**. 2B aynı veri üzerinde baseline olarak mutlaka ölçülür. 8B, yalnız 4B başarısız olursa ya da sadece küçük “oracle” değerlendirmesi için kullanılır; ilk eğitim hedefi değildir.

### Model seçme deneyi: isim değil kanıt

Model seçimi ilk iki haftada 25–30 sayfalık, geliştirme dışında tutulan MEB-STEM-Mini-Gold ile yapılır. Kümede dijital PDF, düşük kaliteli tarama, metin, karmaşık formül, tablo ve grafik örnekleri dengeli bulunur.

| Görev | Ölçüm | Hata maliyeti |
|---|---|---|
| Metin | Türkçe CER/WER, okuma sırası doğruluğu | Orta |
| Formül | sembol F1, render eşdeğerliği, kritik operatör hatası | Çok yüksek |
| Tablo | TEDS, başlık-hücre ilişkisi | Çok yüksek |
| Grafik | veri MAE/MAPE, seri-etiket eşleşmesi, eksen/birim doğruluğu, uydurma oranı | Çok yüksek |
| Operasyon | saniye/sayfa, GPU VRAM tepe değeri, hata/timeout oranı | Yüksek |
| Erişilebilirlik | TalkBack/NVDA görev başarısı ve düzeltme yükü | Çok yüksek |

Her aday için sonuçlar aşağıdaki gibi tek bir karar kartına yazılır:

```text
model sürümü + checksum
veri kümesi sürümü + sayfa türleri
donanım + quantization + prompt/ayar
doğruluk metrikleri + kritik hata örnekleri
gecikme + VRAM + lisans
seç / reddet gerekçesi
```

Model yalnız genel ortalaması yüksek olduğu için seçilemez. Örneğin OCR WER’i iyi ama eksi işaretini kaçırıyorsa formül yolu için reddedilir. Bu karar kartı rapora ve model envanterine girer.

### Eğitim için kesin öneri

GPU ile eğitilecek **tek temel model**, benchmark kapısını geçemezse Qwen3-VL 4B’nin grafik→JSON görevi için LoRA adapter’ıdır. Eğitim çıktısı temel modelin kopyası değil, sürümü ve veri manifesti kayıtlı küçük adapter olur.

```text
Qwen3-VL 4B Instruct (4-bit NF4, dondurulmuş temel ağırlıklar)
       +
LoRA adapter (görsel katman/uygun attention katmanları)
       +
Synthetic-Chart-TR + insan doğrulamalı MEB grafik eğitim bölümü
       ↓
Şemaya bağlı JSON çıktı
       ↓
Pydantic doğrulaması + grafik yeniden çizimi + güven kalibrasyonu
```

Eğitimde başarı ölçütü “daha güzel açıklama” değil, held-out grafikte sayısal hatanın ve kritik eksen/seri hatalarının baseline’a göre düşmesidir. Düşmezse adapter kullanılmaz; proje bunu negatif fakat değerli deney sonucu olarak raporlar.

### TTS ve embedding modelini hemen sabitlememe nedeni

TTS modeli için doğru seçim, genel Türkçe ses benchmarkıyla değil **MathTR-Readings** ile yapılır: kesir, üs, kök, fonksiyon, birim, negatif sayı ve tablo hücresi örneklerini öğrencinin anlayıp anlamadığı ölçülür. TTS’yi bu testten önce eğitmek GPU harcamaktır.

Embedding modeli de RAG başlamadan seçilmez. Türkçe ders kitabı başlıkları, formül çevresindeki metin ve öğrenci sorgularından oluşan ayrı retrieval kümesinde `Recall@k`, Türkçe sorgu eşleşmesi ve kaynak sayfa doğruluğu ölçülür. En küçük yeterli çok dilli embedding modeli seçilir; öğrenci arama hızı bundan faydalanmıyorsa RAG eklenmez.
