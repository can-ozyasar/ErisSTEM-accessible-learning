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
3. Yalnız aşağıdaki özetleri paylaşın: `run_metadata.json`, `run_records.json` içindeki `status` sayıları ve terminal hatası varsa hata metni. `results/` içeriğini, PDF'yi veya sayfa görüntülerini paylaşmayın.

Başarılı koşum sonunda `run_records.json` 18 kaydın her biri için private artefact dosya yollarını ve SHA-256 değerlerini tutar. Boş `expected` alanları varken sonuç yine bilinçli olarak `blocked_missing_gold_annotations` kalır: bu, model seçimini varsayıma göre yapmamızı engeller.

For a T4 (CC 7.x), this runner deliberately avoids vLLM. It uses the official Transformers engine for the full document-parsing pipeline and records only private output artefact paths and SHA-256 checksums. Keep the model-download Internet setting temporary, and never publish PDFs, page images, annotations, or `results/` outputs.

Do not publish the MEB PDF, page images, annotations, or notebook outputs. Qwen3-VL 4B QLoRA is explicitly out of scope until Docling/Paddle baselines fail the recorded Gold gates.
