"""Create an offline, blind Piper-vs-Chatterbox history listening packet."""

from __future__ import annotations

import html
import json
import random
import shutil
from pathlib import Path

import kaggle_ops

ROOT = kaggle_ops.repo_root()
PRIVATE = kaggle_ops.private_root()
INPUT = PRIVATE / "eristem_history_tts_eval_v1/tts-history-eval-v1.json"
PIPER = PRIVATE / "tts_history_piper_v1"
OUTPUT = PRIVATE / "tts_history_listening_v2"
KERNEL = "eristem-history-tts-chatterbox-v3-v2"
# Pair the listening study with the exact V3 WAVs used by the ASR v2 run.
CHATTERBOX_OUTPUT_RUN = "20261020T091906Z"


def load_report(path: Path, input_hash: str) -> dict:
    report = json.loads(kaggle_ops.private_path(path).read_text(encoding="utf-8"))
    if report.get("schema_version") != "tts-synthesis-run-v1" or report.get("input_sha256") != input_hash:
        raise ValueError("Ses raporu tarih değerlendirme girdisiyle eşleşmiyor")
    if report.get("items_failed") != 0 or report.get("items_generated") != report.get("items_total"):
        raise ValueError("Eksik veya başarısız ses kaydı var")
    return report


def chatterbox_audio(input_hash: str, output_run: str | None = None) -> tuple[Path, dict]:
    root = PRIVATE / "kaggle-notebook-outputs/muhammedcanozyasar" / KERNEL
    matches = []
    for manifest_path in root.glob("*/download_manifest.json"):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "kaggle-tts-audio-download-v1":
            continue
        report_path = PRIVATE / payload["run_records_relative_path"]
        try:
            report = load_report(report_path, input_hash)
        except (OSError, ValueError):
            continue
        matches.append((manifest_path.parent, payload, report))
    if output_run is not None:
        matches = [item for item in matches if item[0].name == output_run]
    # Re-running ``fetch`` can create more than one local download directory
    # for the same remote WAV set.  Accept those exact duplicates, but never
    # silently choose between different synthesis outputs.
    signatures = {
        tuple(sorted((item["id"], item["sha256"]) for item in payload["files"]))
        for _, payload, _ in matches
    }
    if len(signatures) != 1:
        raise ValueError("Bu tarih girdisi için birden çok farklı Chatterbox WAV paketi bulundu; koşum kimliği seçin")
    directory, payload, report = max(matches, key=lambda item: item[0].name)
    return directory, {"manifest": payload, "report": report}


