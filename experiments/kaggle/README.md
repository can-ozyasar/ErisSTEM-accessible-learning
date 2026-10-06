# Kaggle T4 benchmark çalışma paketi / Kaggle T4 benchmark package

1. Kaggle'da **Private** Python Notebook oluşturun.
2. Settings > Accelerator altında GPU seçin; Internet yalnız ilk paket kurulumu için açık olsun.
3. Gerçek MEB PDF ve `gold-v1-annotated.json` dosyasını yalnız **Private Dataset** olarak ekleyin. Dataset, notebook ve output public yapılmaz.
4. Bu dizini notebook'a yükleyin veya ilgili runner içeriğini hücreye yapıştırın. Kod private input yolunu kullanır: `/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-gold-benchmark-v1`.
5. Çıktıda yalnız environment/metric/prediction artefact'larını tutun; PDF veya sayfa görselini public output olarak kaydetmeyin.

Yerelde, Gold anotasyonları varsa private manifesti üretin:

```bash
cd apps/api
python -m app.pipeline.export_gold --manifest ../../data/derived/gold-v1.json --output ../../data/derived/gold-v1-annotated.json
```

Kaggle'ın Notebook ayarları GPU, internet ve input veri kaynaklarını yapılandırır; private Dataset paylaşımı Notebook paylaşımından ayrıdır. Ayrıntılar: [Kaggle Notebooks dokümantasyonu](https://www.kaggle.com/docs/notebooks) ve [Kaggle Datasets dokümantasyonu](https://www.kaggle.com/docs/datasets).

Notebook hücresi: `!python /kaggle/working/benchmark_runner.py`

İlk çalıştırma yalnız Docling baseline üretir ve seçili 18 sayfayı işler. `docling_predictions.json` MEB'den türetilmiş içerik taşıdığından private notebook output'unda kalır. Gold anotasyonları eksikse metadata bunu `blocked_missing_gold_annotations` olarak kaydeder.

## İkinci aday: PaddleOCR-VL / Second candidate: PaddleOCR-VL

T4 (CC 7.x) için vLLM seçilmez; resmi dokümantasyon bu kartlarda zaman aşımı veya bellek taşması riski belirtiyor. `paddleocr_vl_runner.py`, tam belge ayrıştırma hattını resmi `transformers` motoruyla başlatır ve modeli GPU'ya yalnız **bir kez** yükler; tüm Gold sayfaları aynı pipeline ile işlenir. Tablo, formül, grafik ve okuma sırası çıktıları private artefact olarak tutulur.

1. Notebook **Internet** ayarını yalnız bu ilk model indirmesi için açın ve GPU olarak T4 seçili kalsın.
2. Yeni bir kod hücresine `paddleocr_vl_runner.py` dosyasının tamamını yapıştırıp çalıştırın. Dosyanın sonundaki koruma bloğu notebook'ta `main()` fonksiyonunu zaten bir kez çağırır; ayrıca çağırmayın.
3. Yalnız aşağıdaki özetleri paylaşın: `run_metadata.json`, `run_records.json` içindeki `status` sayıları ve `structural_report.json` içindeki `by_kind` alanı. `results/` içeriğini, PDF'yi veya sayfa görüntülerini paylaşmayın.

Runner terminale yalnız `[n/18] İşleniyor/Tamamlandı/Başarısız` durum satırlarını yazar. Bu satırlar belge içeriği içermez; süreç takibi için güvenle paylaşılabilir.

`structural_report.json` ham MEB metni ya da görüntüsü içermez. Her örnek için yalnız beklenen yapı sinyalinin (ör. formül, tablo veya grafik) varlığı, yapı etiketlerinin sayısı ve bbox sayısı bulunur. Bu rapor **doğruluk skoru değildir**: doğru model seçimi için sonraki aşamada yalnız az sayıdaki Gold örneğinin doğrulanmış beklenen değerleriyle içerik metrikleri hesaplanır.

Her koşum, konfigürasyon kimliği altında (`runs/paddleocr-vl-1.6-transformers-chart-v1/`) saklanır. Aynı konfigürasyon yeniden başlatılırsa yalnız o konfigürasyonun yarım kalmış private artefact'ları temizlenir; önceki Docling ve Paddle smoke-test sonuçları silinmez.

Başarılı koşum sonunda `run_records.json` 18 kaydın her biri için private artefact dosya yollarını ve SHA-256 değerlerini tutar. Boş `expected` alanları varken sonuç yine bilinçli olarak `blocked_missing_gold_annotations` kalır: bu, model seçimini varsayıma göre yapmamızı engeller.

For a T4 (CC 7.x), this runner deliberately avoids vLLM. It uses the official Transformers engine for the full document-parsing pipeline and records only private output artefact paths and SHA-256 checksums. Keep the model-download Internet setting temporary, and never publish PDFs, page images, annotations, or `results/` outputs.

## Görsel bölge tablo deneyi / Visual-region table experiment

Mevcut üçlü private görsel bölge Dataset yolu: `/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-table-gold-regions-v1`.

1. Private Notebook'ta T4 ve yalnız model indirme süresince Internet etkin olmalıdır.
2. `visual_region_runner.py` dosyasının tamamını yeni bir hücreye yapıştırıp bir kez çalıştırın.
3. Yalnız `run_metadata.json`, `region_records.json` ve `native_agreement_report.json` içeriğini paylaşın. `table_drafts.json`, `results/`, görsel crop, native kanıt veya model işaretlemesini paylaşmayın.

Runner, tam PDF yerine yalnız checksum ile doğrulanan private crop'ı işler. Modelin tablo işaretlemesi doğrudan HTML olarak kullanılmaz; yalnız bir adet güvenle ayrıştırılabilen tablo işaretlemesi, düşük güvenli ve öğretmen denetimli JSON hücre taslağına dönüştürülür. Birden çok/hiç tablo işaretlemesi veya şema sorunu koşumu `blocked` yapar; yayın kapalı kalır.

The runner processes only the checksum-verified private crop, never a full PDF. Model table markup is never used as direct HTML: exactly one safely parsed table becomes a low-confidence, teacher-reviewed JSON cell draft. Zero/multiple table markups or a schema issue produces `blocked`; publication remains disabled.

When the private Dataset includes `native-table-evidence-v1.json`, the runner also creates a content-free native-source token-agreement proxy. This is deliberately not a Gold accuracy score, a model-selection decision, or a publishing decision; it only prioritises disagreements for later Gold review.

Do not publish the MEB PDF, page images, annotations, or notebook outputs. Qwen3-VL 4B QLoRA is explicitly out of scope until Docling/Paddle baselines fail the recorded Gold gates.
