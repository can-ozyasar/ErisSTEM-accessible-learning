# AYT Tarih deneme paketi sözleşmesi

Öğrenci denemesi varsayılan olarak yalnız sentetik erişilebilirlik provasını
gösterir. Gerçek AYT Tarih paketi ancak yetkili yerel dosya olarak hazırlanır;
Git'e, Kaggle'a veya tarayıcıya ham PDF gönderilmez.

Paketi etkinleştirmek için manifesti örneğin
`data/private/ayt-history-exam/pack-v1.json` altına koyup Compose'u şu
değişkenle başlatın:

```bash
AYT_HISTORY_EXAM_PACK=/private/ayt-history-exam/pack-v1.json docker compose up --build
```

Önce resmî MEB ders kitabı PDF'sini yalnız yerel `data/private` altında tutup
metadata kataloğunu üretin; bu komut PDF'yi kopyalamaz, Git'e eklemez ve hiçbir
API'ye göndermez:

```bash
apps/api/.venv/bin/python -m app.pipeline.register_meb_exam_source \
  --pdf data/meb/tarih-12.pdf \
  --source-id meb-tarih-12-2026 \
  --title "MEB Tarih 12. Sınıf Ders Kitabı" \
  --canonical-url "https://ogmmateryal.eba.gov.tr/..." \
  --relative-path tarih-12.pdf \
  --output data/private/ayt-history-exam/sources-v1.json
```

`--relative-path`, Compose içindeki `/private/meb` altında bulunan göreli dosya
adıdır; varsayılanı yerel PDF dosya adıdır. Çıktıdaki `sources` alanı, paket manifestindeki kaynak kataloğuna aynen
aktarılır. Araç, resmî alan adına ek olarak PDF'nin ayrıştırılabildiğini,
şifresiz olduğunu ve sayfa sayısının makul sınırda kaldığını denetler. Dosya
özeti değişirse kanıtlar yeniden incelenmeden paket yayınlanmaz.

Manifest şeması `ayt-history-exam-pack-v1` olmalı; tam **120** onaylı soru
içermelidir: 72 `development`, 24 `retrieval_test`, 24 `system_acceptance`.
Eksik, yinelenen, özgün olmadığı belirtilen, resmî MEB kaynak kataloğuna ve
checksum'ına bağlı olmayan veya görsel/tabloya bağımlı olan paket API tarafından 503 ile
reddedilir. İlk ürün kapsamı yalnız metinle çözülebilen sorulardır; doğrulanmış
bir görsel betimlemesi de bu sınırı kaldırmaz.

Her soru; `authorship: "original"`, inceleme yöntemini açıkça belirten bir
denetim izi, özgün soru/şık metni, sesletime uygun soru metni, beş benzersiz
şık, doğrulanmış cevap etiketi, kısa kaynak açıklaması ve en çok üç MEB ders
kitabı kanıtı taşır. Öğrenciye açılan pakette `review_method` yalnız
`human_pdf_crop_review` olabilir. AI destekli ön inceleme, kaynak bulma ve
kuyruk sıralama için kullanılabilir; insan PDF kırpımı incelemesi veya
öğretmen onayı olarak sunulamaz ve paketi tek başına yayımlayamaz.
Her kanıt `source_checksum`, `page`, `bbox`, kısa alıntı, kimlik ve rol
(`primary`, `context`, `relation`, `contrast`) içerir. Aktif sınavda bunlar
istemciye verilmez; teslim sonrası kaynaklı koçlukta kullanılır.

Minimal şablon:

```json
{
  "schema": "ayt-history-exam-pack-v1",
  "pack_id": "ayt-tarih-v1",
  "sources": [{
    "id": "meb-kanit-001",
    "kind": "meb_textbook",
    "title": "MEB Tarih Ders Kitabı",
    "canonical_url": "https://ogm.meb.gov.tr/ornek.pdf",
    "source_checksum": "64 karakter küçük harf hex kaynak özeti",
    "page_count": 250
  }],
  "questions": [{
    "id": "ayt-001",
    "authorship": "original",
    "review_method": "human_pdf_crop_review",
    "review_artifact_checksum": "64 karakter küçük harf hex denetim özeti",
    "topic": "Örnek konu",
    "outcome": "Örnek kazanım",
    "split": "development",
    "question": "Özgün soru metni.",
    "spoken_question": "Özgün soru metni.",
    "choices": ["A", "B", "C", "D", "E"],
    "correct_label": "A",
    "explanation": "Öğretmen onaylı kısa açıklama.",
    "evidence": [{
      "source_checksum": "64 karakter küçük harf hex checksum",
      "page": 1,
      "bbox": [1, 1, 2, 2],
      "source_id": "meb-kanit-001",
      "source_kind": "meb_textbook",
      "quote": "Kısa, öğretmenin PDF kırpımında doğruladığı alıntı.",
      "role": "primary"
    }],
    "visual_dependency": false,
    "visual_description_reviewed": false,
    "status": "approved"
  }]
}
```

Şablondaki tek soru yalnız alanları gösterir; etkin paket için belirtilen 120
soru ve dağılım zorunludur.

## İnsan PDF kırpımı inceleme kuyruğu

`original-question-candidate-pack-v2.json` yayımlanabilir paket değildir.
Önce adayların yerel PDF kaynaklarıyla denetlenebilir inceleme kuyruğunu
üretin. Çıktıdaki kırpımlar ve manifest de özeldir; Git'e veya bulut API'sine
konmaz:

```bash
apps/api/.venv/bin/python -m app.pipeline.prepare_ayt_history_question_review \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --source-catalog data/private/ayt-history-exam/sources-v1.json \
  --source-root data/meb \
  --output data/private/ayt-history-exam/human-review-v1
```

Araç yalnız `review_required` kayıtları ve yerel PDF kırpımlarını oluşturur;
hiçbir soruyu yayımlamaz. Her kayıt için soru/şık eşdeğerliği, doğru şıkkın
kanıtı, açıklama, sesletim ve yalnız metinle çözülebilirlik insan tarafından
ayrı ayrı doğrulanmalıdır. 120 kaydın tamamı bu denetimi geçmeden çalışma
zamanı manifesti oluşturulmaz.

## Kanıt sınırı onarım incelemesi

Ön denetimde alıntısı bbox içinde birebir bulunamayan adaylar için önce yerel
bir tanı kuyruğu üretilebilir. Bu araç düşük karakter benzerlikli gerçek
uyuşmazlık adaylarını, PDF metin katmanı/noktalama farkı olabilecek yakın
eşleşmelerden önce gösterir. Yalnız sınırlı sayfa bağlamı kırpımı üretir;
kanıtı, adayı veya çalışma zamanı durumunu asla kendiliğinden değiştirmez.

```bash
apps/api/.venv/bin/python -m app.pipeline.prepare_ayt_history_crop_repair_review \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --audit data/private/ayt-history-exam/candidate-pdf-crop-text-audit-v5.json \
  --source-catalog data/private/ayt-history-exam/sources-v1.json \
  --source-root data/meb \
  --output data/private/ayt-history-exam/crop-repair-review-v1
```

Üretilen `index.html` ve `manifest.json` özeldir. Bir bbox veya alıntı
düzeltmesi önerildiğinde ilgili aday yeniden denetlenir; yakın eşleşme dahi
insan PDF kırpımı incelemesinin yerine geçmez.

## Ölçüm için dondurulmuş aday bölünmesi

Yayımlanmamış adaylar üzerinde retrieval veya koçluk araştırması başlamadan
önce sabit `72/24/24` bölünmesi oluşturulur. Araç, aynı kaynak bölümündeki
adayları farklı kümelere dağıtmaz ve kaynak kitap oranlarını iki kilitli
kümede dengeler. Bu, semantic olarak benzer fakat metni farklı soru
şablonlarını saptadığını iddia etmez; yalnız tam soru metni yinelerini
farklı kaynak bölümlerinde fail-closed reddeder.

```bash
apps/api/.venv/bin/python -m app.pipeline.freeze_ayt_history_candidate_splits \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --output data/private/ayt-history-exam/candidate-split-v1.json
```