def main() -> None:
    input_hash = kaggle_ops.sha256(INPUT)
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    piper = load_report(PIPER / "run_records.json", input_hash)
    chatterbox_dir, chatterbox = chatterbox_audio(input_hash, CHATTERBOX_OUTPUT_RUN)
    if OUTPUT.exists():
        raise FileExistsError("Dinleme paketi zaten var; önceki yanıtlar korunuyor")
    expected_ids = [item["id"] for item in source["items"]]
    piper_records = {item["id"]: item for item in piper["records"]}
    cb_records = {item["id"]: item for item in chatterbox["report"]["records"]}
    cb_files = {item["id"]: item for item in chatterbox["manifest"]["files"]}
    if set(expected_ids) != set(piper_records) or set(expected_ids) != set(cb_records) or set(expected_ids) != set(cb_files):
        raise ValueError("İki adayın örnek kimlikleri eşleşmiyor")
    assignments = {}
    rng = random.Random(int(input_hash[:16], 16))
    order = expected_ids.copy()
    rng.shuffle(order)
    piper_a = set(order[: len(order) // 2])
    for item_id in expected_ids:
        assignments[item_id] = "A" if item_id in piper_a else "B"
        for name, record, path in (
            ("piper", piper_records[item_id], PIPER / f"{item_id}.wav"),
            ("chatterbox", cb_records[item_id], chatterbox_dir / cb_files[item_id]["path"]),
        ):
            if kaggle_ops.sha256(path) != record["audio_sha256"]:
                raise ValueError(f"{name} WAV checksum uyuşmuyor: {item_id}")
    OUTPUT.mkdir(parents=True)
    cards = []
    mapping = {}
    for item in source["items"]:
        item_id = item["id"]
        a_name = "piper" if assignments[item_id] == "A" else "chatterbox"
        b_name = "chatterbox" if a_name == "piper" else "piper"
        mapping[item_id] = {"A": a_name, "B": b_name}
        paths = {"piper": PIPER / f"{item_id}.wav",
                 "chatterbox": chatterbox_dir / cb_files[item_id]["path"]}
        for label, candidate in (("A", a_name), ("B", b_name)):
            target = OUTPUT / f"{item_id}-{label}.wav"
            shutil.copy2(paths[candidate], target)
        escaped_id = html.escape(item_id, quote=True)
        escaped_text = html.escape(item["expected_spoken_text"])
        cards.append(f'''<fieldset class="sample" data-id="{escaped_id}"><legend>{escaped_id}</legend>
<p class="source">Beklenen okuma: {escaped_text}</p>
<div class="voices"><label>Ses A <audio controls preload="none" src="{escaped_id}-A.wav"></audio></label>
<label>Ses B <audio controls preload="none" src="{escaped_id}-B.wav"></audio></label></div>
<label>Daha doğal gelen <select class="preferred" required><option value="">Seçin</option><option>A</option><option>B</option><option value="equal">Eşit</option></select></label>
<label>Ses A metni doğru okudu mu? <select class="accurate-a" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Ses B metni doğru okudu mu? <select class="accurate-b" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Hata veya izlenim <textarea class="note" rows="2"></textarea></label></fieldset>''')
    (OUTPUT / "mapping.json").write_text(json.dumps({"input_sha256": input_hash,
        "candidates": {"piper": piper["candidate"], "chatterbox": chatterbox["report"]["candidate"]},
        "assignments": mapping}, ensure_ascii=False, indent=2), encoding="utf-8")
    page = '''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tarih sesleri kör dinleme</title><style>body{font:1rem/1.5 system-ui;max-width:58rem;margin:auto;padding:1.5rem;background:#f7f8fc;color:#15233b}h1{font-size:1.8rem}.sample{margin:1.25rem 0;padding:1.25rem;border:1px solid #b8c6da;border-radius:1rem;background:white}.sample label{display:block;margin:.65rem 0}.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.voices audio{display:block;width:100%}select,textarea,input{font:inherit;padding:.45rem;max-width:100%}textarea{display:block;width:100%;box-sizing:border-box}button{font:inherit;padding:.8rem 1.2rem;border:0;border-radius:.6rem;background:#075f9c;color:white;cursor:pointer}button:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #e08900}</style>
<h1>Tarih metinleri: kör ses karşılaştırması</h1><p>Her iki sesi kulaklıkla dinleyin. Hangisinin daha doğal olduğunu ve metindeki tarih, özel ad, soru numarası gibi bilgileri doğru okuyup okumadığını ayrı işaretleyin. Ses A/B kimliği bu sayfada gösterilmez. Sonuçlar yalnız cihazınızda kalır; indirdiğiniz JSON dosyasını proje sahibine iletin.</p>
<label>Dinleyici kodu <input id="reviewer" required autocomplete="off" maxlength="50"></label><form id="review">'''+"\n".join(cards)+'''<button type="submit">Yanıtları JSON olarak indir</button></form>
<script>document.getElementById('review').addEventListener('submit',event=>{event.preventDefault();const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('Dinleyici kodu gerekli');return}const entries=[...document.querySelectorAll('.sample')].map(card=>({id:card.dataset.id,preferred:card.querySelector('.preferred').value,accurate_a:card.querySelector('.accurate-a').value,accurate_b:card.querySelector('.accurate-b').value,note:card.querySelector('.note').value.trim().slice(0,500)}));if(entries.some(item=>!item.preferred||!item.accurate_a||!item.accurate_b)){alert('Her örneği işaretleyin');return}const data={schema_version:'tts-history-listener-v1',reviewer,entries};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='history-listener-'+reviewer.replace(/[^a-zA-Z0-9_-]/g,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});</script></html>'''
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({"samples": len(expected_ids), "private_page": str(OUTPUT / "index.html")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
