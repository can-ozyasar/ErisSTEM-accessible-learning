# AYT bilgi grafiği insan onay akışı

Graf adayları otomatik çıkarılır; öğrenciye yalnız PDF kesiti insan tarih öğretmeni tarafından doğrulanan parçalar açılır. Agent değerlendirmesi öneri olarak kalır.

## Şablon üretme

Private corpus’tan sayfa ve koordinat içeren boş şablon:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.build_ayt_graph_approval_template \
  --corpus data/private/yks-ayt-source-v1/ayt-target-discovery-corpus-local12-v1.json \
  --output data/private/yks-ayt-source-v1/ayt-graph-teacher-approval-template-v1.json
```

Öğretmen her satırda PDF kırpımını kontrol eder, `decision` alanını `approved_for_runtime` yapar, kısa birebir alıntıyı ve onun SHA-256 değerini doldurur; `pdf_crop_checked` ve `quality_checked` değerlerini `true` yapar. Görsel, yönerge veya OCR riski olan parça onaylanmaz.

Görsel inceleme paketi:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.build_ayt_graph_approval_pack \
  --corpus data/private/yks-ayt-source-v1/ayt-target-discovery-corpus-local12-v1.json \
  --source-root data/private/yks-ayt-source-v1 \
  --output data/private/yks-ayt-source-v1/ayt-graph-teacher-approval-pack-v1
```

Paketteki `index.html` ve `crops/` yalnız private inceleme içindir; paket kararları manifest’e otomatik yazmaz.

## Terfi ve graf üretimi

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.promote_ayt_graph_approvals \
  --corpus data/private/yks-ayt-source-v1/ayt-target-discovery-corpus-local12-v1.json \
  --manifest data/private/yks-ayt-source-v1/ayt-graph-teacher-approval-manifest-v1.json \
  --output data/private/yks-ayt-source-v1/ayt-target-approved-corpus-v1.json
```

Komut checksum, alıntı, insan reviewer kimliği ve risk bayraklarını doğrular. Eksik veya agent kökenli onayda durur; otomatik olarak hiçbir adayı onaylamaz. Terfi edilmiş corpus `KnowledgeGraphBuilder` ile işlendiğinde onaylı parça, bölüm ve kitap hiyerarşisi birlikte geçerli olur.

## Yerel tutor route’u

API’de `/v1/ayt-tutor/turn` route’u bulunur. `AYT_APPROVED_GRAPH_PATH` ve `AYT_TTS_CACHE_ROOT` ayarlanmadan route **503** döner; bu varsayılan davranış aday grafiğin öğrenciye açılmasını önler. Qwen servisi için `LOCAL_TUTOR_LLM_URL=http://tutor-llm:8001/generate` ayarlanır. Yanıt ses dosyasının yolu dışarı verilmez, yalnız cache kimliği döner ve `/v1/ayt-tutor/audio/{id}` üzerinden doğrulanmış hex kimliğiyle okunur.