Bu manifest de özeldir ve `runtime_enabled: false` kalır. Retrieval modeli,
reranker veya QLoRA hiperparametresi yalnız 72 geliştirme kaydında seçilebilir;
24 `retrieval_test` kaydı tek seferlik karşılaştırma için ayrılır. Ölçümde
görülen bir kazanç insan PDF kırpımıyla etiketli kanıt ve kaynak güvenlik
kapıları olmadan ürün kabulü anlamına gelmez.

## Yerel atom-BM25 iz sürme baseline'ı

Kilitli 24 retrieval kaydında, adayın kaynak atom kimliğine ulaşılabildiğini
ölçmek için yerelde bütün atom corpus'u üzerinde BM25 başlangıç ölçümü alınır:

```bash
apps/api/.venv/bin/python -m app.pipeline.benchmark_ayt_history_atom_bm25 \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --split data/private/ayt-history-exam/candidate-split-v1.json \
  --corpus data/private/ayt-history-exam/multi-history-rag-v3.json \
  --output data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json
```

Bu ölçümde adaydaki kaynak atomu yalnız **iz sürme referansı**dır; insan
tarafından etiketlenmiş tam kanıt değildir. Diğer çekilen atomlar yanlış diye
varsayılmaz, `unjudged` olarak raporlanır. Bu nedenle elde edilen Recall/MRR,
BM25'in insan sorusuna verdiği pedagojik doğruluk veya ürün kabulü değildir.
Bir dense/RRF/reranker adayı ancak aynı dondurulmuş sorgularda, insan PDF
kırpımıyla etiketlenmiş tam kanıt ve yanlış kanıt kayıtlarıyla yeniden
değerlendirilebilir.

## Cevap-körü AI aday-kart incelemesi

BM25'in getirdiği üç atomun yalnız kaynak metnine göre ilk araştırma etiketi
oluşturulabilir. Hazırlık aracı soru ve beş şık ile top-3 atomu taşır;
**cevap anahtarı, açıklama ve referans atom kimliği dış servise yazılmaz**.
Bu işlem yalnız `DEEPSEEK_API_KEY` tanımlıyken, kaynak politikası izin veriyorsa
ve açık `--allow-external-private-evaluation` bayrağıyla çalıştırılır:

```bash
apps/api/.venv/bin/python -m app.pipeline.prepare_ayt_history_bm25_ai_review \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --split data/private/ayt-history-exam/candidate-split-v1.json \
  --corpus data/private/ayt-history-exam/multi-history-rag-v3.json \
  --baseline data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json \
  --queue-output data/private/ayt-history-exam/retrieval-bm25-ai-review-queue-v1.json \
  --calibration-output data/private/ayt-history-exam/retrieval-bm25-ai-review-calibration-v1.json
```

Partiler tamamlanınca yalnız aynı candidate/corpus/split checksum'ına bağlı 24
kayıt birleştirilir. Sonuçtaki `ai_top_1_support_rate` ve
`ai_top_3_any_support_rate`, BM25'in **kendi aday kümesinin** AI tarafından
desteklenip desteklenmediğini anlatır; bağımsız relevance gold, insan/PDF
onayı, dense/RRF karşılaştırması veya çalışma zamanı retriever seçimi değildir.
İnsan kırpım etiketi olmadan bu sınır değişmez.

## Kilitli retrieval için sıralama-kör PDF incelemesi

Araştırma ölçümünde gerçek relevance etiketi üretmek için BM25'in top-3 kartı
yerel PDF kesitleri ile hazırlanır. İncelemeci doğru cevabı, açıklamayı,
adayın üretimde bağlandığı referans atomu ve BM25 sırasını görmez. Her kart
`relevant`, `wrong` veya `insufficient`; her soru da `sufficient`,
`insufficient` ya da `review_required` olarak karara bağlanır.

```bash
apps/api/.venv/bin/python -m app.pipeline.prepare_ayt_history_retrieval_pdf_review \
  --candidate-pack data/private/ayt-history-exam/original-question-candidate-pack-v2.json \
  --split data/private/ayt-history-exam/candidate-split-v1.json \
  --corpus data/private/ayt-history-exam/multi-history-rag-v3.json \
  --baseline data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json \
  --source-catalog data/private/ayt-history-exam/sources-v1.json \
  --source-root data/meb \
  --output data/private/ayt-history-exam/retrieval-human-pdf-review-v1
```

