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

If the mathematical token normaliser changes, `rescore_native_agreement.py` re-scores the existing private `table_drafts.json` without downloading or running the model again. Share only its content-free report.

## Güvenli Kaggle API işlemleri / Safe Kaggle API operations

`kaggle_ops.py`, token'ı okumaz veya repo içine yazmaz; `kagglehub` yalnız kullanıcının yerel kimlik deposunu kullanır. Kaynak olarak sadece `data/private/` altındaki klasör kabul edilir. Uzak Dataset sürümü oluşturmak için ayrıca `--apply` gerekir; aksi hâlde yalnız checksum içeren private işlem kaydı yazılır.

```bash
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py verify
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-dataset \
  --source-dir data/private/eristem_meb9_table_gold_regions_v2 \
  --handle muhammedcanozyasar/eristem-meb9-table-gold-regions-v2 \
  --version-notes "Private native evidence package"
```

Do not add `--apply` unless the exact private folder and target Dataset version have been reviewed. Operation records remain under ignored `data/private/kaggle-operation-records/`.

## Private Notebook orkestrasyonu / Private Notebook orchestration

`kaggle_ops.py` artık aynı güvenlik sınırında private Notebook paketi hazırlar,
Kaggle'a gönderip GPU koşumunu başlatır ve yalnız allowlist'teki özet JSON
dosyalarını indirir. Kod ve indirilen çıktılar `data/private/` altında kalır;
runner ham PDF, crop, `results/`, `table_drafts.json` veya model Markdown'ını
indiremez. `push-notebook` uzaktaki private Notebook'u oluşturur/günceller ve
çalıştırır; bu nedenle ancak gerçek yeni bir benchmark gerektiğinde `--apply`
ile kullanılır.

```bash
# 1. Bir kez: V2 Paddle tablosu için yerel private Notebook paketi oluştur.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-notebook \
  --kernel muhammedcanozyasar/eristem-private-table-benchmark-v2 \
  --dataset muhammedcanozyasar/eristem-meb9-table-gold-regions-v2 \
  --runner experiments/kaggle/visual_region_runner.py \
  --title "ErişSTEM private table benchmark V2" --internet

# 2. Önce uzakta değişiklik yapmadan paketi doğrula.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py push-notebook \
  --package-dir data/private/kaggle-notebooks/muhammedcanozyasar/eristem-private-table-benchmark-v2 \
  --kernel muhammedcanozyasar/eristem-private-table-benchmark-v2 \
  --dataset muhammedcanozyasar/eristem-meb9-table-gold-regions-v2

# 3. Yalnız gerçek yeni koşum için: private T4 koşumunu gönder ve başlat.
# Aynı komuta --apply eklenir; ardından yalnız durum ve izinli özetler alınır.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py notebook-status \
  --kernel muhammedcanozyasar/eristem-private-table-benchmark-v2
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py download-summaries \
  --kernel muhammedcanozyasar/eristem-private-table-benchmark-v2
```

The Kaggle notebook remains private, GPU-enabled, and receives exactly one
declared private Dataset. A remote run is never started by a default command;
`--apply` is the deliberate boundary. The downloader requests only named,
content-free report files and creates a checksum manifest in the ignored private
output folder.

## Docling visual-table comparison / Docling görsel tablo karşılaştırması

`docling_visual_region_runner.py`, aynı V2 private crop ve native-kanıt paketi üzerinde Docling'i ikinci aday olarak çalıştırır. Ham Markdown yalnız private run klasöründe kalır; yalnız tek ve güvenle ayrıştırılabilen pipe-table düşük güvenli JSON taslağına dönüşür. `native_agreement_report.json` iki aday için karşılaştırılabilir içeriksiz proxy sinyalidir; Gold skoru veya yayın kararı değildir.

Do not publish the MEB PDF, page images, annotations, or notebook outputs. Qwen3-VL 4B QLoRA is explicitly out of scope until Docling/Paddle baselines fail the recorded Gold gates.

## Matematik sembol hücre benchmark'ı / Mathematical symbol-cell benchmark

Tablo geometrisi doğru olduğu hâlde sembol fontu/Unicode eşlemesinin bozulduğu
durumlarda tüm tabloyu yeniden OCR etmek yerine yalnız sorunlu hücreleri yüksek
çözünürlükte ölçeriz. `symbol_cell_benchmark.py`, öğretmen-onaylı Gold'daki
matematik-kritik hücreleri (ör. küme işlemleri ve üyelik işaretleri) kaynak PDF
koordinatından crop olarak üretir.

Kaggle'a gidecek aday paketi **cevap içermez**; beklenen semboller ayrı bir
yerel private Gold dosyasında kalır. Böylece aday modeller eşit koşulda
karşılaştırılır ve modelin Gold'u görmesi engellenir.

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.symbol_cell_benchmark \
  --input data/meb/matematik-9sinif-ders-kitabi-1kitap_2026.pdf \
  --source-root data/meb \
  --gold data/private/vector-native-table-gold-v1.json \
  --output-dir data/private/eristem_meb9_symbol_cell_benchmark_v1 \
  --gold-output data/private/eristem_meb9_symbol_cell_gold_v1.json

# Uzakta değişiklik yapmadan, gönderilecek paketi denetle.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-dataset \
  --source-dir data/private/eristem_meb9_symbol_cell_benchmark_v1 \
  --handle muhammedcanozyasar/eristem-meb9-symbol-cell-benchmark-v1 \
  --version-notes "Private high-resolution math-symbol benchmark input; expected answers retained locally"
