# Yerel Qwen3-14B koç servisi

Bu servis GPU profiliyle çalışır. API, yalnız cevap anahtarı içermeyen sınırlı
istem gönderir. PDF, soru bankası ve öğrenci verisi bu kapsayıcıya bağlanmaz.

`data/private/tutor-models/qwen3-14b-v1/manifest.json` örneği:

```json
{
  "model_id": "Qwen/Qwen3-14B",
  "revision": "40c069824f4251a91eefaf281ebe4c544efd3e18",
  "model_path": "/models/base",
  "tokenizer_path": "/models/base",
  "adapter_path": "/models/adapter",
  "quantization": "nf4-4bit-fp16",
  "training_data_summary": {"examples": 126, "source_material_included": false, "answer_keys_included": false}
}
```

Model ve adaptör yolları yerel dosya sistemine aittir. Manifestteki sürüm,
tokenizer, NF4 ayarı ve eğitim özeti birlikte saklanır. GPU yoksa API
deterministik koçluk metnine geri döner; mevcut erişilebilirlik özellikleri
çalışmaya devam eder.