`index.html` yerel, etkileşimli inceleme formudur. İncelemeci adını girer,
her kartı ve soruyu işaretler, gerekçesini yazar; **Completed JSON indir**
düğmesiyle `completed-manifest.json` dosyasını alır. Form yalnız tarayıcıda
çalışır; kaynak veya öğrenci verisini sunucuya göndermez. Yarım kalan çalışma
aynı dosya ile tekrar yüklenebilir. Tamamlanan dosya, kaynak konumunun/metnin
değiştirilmediğini ve her kararın mantıksal olarak tutarlı olduğunu kontrol
eden aşağıdaki doğrulayıcıdan geçmelidir:

```bash
apps/api/.venv/bin/python -m app.pipeline.validate_ayt_history_retrieval_pdf_review \
  --template data/private/ayt-history-exam/retrieval-human-pdf-review-v1/manifest.json \
  --completed data/private/ayt-history-exam/retrieval-human-pdf-review-v1/completed-manifest.json \
  --output data/private/ayt-history-exam/retrieval-human-pdf-review-v1/validation.json
```

Doğrulayıcı yapısal bütünlüğü denetler; incelemecinin uzmanlığını kanıtlamaz,
insan öğretmen onayı oluşturmaz ve runtime yolunu açmaz. Yalnız tamamlanmış
bağımsız etiketlerden sonra BM25/dense/RRF aynı soru havuzunda karşılaştırılır.

Tamamlanmış ve doğrulanmış inceleme, önce yalnız incelenen BM25 aday havuzu
için kaynak etiketlerine projekte edilir:

```bash
apps/api/.venv/bin/python -m app.pipeline.project_ayt_history_pdf_review_labels \
  --template data/private/ayt-history-exam/retrieval-human-pdf-review-v1/manifest.json \
  --completed data/private/ayt-history-exam/retrieval-human-pdf-review-v1/completed-manifest.json \
  --baseline data/private/ayt-history-exam/retrieval-bm25-provisional-baseline-v1.json \
  --output data/private/ayt-history-exam/retrieval-human-pdf-review-v1/pool-labels.json
```

Bu çıktının `metrics_ready: false` olması kasıtlıdır: dense/RRF'nin havuz
dışından getirdiği kartlar hâlâ etiketsizdir. Adil karşılaştırma için tüm
yöntemlerin aday birleşimi aynı kör PDF sürecine eklenmelidir; bu yapılmadan
yüksek Recall/MRR sonucu ürün yolu seçmez.

### Kaynak-sınırlı ajan alternatifi

İnsan incelemesi bulunmadığında, yerel kör şablon üç PDF kesitiyle birlikte
ayrı bir tarih-kanıt ajanına verilebilir. Bu, insan öğretmen onayı değil,
izlenebilir araştırma etiketi üretir. İstek; soru, beş şık ve üç küçük kesitle
sınırlıdır; doğru cevap, çözüm, referans atomu ve öğrenci verisi gönderilmez.
Tekrar üretilebilirlik için sekizerlik partiler çalıştırılır ve birleştirilir:

```bash
apps/api/.venv/bin/python -m app.pipeline.deepseek_rank_blind_pdf_retrieval_review \
  --template data/private/ayt-history-exam/retrieval-human-pdf-review-v1/manifest.json \
  --crop-root data/private/ayt-history-exam/retrieval-human-pdf-review-v1 \
  --output data/private/ayt-history-exam/retrieval-agent-pdf-review-v1-000.json \
  --offset 0 --limit 8 --allow-external-private-evaluation
```

Partiler ancak aynı şablon, candidate ve corpus checksum'larına bağlıysa
birleştirilir. Birleşik dosya normal PDF inceleme doğrulayıcısından da geçer;
`reviewer_kind=deepseek_history_teacher_agent_v1` ve
`is_human_teacher_approval=false` alanları korunur. Ajanın `relevant` etiketi
yalnız pool-limited ölçüm sinyalidir; runtime/QLoRA yolunu açmaz.
