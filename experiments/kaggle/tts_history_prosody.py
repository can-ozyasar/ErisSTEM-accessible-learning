"""Private, paired punctuation/prosody test with the pinned Chatterbox V3 voice.

Usage: prepare, run, status, fetch. The remote job is launched only by run.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import sys
from pathlib import Path

import kaggle_ops

ROOT = kaggle_ops.repo_root()
PRIVATE = kaggle_ops.private_root()
SOURCE = PRIVATE / "eristem_history_tts_eval_v1/tts-history-eval-v1.json"
INPUT_DIR = PRIVATE / "eristem_history_tts_prosody_v1"
MANIFEST = INPUT_DIR / "tts-history-eval-v1.json"
PACKET = PRIVATE / "tts_history_prosody_listening_v1"
DATASET = "muhammedcanozyasar/eristem-history-tts-prosody-v1"
KERNEL = "muhammedcanozyasar/eristem-history-tts-prosody-run-v1"
TITLE = "Eristem History Tts Prosody Run V1"
VARIANTS = {
    "history-caption-01": "Kaynak C: Pişmiş topraktan yapılmış tekerlekli bir at. Milattan önce altıncı yüzyıl.",
    "history-caption-02": "Kaynak B: Aşık kemiği oyunu oynayan iki kadını gösteren Roma Dönemi heykeli.",
    "history-question-01": "Birinci soru: Kaynak A'yı yazan araştırmacı çalışmasına neden sorular sorarak başlamış olabilir?",
    "history-question-02": "İkinci soru: Kaynak B ve Kaynak C, bu konuyla ilgili araştırma yapan bir tarihçinin bütün sorularına cevap verebilir mi?",
    "history-name-01": "Pachymérès, Bizans tarih yazarlarından biridir; eserinde bin iki yüz altmış bir ile bin üç yüz sekiz yılları arasını anlatır.",
}


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def build_manifest(source: dict) -> dict:
    if source.get("schema_version") != "tts-history-eval-v1" or source.get("evaluation_only") is not True:
        raise ValueError("Tarih akustik pilot kaynağı geçersiz")
    by_id = {item["id"]: item for item in source["items"]}
    if len(by_id) != len(source["items"]) or not set(VARIANTS).issubset(by_id):
        raise ValueError("Kaynak örnekleri eksik veya yinelenmiş")
    items = []
    for source_id, alternative in VARIANTS.items():
        item = by_id[source_id]
        original = item["expected_spoken_text"]
        if words(original) != words(alternative) or original == alternative:
            raise ValueError("Deney sürümleri yalnız noktalama/büyük harf bakımından değişebilir")
        for variant, text in (("control", original), ("punctuation", alternative)):
            items.append({"id": f"{source_id}-{variant}", "kind": item["kind"],
                          "page": item["page"], "expected_spoken_text": text,
                          "critical_tokens": item["critical_tokens"]})
    return {"schema_version": "tts-history-eval-v1", "evaluation_only": True,
            "student_publication": "blocked_pending_blind_prosody_review",
            "source": source["source"], "experiment": "same-run-punctuation-only-paired-v1", "items": items}


def prepare_input() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    pdf = ROOT / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
    if kaggle_ops.sha256(pdf) != source.get("source", {}).get("pdf_sha256"):
        raise ValueError("Kaynak PDF checksum uyuşmuyor")
    manifest = build_manifest(source)
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Mevcut private deney girdisi değişmiş; üzerine yazılmadı")
    else:
        if INPUT_DIR.exists() and any(INPUT_DIR.iterdir()):
            raise ValueError("Deney girdi klasörü beklenmedik dosyalar içeriyor")
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pairs": len(VARIANTS), "audio_items": len(manifest["items"]),
            "input_sha256": kaggle_ops.sha256(MANIFEST)}


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
             "/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-prosody-v1"),
            ("/kaggle/working/eristem-private-tts-chatterbox-v3-reference-v1",
             "/kaggle/working/eristem-history-tts-prosody-v1"),
            ('"tts-gold-v1.json"', '"tts-history-eval-v1.json"'),
        ),
    )


def build_packet(audio_dir: Path, report: dict) -> Path:
    if PACKET.exists():
        raise FileExistsError("Kör dinleme paketi zaten var; yanıtlar korunuyor")
    if report.get("input_sha256") != kaggle_ops.sha256(MANIFEST) or report.get("items_failed") != 0:
        raise ValueError("Ses raporu bu deney girdisine ait değil veya eksik")
    records = {record["id"]: record for record in report["records"]}
    expected = {item["id"] for item in json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]}
    if set(records) != expected or len(records) != len(report["records"]):
        raise ValueError("Deney ses kimlikleri eksik veya yinelenmiş")
    files = {}
    for item_id, record in records.items():
        matches = list(audio_dir.rglob(f"{item_id}.wav"))
        if len(matches) != 1 or kaggle_ops.sha256(matches[0]) != record.get("audio_sha256"):
            raise ValueError("Deney WAV checksum uyuşmuyor")
        files[item_id] = matches[0]
    source = {item["id"]: item for item in json.loads(SOURCE.read_text(encoding="utf-8"))["items"]}
    order = list(VARIANTS)
    random.Random(int(kaggle_ops.sha256(MANIFEST)[:16], 16)).shuffle(order)
    variant_a = set(order[:3])
    assignments = {}
    cards = []
    PACKET.mkdir(parents=True)
    for source_id in VARIANTS:
        pair = {"A": "punctuation" if source_id in variant_a else "control"}
        pair["B"] = "control" if pair["A"] == "punctuation" else "punctuation"
        assignments[source_id] = pair
        for label, variant in pair.items():
            shutil.copy2(files[f"{source_id}-{variant}"], PACKET / f"{source_id}-{label}.wav")
        item_id = html.escape(source_id, quote=True)
        expected_text = html.escape(source[source_id]["expected_spoken_text"])
        cards.append(f'''<fieldset class="sample" data-id="{item_id}"><legend>{item_id}</legend>
<p>Beklenen sözcükler: {expected_text}</p><div class="voices">
<label>Ses A <audio controls preload="none" src="{item_id}-A.wav"></audio></label>
<label>Ses B <audio controls preload="none" src="{item_id}-B.wav"></audio></label></div>
<label>Duraklama ve doğallık açısından hangisi iyi? <select class="preferred" required><option value="">Seçin</option><option>A</option><option>B</option><option value="equal">Eşit</option></select></label>
<label>Ses A sözcükleri doğru okudu mu? <select class="accurate-a" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Ses B sözcükleri doğru okudu mu? <select class="accurate-b" required><option value="">Seçin</option><option value="yes">Evet</option><option value="no">Hayır</option><option value="unsure">Emin değilim</option></select></label>
<label>Somut duraklama/telaffuz notu (sorun yoksa "sorun yok" yazın) <textarea class="note" rows="2" required minlength="5"></textarea></label></fieldset>''')
    (PACKET / "mapping.json").write_text(json.dumps({"schema_version": "tts-history-prosody-mapping-v1",
        "input_sha256": kaggle_ops.sha256(MANIFEST), "assignments": assignments}, ensure_ascii=False, indent=2), encoding="utf-8")
    page = '''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tarih okuma: duraklama karşılaştırması</title><style>body{font:1rem/1.55 system-ui;max-width:60rem;margin:auto;padding:1rem;background:#f7f8fc;color:#15233b}.sample{margin:1rem 0;padding:1rem;border:1px solid #a9b9cd;border-radius:1rem;background:white}.sample label{display:block;margin:.7rem 0}.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.voices audio{display:block;width:100%}input,select,textarea{font:inherit;padding:.5rem;max-width:100%}textarea{display:block;width:100%;box-sizing:border-box}button{font:inherit;background:#075f9c;color:white;padding:.8rem 1.2rem;border:0;border-radius:.5rem}*:focus-visible{outline:3px solid #e08900}</style>
<h1>Tarih sesleri: noktalama ve duraklama</h1><p>A/B sesleri aynı model ve aynı sözcüklerle üretildi; yalnız noktalama farklı. Hangisinin daha doğal durakladığını işaretleyin. Özel ad ve tarih sözcüklerini ayrıca kontrol edin. Her örneğe kısa somut not yazın. Kimlik eşlemesi bu sayfada bulunmaz.</p>
<label>Dinleyici kodu <input id="reviewer" required maxlength="50" autocomplete="off"></label><form id="review">''' + "\n".join(cards) + '''<button type="submit">JSON indir</button></form>
<script>document.getElementById('review').addEventListener('submit',event=>{event.preventDefault();const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('Dinleyici kodu gerekli');return}const entries=[...document.querySelectorAll('.sample')].map(card=>({id:card.dataset.id,preferred:card.querySelector('.preferred').value,accurate_a:card.querySelector('.accurate-a').value,accurate_b:card.querySelector('.accurate-b').value,note:card.querySelector('.note').value.trim().slice(0,500)}));if(entries.some(item=>!item.preferred||!item.accurate_a||!item.accurate_b||item.note.length<5)){alert('Her örneği ve somut notunu doldurun');return}const data={schema_version:'tts-history-prosody-listener-v1',reviewer,entries};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='history-prosody-'+reviewer.replace(/[^a-zA-Z0-9_-]/g,'_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});</script></html>'''
    (PACKET / "index.html").write_text(page, encoding="utf-8")
    return PACKET / "index.html"


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "push", "status", "fetch"))
    args = parser.parse_args(argv)
    if args.command == "status":
        return {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    state = prepare_input()
    if args.command == "prepare":
        return state
    if args.command in {"run", "push"}:
        owner = kaggle_ops.verify()["authenticated_user"]
        if owner != KERNEL.split("/", 1)[0]:
            raise ValueError("Kaggle hesabı private notebook sahibinden farklı")
        if args.command == "run":
            kaggle_ops.upload_dataset(INPUT_DIR, DATASET, "Private paired punctuation-only history TTS test v1")
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
    page = build_packet(audio, report)
    return {"audio_items": state["audio_items"], "private_listening_page": str(page)}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Tarih duraklama deneyi: {error}", file=sys.stderr)
        raise SystemExit(1) from error
