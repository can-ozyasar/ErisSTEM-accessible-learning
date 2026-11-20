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
  --pdf data/private/meb/tarih-12.pdf \
  --source-id meb-tarih-12-2026 \
  --title "MEB Tarih 12. Sınıf Ders Kitabı" \
  --canonical-url "https://ogmmateryal.eba.gov.tr/..." \
  --output data/private/ayt-history-exam/sources-v1.json
```

Çıktıdaki `sources` alanı, paket manifestindeki kaynak kataloğuna aynen
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
kitabı kanıtı taşır. `ai_source_text_review`, AI destekli kaynak metni
incelemesidir; insan PDF kırpımı incelemesi olarak sunulamaz.
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
    "review_method": "ai_source_text_review",
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
