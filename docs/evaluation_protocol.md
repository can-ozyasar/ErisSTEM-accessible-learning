# Değerlendirme protokolü / Evaluation protocol

Durum: İlk sürüm, ölçüm yapılmadan önce sabitlenmiştir.

## Türkçe

Geliştirme (`MEB-STEM-Dev`) ve kilitli test (`MEB-STEM-Gold`) kümeleri sayfa, kitap sürümü ve neredeyse aynı şablon düzeyinde ayrılır. Gerçek MEB verisi veya sayfa görseli bu depoya konmaz; yalnız checksum, sürüm manifesti ve anonim metrikler kaydedilir.

| Alan | Ölçüm | Yayın kapısı |
|---|---|---|
| Metin | Türkçe CER/WER, okuma sırası | Eşik Gold kümede önceden belirlenir. |
| Formül | sembol F1, render eşdeğerliği, kritik operatör hatası | Kritik hata veya geçersiz MathML yayımlanamaz. |
| Tablo | TEDS, başlık-hücre ilişkisi | Başlık ilişkisi doğrulanmadan öğrenciye kesin içerik verilmez. |
| Güven | yüksek-güven precision, yanlışları düşük güvene alma recall'ı | Yanlış yüksek-güven oranı önceden kayıtlı sınırı aşamaz. |
| Erişilebilirlik | axe-core, klavye, NVDA+Firefox görevleri | Kritik otomatik ihlal sıfır; manuel görev kaydı zorunlu. |
| Worker | tekrar deneme, idempotency, timeout/hata oranı | Aynı checksum+sürüm ikinci iş üretmez. |

Her deney; veri manifest checksum'ı, kod commit'i, model sürümü/checksum'ı, donanım, prompt/ayar, metrik ve kritik hata örnekleriyle kaydedilir. Yeni model/kural mevcut üretim sürümünden Gold kümede kötüleşirse yayımlanmaz.

## English

Development (`MEB-STEM-Dev`) and locked test (`MEB-STEM-Gold`) sets are separated by page, book edition, and near-identical template. No real MEB data or page image is committed; only checksums, manifests, and anonymised metrics are retained.

Text uses Turkish CER/WER and reading order; formulas use symbol F1, render equivalence, and critical-operator errors; tables use TEDS plus header-cell relationships. High-confidence precision, low-confidence recall, axe-core, keyboard, NVDA+Firefox tasks, and worker idempotency are release gates. Every experiment records data checksum, code commit, model checksum, hardware, settings, metrics, and critical errors. A regression on the Gold set blocks release.
