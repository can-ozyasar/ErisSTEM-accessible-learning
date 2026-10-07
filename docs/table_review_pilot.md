# Vektör-native tablo denetim pilotu / Vector-native table-review pilot

Pilot, gerçek MEB kaynağını veya ham çıkarım çıktısını Git'e koymaz. Seçilmiş
private bölgelerden yalnız kaynak koordinatına bağlı denetim kayıtları ve sayfa
önizlemeleri üretir.

## Hazır pilot durumu

Yerel private pilotta üç tablo öğretmen kuyruğuna alındı:

- P40 sol: 12 hücre
- P40 sağ: 12 hücre
- P46: 35 hücre

Hiçbiri yayımlanmadı; tamamı `review_required` durumundadır.

## Yerelde açma

API ve web aynı private pilot veritabanını kullanmalıdır. Aşağıdaki ortam
değişkenleri token veya ham dosya yolunu tarayıcıya göndermez.

```bash
export DATABASE_URL="sqlite:///$PWD/data/private/table-review-pilot.db"
export DERIVED_ROOT="$PWD/data/derived"
PYTHONPATH=apps/api apps/api/.venv/bin/uvicorn app.main:app --reload --port 8000
```

Web uygulamasını normal geliştirme komutuyla başlatıp şu adresi açın:

```text
http://localhost:5173/?mode=table-review
```

Öğretmen yalnız sayfa görüntüsündeki turuncu kaynak kutusunu ve sade hücre
metnini görür. “Kaynakla aynı, onayla” veya “Düzelt ve onayla” öğrenci yayını
değildir. Yayın için ikinci rolün ayrı API çağrısı gerekir; öğrenci uç noktası
onaylanmamış tabloyu döndürmez.

## Tekrar üretim

Pilot içe alıcısı güvenle tekrar çalışır; var olan denetim kayıtlarını ve
öğretmen kararlarını ezmez:

```bash
DATABASE_URL="sqlite:///$PWD/data/private/table-review-pilot.db" \
PYTHONPATH=apps/api apps/api/.venv/bin/python \
  -m app.pipeline.import_vector_native_table_reviews \
  --input data/meb/matematik-9sinif-ders-kitabi-1kitap_2026.pdf \
  --source-root data/meb \
  --regions data/private/eristem_meb9_table_gold_regions_v2/visual-regions.json \
  --derived-root data/derived
```

The importer is deterministic and idempotent: it creates previews and imports
only vector/native candidates. It never imports a visual-model table draft,
does not overwrite an existing review, and never publishes a table.

## Öğretmen onayından sonraki otomatik kapı

Üç farklı tablo öğretmen tarafından onaylanmadan Gold manifesti oluşmaz. Bu
komut yalnız onaylı kayıtları private Gold biçimine dönüştürür; yeterli örnek
yoksa yalnız içeriksiz bir `blocked` raporu yazar:

```bash
DATABASE_URL="sqlite:///$PWD/data/private/table-review-pilot.db" \
PYTHONPATH=apps/api apps/api/.venv/bin/python \
  -m app.pipeline.export_teacher_table_gold \
  --output data/private/vector-native-table-gold-v1.json \
  --report data/private/vector-native-table-gold-export-report.json
```

Gold manifesti ancak üç onaydan sonra yazılır. Sonraki ölçüm, private
vector/native taslakları bu manifestle `visual_table_benchmark` üzerinden
karşılaştırır; tam hücre/yapı/rol/metin eşleşmesi sağlanmadıkça üretim adayı
onaylanmaz.