```

`--apply` olmadan komut yalnız checksum içeren private işlem kaydı üretir;
uzak Dataset'e yükleme yapmaz. Sembol-crop sonuçları üretimde otomatik
kullanılamaz: aday tahminleri private olarak geri alındıktan sonra yalnız yerel
Gold ile skorlanır ve öğretmen/yayın kapıları yine geçerlidir. Üç tablodan
oluşan mevcut pilot, fine-tuning için eğitim verisi değildir; önce bu kapalı
benchmark üzerinde en az bir güçlü adayın kanıtlanması gerekir.

İlk aday için runner, sadece tek tahmin dosyasını üretir. Ham model sonucu,
PDF veya Gold Notebook output'undan indirilmez. Aşağıdaki dört komut sırasıyla
private Dataset sürümünü yükler, private T4 Notebook paketini hazırlar,
çalıştırır ve yalnız doğrulanmış tahmin dosyasını yerelde private alana getirir:

```bash
# Bu iki --apply komutu uzak private Kaggle kaynağını değiştirir.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py upload-dataset \
  --source-dir data/private/eristem_meb9_symbol_cell_benchmark_v1 \
  --handle muhammedcanozyasar/eristem-meb9-symbol-cell-benchmark-v1 \
  --version-notes "Private sealed math-symbol candidate input v1" --apply

apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-notebook \
  --kernel muhammedcanozyasar/eristem-private-symbol-cell-paddleocr-v1 \
  --dataset muhammedcanozyasar/eristem-meb9-symbol-cell-benchmark-v1 \
  --runner experiments/kaggle/symbol_cell_paddleocr_runner.py \
  --title "Eristem Private Symbol Cell Paddleocr V1" --internet

apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py push-notebook \
  --package-dir data/private/kaggle-notebooks/muhammedcanozyasar/eristem-private-symbol-cell-paddleocr-v1 \
  --kernel muhammedcanozyasar/eristem-private-symbol-cell-paddleocr-v1 \
  --dataset muhammedcanozyasar/eristem-meb9-symbol-cell-benchmark-v1 --apply

apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py download-symbol-predictions \
  --kernel muhammedcanozyasar/eristem-private-symbol-cell-paddleocr-v1 \
  --input-manifest data/private/eristem_meb9_symbol_cell_benchmark_v1/symbol-cell-manifest.json
```

İndirilen `symbol_predictions.json`, yalnız private çıktı klasöründe kalır.
Sonra bunu yerel Gold ile skorlayın; rapor beklenen sembolleri veya modelin ham
metnini içermez:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.symbol_cell_evaluation \
  --input-manifest data/private/eristem_meb9_symbol_cell_benchmark_v1/symbol-cell-manifest.json \
  --gold data/private/eristem_meb9_symbol_cell_gold_v1.json \
  --predictions data/private/kaggle-notebook-outputs/.../symbol_predictions.json \
  --output data/private/symbol-cell-paddleocr-evaluation-v1.json
```

## Türkçe STEM TTS aday benchmark'ı

`tts_chatterbox_runner.py`, yalnız private `tts-gold-v1.json` içindeki önceden
doğrulanmış `expected_spoken_text` birimlerinden Chatterbox Multilingual V3
ile Türkçe WAV üretir. Çalıştırıcı bir sesi öğrenciye yayımlamaz, sesletim
kalitesi puanı üretmez ve fine-tuning yapmaz. WAV'lar private Notebook
çıktısında kalır; yalnız içeriksiz `run_metadata.json` ve `run_records.json`
özetleri otomatik olarak indirilebilir.

Girdi Dataset'i `tts-gold-v1.json` dosyasını tek başına veya tek bir zip
içinde taşımalıdır. Bu manifest, yalnız yayın eşiğini geçmiş kanonik bloklardan
yerelde `build_tts_gold` ile üretilir. Dinleme/ASR transkriptleri Kaggle
çalıştırıcısına değil, private yerel değerlendirme sürecine girer; sonuç
`app.pipeline.tts_quality` ile skorlanır.

```bash
# Önce yalnız göndereceğiniz private Gold paketinin checksum kaydını oluşturun.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-dataset \
  --source-dir data/private/eristem_meb9_tts_gold_v1 \
  --handle muhammedcanozyasar/eristem-meb9-tts-gold-v1 \
  --version-notes "Private verified Turkish STEM TTS evaluation input v1"

# Notebook paketi private, GPU'lu ve yalnız bu Dataset'e bağlıdır.
apps/api/.venv/bin/python experiments/kaggle/kaggle_ops.py prepare-notebook \
  --kernel muhammedcanozyasar/eristem-private-tts-chatterbox-v1 \
  --dataset muhammedcanozyasar/eristem-meb9-tts-gold-v1 \
  --runner experiments/kaggle/tts_chatterbox_runner.py \
  --title "Eristem Private Tts Chatterbox V1" --internet
```

`upload-dataset --apply` ve `push-notebook --apply` yalnız manifest içeriği,
model kartı/lisans kaydı ve örnek sayısı gözden geçirildikten sonra kullanılır.
Ses dosyaları ders içeriği taşıdığından genel çıktı indirme aracının allowlist'ine
eklenmez; dinleyici incelemesi gerekiyorsa yalnız ilgili private Kaggle output
elle, private saklama alanına alınır. 50+ Gold örnek, %98+ sesletim, kritik
matematik belirteçlerinde %100 ve kör dinleyici testi geçilmeden ses modeli
ürün varsayılanı olmaz.
