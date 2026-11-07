# Kaynak Bağlı AYT Veri Tamamlama Hattı

Bu hat, eksik kanıt kapsamasını rastgele soru ya da cevap anahtarıyla
tamamlamaz. Girdi yalnız onaylı bilgi grafiği düğümleri, kaynak koordinatlı
alıntılar ve onaylı ilişki kenarlarıdır.

## Akış

1. `QuestionAnalyzerAndEliminator`, soru kökündeki olumsuzluk, kronoloji ve
   yorum gereksinimini saptar. Doğrudan destek zayıfsa şık seçmek yerine
   açık çelişkileri eleyerek ilerler.
2. `HistoryTeacherValidatorAgent`, tek atomlu doğrudan desteği veya en çok
   üç atomdan oluşan, aynı şık zincirinde bağlı sınırlı çıkarımı önerir.
   Bu sonuç araştırma adayıdır; insan öğretmen onayı değildir.
3. `GraphToQuestionGenerator`, yalnız kaynak checksum'ı, sayfası,
   koordinatı ve alıntısı bulunan onaylı ilişki kenarlarından private soru
   taslağı üretir. Taslağın cevap etiketi `QuestionItem` çalışma zamanı
   şemasına aktarılmaz.
4. `ConceptBasedDataSplitter`, ortak kişi, olay, yer, dönem, kavram ya da
   ilişki taşıyan kayıtları transitif olarak aynı veri bölümünde tutar.
   Böylece eğitim, geliştirme ve kapalı test arasında kavram sızıntısı
   önlenir.

`export_autonomous_graph_qlora.py`, bu dört adımı private bir graf üzerinde
çalıştırır. Kaynak izli taslakları altı koçluk turuna dönüştürür; yalnız
`train.jsonl` ve `dev.jsonl` Kaggle dizinine yazılır. `sealed_test.jsonl` ve
cevap etiketi taşıyan taslaklar yerelde, ayrı dizinde kalır.

Graf kenarının kaynakta bulunması tek başına yeterli değildir.
`GeneratedDraftQualityGate`, split'ten önce konuşulabilir soru kökünü
doğrular: satır sonu OCR bölünmesi, kırpılmış tarih, cümle boyunda düğüm,
bozuk beşli şık ve eksik dil bilgisi olan taslakları reddeder. PDF'deki
`ilişki- lerinde` türü satır sonları yalnız konuşma metninde deterministik
olarak birleştirilir; checksum, sayfa ve koordinat korunur ve çıkarma yöntemi
normalizasyonu belirtir. Aynı cümlede geçen her olay-yıl çifti ilişki değildir:
adlandırılmış olay-yıl kenarı ancak doğrudan eylem fiili veya bitişik tarih
kalıbı bulunduğunda üretilir.

## QLoRA kabul sırası

Otomatik adaylar önce kaynak kesiti üzerinden incelenir. İnceleme sonrası
altı koçluk durumunun tamamı bulunan soru grupları private QLoRA dışa
aktarımına girer. Kaggle paketi PDF, koordinat, cevap anahtarı, çözüm metni,
öğrenci verisi ve kapalı test içermez. `history_tutor_qwen14b_qlora.py`,
Qwen3-14B için NF4 4-bit QLoRA, completion-only loss ve grup bazlı split
doğrulamasını uygular.

## Deney kaydı ve geçerli durum

Kaggle'daki teknik QLoRA smoke testi tamamlandı: Qwen3-14B sabit sürümü,
NF4 4-bit taban, fp32 LoRA ana ağırlıkları, üç epoch, 168 eğitim ve 36
geliştirme turu. Adaptör üretildi. Bu küçük setin `eval_loss` değeri yalnız
optimizasyon sinyalidir; taban modele karşı pedagojik kalite kanıtı değildir.

İlk 180 tersine üretilmiş taslağın kalite denetimi, uzun atomların ve OCR
artıklarının konuşulamaz soru ürettiğini ortaya çıkardı. Bu bulgu sonrasında
kalite kapısı ve olay-yıl ilişki denetimi eklendi. Yeni 120+ grubun eğitimi,
kapalı testte kullanılacak grup ayrımı, kaynak bağlılık ve erken cevap ifşası
değerlendirmesi hazır olmadan başlatılmaz. Araştırma çıktısı öğrenci çalışma
zamanına alınmaz; `research_only` sınırı korunur.
