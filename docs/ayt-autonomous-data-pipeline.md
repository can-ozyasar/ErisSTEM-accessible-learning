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

## QLoRA kabul sırası

Otomatik adaylar önce kaynak kesiti üzerinden incelenir. İnceleme sonrası
altı koçluk durumunun tamamı bulunan soru grupları private QLoRA dışa
aktarımına girer. Kaggle paketi PDF, koordinat, cevap anahtarı, çözüm metni,
öğrenci verisi ve kapalı test içermez. `history_tutor_qwen14b_qlora.py`,
Qwen3-14B için NF4 4-bit QLoRA, completion-only loss ve grup bazlı split
doğrulamasını uygular.

## Geçerli durum

Mevcut 80 grup / 480 tur, `agent_reviewed_only` araştırma pilotudur. Bu
durum üretim modeli veya öğrenci çalışma zamanı için onay anlamına gelmez.
Kaynak kapsama denetimindeki eksik sorular, yeni atom-bağlam çıkarımı ve
ilişki grafiğiyle tamamlanmadan eğitim başlatılmaz.
