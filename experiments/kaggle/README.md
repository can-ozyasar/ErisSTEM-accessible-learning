# Kaggle T4 benchmark çalışma paketi / Kaggle T4 benchmark package

1. Kaggle'da **Private** Python Notebook oluşturun.
2. Settings > Accelerator altında GPU seçin; Internet yalnız ilk paket kurulumu için açık olsun.
3. Gerçek MEB PDF ve `gold-v1-annotated.json` dosyasını yalnız **Private Dataset** olarak ekleyin. Dataset, notebook ve output public yapılmaz.
4. Bu dizini notebook'a yükleyin veya `benchmark_runner.py` içeriğini hücreye yapıştırın.
5. Çıktıda yalnız environment/metric/prediction artefact'larını tutun; PDF veya sayfa görselini public output olarak kaydetmeyin.

Yerelde, Gold anotasyonları varsa private manifesti üretin:

```bash
cd apps/api
python -m app.pipeline.export_gold --manifest ../../data/derived/gold-v1.json --output ../../data/derived/gold-v1-annotated.json
```

Kaggle'ın Notebook ayarları GPU, internet ve input veri kaynaklarını yapılandırır; private Dataset paylaşımı Notebook paylaşımından ayrıdır. Ayrıntılar: [Kaggle Notebooks dokümantasyonu](https://www.kaggle.com/docs/notebooks) ve [Kaggle Datasets dokümantasyonu](https://www.kaggle.com/docs/datasets).

Do not publish the MEB PDF, page images, annotations, or notebook outputs. Qwen3-VL 4B QLoRA is explicitly out of scope until Docling/Paddle baselines fail the recorded Gold gates.
