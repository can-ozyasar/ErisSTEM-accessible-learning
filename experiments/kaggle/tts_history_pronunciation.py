"""Private same-run test for the observed Turkish source-label TTS failures.

Only `run` uploads a private dataset and starts Kaggle GPU work. Nothing is
published to the student app. `fetch` creates an offline, blind A/B packet.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import shutil
import sys
from pathlib import Path

import kaggle_ops

ROOT = kaggle_ops.repo_root()
sys.path.insert(0, str(ROOT / "apps/api"))
from app.history_speech import history_spoken_text  # noqa: E402

PRIVATE = kaggle_ops.private_root()
SOURCE = PRIVATE / "eristem_history_tts_eval_v1/tts-history-eval-v1.json"
INPUT_DIR = PRIVATE / "eristem_history_tts_pronunciation_v1"
MANIFEST = INPUT_DIR / "tts-history-eval-v1.json"
PACKET = PRIVATE / "tts_history_pronunciation_listening_v1"
DATASET = "muhammedcanozyasar/eristem-history-tts-pronunciation-v1"
KERNEL = "muhammedcanozyasar/eristem-history-tts-pronunciation-run-v1"
TITLE = "Eristem History Tts Pronunciation Run V1"
IDS = ("history-caption-01", "history-question-01", "history-question-02")


def build_manifest(source: dict) -> dict:
    if source.get("schema_version") != "tts-history-eval-v1" or source.get("evaluation_only") is not True:
        raise ValueError("Geçersiz tarih akustik pilot kaynağı")
    by_id = {item["id"]: item for item in source["items"]}
    if len(by_id) != len(source["items"]) or not set(IDS).issubset(by_id):
        raise ValueError("Kaynak cümleler eksik veya yinelenmiş")
    items = []
    for item_id in IDS:
        item = by_id[item_id]
        original = item["expected_spoken_text"]
        normalized = history_spoken_text(original)
        if normalized == original:
            raise ValueError("Telaffuz normalizasyonu örneği değiştirmedi")
        for variant, text in (("control", original), ("normalized", normalized)):
            critical = list(item["critical_tokens"])
            if variant == "normalized":
                critical = ["A kaynağını" if token == "Kaynak A" and "A kaynağını" in text
                            else history_spoken_text(token) for token in critical]
            if any(token not in text for token in critical):
                raise ValueError("Kritik tarih/ses sözcüğü okuma metninde yok")
            items.append({"id": f"{item_id}-{variant}", "kind": item["kind"],
                          "page": item["page"], "expected_spoken_text": text,
                          "critical_tokens": critical})
    return {"schema_version": "tts-history-eval-v1", "evaluation_only": True,
            "student_publication": "blocked_pending_blind_pronunciation_review",
            "source": source["source"], "experiment": "same-run-source-label-pronunciation-v1",
            "items": items}


def prepare() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    pdf = ROOT / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
    if kaggle_ops.sha256(pdf) != source.get("source", {}).get("pdf_sha256"):
        raise ValueError("Tarih PDF checksum uyuşmuyor")
    payload = build_manifest(source)
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text(encoding="utf-8")) != payload:
            raise ValueError("Özel deney manifesti değişmiş; üzerine yazılmadı")
    else:
        if INPUT_DIR.exists() and any(INPUT_DIR.iterdir()):
            raise ValueError("Özel deney klasörü beklenmedik dosyalar içeriyor")
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pairs": len(IDS), "audio_items": len(payload["items"]), "input_sha256": kaggle_ops.sha256(MANIFEST)}


def package() -> Path:
    destination = kaggle_ops.kernel_package_directory(KERNEL)
    if destination.exists():
        kaggle_ops.load_kernel_metadata(destination, KERNEL, DATASET)
        return destination
    return kaggle_ops.prepare_notebook_package(
        KERNEL, DATASET, ROOT / "experiments/kaggle/tts_chatterbox_v3_reference_runner.py",
        TITLE, enable_internet=True,
        source_replacements=(
            ("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-gold-v1",
             "/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-pronunciation-v1"),
            ("/kaggle/working/eristem-private-tts-chatterbox-v3-reference-v1",
             "/kaggle/working/eristem-history-tts-pronunciation-v1"),
            ('"tts-gold-v1.json"', '"tts-history-eval-v1.json"'),
        ),
    )


def build_packet(audio_dir: Path, report: dict) -> Path:
    if PACKET.exists():
        raise FileExistsError("Dinleme paketi zaten var; yanıtlar korunuyor")
    expected = {item["id"] for item in json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]}
    records = report.get("records")
    if (report.get("input_sha256") != kaggle_ops.sha256(MANIFEST)
            or report.get("items_failed") != 0 or not isinstance(records, list)
            or len(records) != len(expected) or {item.get("id") for item in records} != expected):
        raise ValueError("Eksik veya farklı deney ses raporu")
    files = {}
    for record in records:
        item_id = record["id"]
        matches = list(audio_dir.rglob(f"{item_id}.wav"))
        if len(matches) != 1 or kaggle_ops.sha256(matches[0]) != record.get("audio_sha256"):
            raise ValueError("Deney WAV checksum uyuşmuyor")
        files[item_id] = matches[0]
    source = {item["id"]: item for item in json.loads(SOURCE.read_text(encoding="utf-8"))["items"]}
    order = list(IDS)
    random.Random(int(kaggle_ops.sha256(MANIFEST)[:16], 16)).shuffle(order)
    normalized_a = set(order[:2])
    assignments = {}
    cards = []
    PACKET.mkdir(parents=True)
    for source_id in IDS:
        pair = {"A": "normalized" if source_id in normalized_a else "control"}
        pair["B"] = "control" if pair["A"] == "normalized" else "normalized"
        assignments[source_id] = pair
        for label, variant in pair.items():
            shutil.copy2(files[f"{source_id}-{variant}"], PACKET / f"{source_id}-{label}.wav")
        safe_id = html.escape(source_id, quote=True)
        text = html.escape(source[source_id]["expected_spoken_text"])
        cards.append(f'''<fieldset class="sample" data-id="{safe_id}"><legend>{safe_id}</legend>
<p>Kaynakta görünen metin: {text}</p><div class="voices">
<label>Ses A <audio controls preload="none" src="{safe_id}-A.wav"></audio></label>
<label>Ses B <audio controls preload="none" src="{safe_id}-B.wav"></audio></label></div>
<label>Kaynak harfi ve ekler bakımından daha anlaşılır olan <select class="preferred" required><option value="">Seçin</option><option>A</option><option>B</option><option value="equal">Eşit</option></select></label>
<label>Ses A, kaynak harfini ve anlamı doğru aktardı mı? <select class="accurate-a" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Ses B, kaynak harfini ve anlamı doğru aktardı mı? <select class="accurate-b" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Hangi sesi nasıl duydunuz? Harf telaffuzunu yazın; sorun yoksa belirtin. <textarea class="note" rows="2" required minlength="5"></textarea></label></fieldset>''')
    (PACKET / "mapping.json").write_text(json.dumps({"schema_version": "tts-history-pronunciation-mapping-v1",
        "input_sha256": kaggle_ops.sha256(MANIFEST), "assignments": assignments}, ensure_ascii=False, indent=2), encoding="utf-8")
    page = '''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tarih kaynak harfi telaffuzu</title><style>body{font:1rem/1.55 system-ui;max-width:58rem;margin:auto;padding:1rem;background:#f7f8fc;color:#15233b}.sample{margin:1rem 0;padding:1rem;border:1px solid #a9b9cd;border-radius:1rem;background:white}.sample label{display:block;margin:.7rem 0}.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.voices audio{display:block;width:100%}input,select,textarea{font:inherit;padding:.5rem;max-width:100%}textarea{display:block;width:100%;box-sizing:border-box}button{font:inherit;background:#075f9c;color:white;padding:.8rem 1.2rem;border:0;border-radius:.5rem}*:focus-visible{outline:3px solid #e08900}</style>
<h1>Tarih: kaynak harfi ve kesme eki</h1><p>Her çiftte aynı ses modeli ve aynı tarihsel anlam kullanıldı. Yalnız seslendirilecek kaynak etiketi farklı yazıldı; hangisinin kaynak harfini açık söylediğini ve anlamı koruduğunu değerlendirin. A/B kimliği bu sayfada gösterilmez.</p>
<label>Dinleyici kodu <input id="reviewer" required maxlength="50" autocomplete="off"></label><form id="review">''' + "\n".join(cards) + '''<button type="submit">JSON indir</button></form>
<script>document.getElementById('review').addEventListener('submit',event=>{event.preventDefault();const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('Dinleyici kodu gerekli');return}const entries=[...document.querySelectorAll('.sample')].map(card=>({id:card.dataset.id,preferred:card.querySelector('.preferred').value,accurate_a:card.querySelector('.accurate-a').value,accurate_b:card.querySelector('.accurate-b').value,note:card.querySelector('.note').value.trim().slice(0,500)}));if(entries.some(item=>!item.preferred||!item.accurate_a||!item.accurate_b||item.note.length<5)){alert('Her örneği ve notunu doldurun');return}const data={schema_version:'tts-history-pronunciation-listener-v1',reviewer,entries};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='history-pronunciation-'+reviewer.replace(/[^a-zA-Z0-9_-]/g,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});</script></html>'''
    (PACKET / "index.html").write_text(page, encoding="utf-8")
    return PACKET / "index.html"


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "push", "status", "fetch"))
    args = parser.parse_args(argv)
    if args.command == "status":
        return {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    state = prepare()
    if args.command == "prepare":
        return state
    if args.command in {"run", "push"}:
        if kaggle_ops.verify()["authenticated_user"] != KERNEL.split("/", 1)[0]:
            raise ValueError("Kaggle hesabı private notebook sahibinden farklı")
        if args.command == "run":
            kaggle_ops.upload_dataset(INPUT_DIR, DATASET, "Private source-letter pronunciation pilot v1")
        kaggle_ops.push_notebook(package(), KERNEL, DATASET, 3600, "NvidiaTeslaT4")
        return {"started": True, **state}
    if "KernelWorkerStatus.COMPLETE" not in kaggle_ops.notebook_status(KERNEL):
        raise RuntimeError("Notebook henüz tamamlanmadı")
    output, _ = kaggle_ops.download_summaries(KERNEL)
    reports = list(output.rglob("run_records.json"))
    if len(reports) != 1:
        raise ValueError("Tek bir TTS raporu bulunamadı")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    if report.get("input_sha256") != state["input_sha256"] or report.get("items_generated") != state["audio_items"] or report.get("items_failed") != 0:
        raise ValueError("TTS raporu eksik veya farklı deney girdisine ait")
    audio = kaggle_ops.download_tts_audio(KERNEL, reports[0])
    return {"private_listening_page": str(build_packet(audio, report)), **state}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Tarih telaffuz deneyi: {error}", file=sys.stderr)
        raise SystemExit(1) from error
