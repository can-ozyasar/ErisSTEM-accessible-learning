"""Build a private, blind, offline listening study for the paired V3 run."""

from __future__ import annotations

import hashlib
import html
import json
import random
import shutil
import wave
from pathlib import Path

import kaggle_ops

PRIVATE = kaggle_ops.private_root()
GOLD = PRIVATE / "eristem_history_tts_eval_v1/tts-history-eval-v1.json"
RUN = PRIVATE / "kaggle-notebook-outputs/muhammedcanozyasar/eristem-tts-v3-finetune-eval-v1/20261024T102817Z/eristem-tts-v3-finetune-eval-v1"
AUDIO = RUN.parent / "audio/eristem-tts-v3-finetune-eval-v1"
OUTPUT = PRIVATE / "tts_v3_finetune_ab_v1"
MAPPING = PRIVATE / "tts_v3_finetune_ab_v1_mapping.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def card(number: int, item: dict) -> str:
    item_id = html.escape(item["id"], quote=True)
    spoken = html.escape(item["expected_spoken_text"])
    return f'''<fieldset class="sample" data-id="{item_id}"><legend>Örnek {number} / 14</legend>
<p class="spoken"><strong>Okunması beklenen metin:</strong> {spoken}</p>
<div class="voices"><div><label for="audio-{number}-a">Ses A</label><audio id="audio-{number}-a" controls preload="none" src="{number:02d}-A.wav">Tarayıcınız ses oynatmayı desteklemiyor.</audio></div>
<div><label for="audio-{number}-b">Ses B</label><audio id="audio-{number}-b" controls preload="none" src="{number:02d}-B.wav">Tarayıcınız ses oynatmayı desteklemiyor.</audio></div></div>
<label>Daha doğal ve rahat anlaşılır olan
<select class="preferred" required><option value="">Seçin</option><option value="A">A</option><option value="B">B</option><option value="equal">Eşit</option><option value="neither">İkisi de anlaşılmıyor</option></select></label>
<label>Ses A metni doğru okudu mu?
<select class="accurate-a" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Ses B metni doğru okudu mu?
<select class="accurate-b" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Belirgin hata veya izlenim (isteğe bağlı)<textarea class="note" rows="2" maxlength="500"></textarea></label></fieldset>'''


def main() -> None:
    gold = load_json(GOLD)
    report = load_json(RUN / "run_records.json")
    meta = load_json(RUN / "run_metadata.json")
    gold_hash = kaggle_ops.sha256(GOLD)
    items = gold.get("items")
    if gold.get("schema_version") != "tts-history-eval-v1" or not isinstance(items, list) or len(items) != 14:
        raise ValueError("Beklenen 14 kapalı tarih metni bulunamadı")
    if report.get("input_sha256") != gold_hash or meta.get("input_sha256") != gold_hash:
        raise ValueError("Sentez raporu kapalı metinlerle eşleşmiyor")
    if meta.get("samples_generated") != 28 or meta.get("samples_failed") != 0 or report.get("items_total") != 28:
        raise ValueError("Eksik ses üretimi var")
    if meta.get("trained_sha256") != "90e0a513e4d5f128233a6442f4d3e4c0ac47fefe2ac64eb88c39b28b2aa48060":
        raise ValueError("Eğitilmiş model kimliği değişmiş")
    ids = [item["id"] for item in items]
    if len(set(ids)) != 14:
        raise ValueError("Tekrarlanan metin kimliği")
    records = {(row["id"], row["candidate"]): row for row in report["records"]}
    if len(records) != 28 or set(records) != {(item_id, variant) for item_id in ids for variant in ("base", "tuned")}:
        raise ValueError("A/B çiftleri tam eşleşmiyor")
    if OUTPUT.exists() or MAPPING.exists():
        raise FileExistsError("Dinleme paketi mevcut; kör yanıtların korunması için üzerine yazılmadı")

    # Verify every source before writing the packet. No model identity enters HTML.
    sources = {}
    for key, row in records.items():
        path = AUDIO / row["audio_path"]
        if not path.resolve().is_relative_to(AUDIO.resolve()):
            raise ValueError("Geçersiz ses dosyası yolu")
        if row.get("status") != "generated" or not path.is_file() or kaggle_ops.sha256(path) != row["audio_sha256"]:
            raise ValueError(f"Ses dosyası eksik veya farklı: {key}")
        with wave.open(str(path), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getframerate() != 24_000 or wav.getsampwidth() != 2:
                raise ValueError(f"Beklenmeyen WAV biçimi: {key}")
        sources[key] = path

    rng = random.Random(int(gold_hash[:16], 16))
    balanced = ids.copy()
    rng.shuffle(balanced)
    base_a = set(balanced[:7])
    OUTPUT.mkdir(parents=True)
    assignments = {}
    for number, item in enumerate(items, 1):
        item_id = item["id"]
        variants = ("base", "tuned") if item_id in base_a else ("tuned", "base")
        assignments[item_id] = {"A": variants[0], "B": variants[1]}
        for label, variant in zip("AB", variants):
            shutil.copy2(sources[item_id, variant], OUTPUT / f"{number:02d}-{label}.wav")

    page = '''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kör A/B ses karşılaştırması</title><style>
:root{color-scheme:light}body{font:1.12rem/1.65 system-ui,sans-serif;color:#132a42;background:#eaf5fb;max-width:58rem;margin:0 auto;padding:1.25rem}h1{line-height:1.25}.intro,.sample{background:#fff;border:2px solid #83adc5;border-radius:1rem;padding:1.25rem;margin:1.1rem 0}.sample legend{font-weight:700;font-size:1.3rem}.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;margin:1rem 0}.voices audio{display:block;width:100%;margin-top:.4rem}.sample label{display:block;font-weight:600;margin:1rem 0}.sample select,.sample textarea{display:block;width:100%;max-width:30rem;box-sizing:border-box;font:inherit;padding:.55rem;background:#fff;color:#132a42;border:2px solid #426d88;border-radius:.45rem}.sample textarea{max-width:100%}button{font:inherit;font-weight:700;color:#fff;background:#075883;border:0;border-radius:.6rem;padding:.85rem 1.25rem;cursor:pointer}button:hover{background:#003d62}:focus-visible{outline:4px solid #c85500;outline-offset:3px}.spoken{font-size:1.1rem}#status{font-weight:700}a{color:#004c84}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body><main><h1>Kör A/B ses karşılaştırması</h1><div class="intro"><p>A ve B'nin model kimliği gizlidir. Her örnekte iki sesi kulaklıkla dinleyin. Önce hangi sesin daha doğal ve anlaşılır olduğunu, sonra her birinin metni doğru okuyup okumadığını işaretleyin.</p><p>Ses oynatıcıları klavyeyle kullanılabilir. Yanıtlar tarayıcıdan hiçbir yere gönderilmez; en alttaki düğme yalnızca bilgisayarınıza JSON dosyası indirir. Tüm 14 örnek yaklaşık 12 dakika sürebilir.</p><p id="status" role="status" aria-live="polite">0 / 14 örnek tamamlandı.</p></div>
<form id="review">''' + "\n".join(card(n, item) for n, item in enumerate(items, 1)) + '''<button type="submit">Yanıtları JSON olarak indir</button></form></main>
<script>
const form=document.getElementById('review');const cards=[...document.querySelectorAll('.sample')];const status=document.getElementById('status');
function progress(){const complete=cards.filter(card=>[...card.querySelectorAll('select')].every(select=>select.value)).length;status.textContent=complete+' / 14 örnek tamamlandı.'}
form.addEventListener('change',progress);
document.querySelectorAll('audio').forEach(player=>player.addEventListener('play',()=>document.querySelectorAll('audio').forEach(other=>{if(other!==player)other.pause()})));
form.addEventListener('submit',event=>{event.preventDefault();if(!form.reportValidity())return;
const entries=cards.map(card=>({id:card.dataset.id,preferred:card.querySelector('.preferred').value,accurate_a:card.querySelector('.accurate-a').value,accurate_b:card.querySelector('.accurate-b').value,note:card.querySelector('.note').value.trim()}));
const result={schema_version:'tts-v3-finetune-blind-ab-v1',entries};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='tts-v3-kor-ab-yanit.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
</script></body></html>'''
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    MAPPING.write_text(json.dumps({"schema_version": "tts-v3-finetune-blind-ab-map-v1", "gold_sha256": gold_hash,
        "synthesis_sha256": kaggle_ops.sha256(RUN / "run_records.json"), "assignments": assignments}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"page": str(OUTPUT / "index.html"), "items": len(items), "audio_files": 28,
        "mapping": str(MAPPING)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
