"""Build an offline, accessible review page for exact AYT V5 candidate WAVs."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path

from .promote_ayt_v5_reviewed_audio import MODEL_SHA256


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(input_manifest: Path, candidate_root: Path, output: Path) -> int:
    if output.exists():
        raise FileExistsError("listener_review_page_already_exists")
    candidate_root = candidate_root.resolve()
    output = output.resolve()
    if not output.parent.is_relative_to(candidate_root):
        raise ValueError("review_page_must_be_inside_private_candidate_root")
    manifest = json.loads(input_manifest.read_text(encoding="utf-8"))
    index = json.loads((candidate_root / "index.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(index, dict):
        raise TypeError("invalid_audio_review_binding_json")
    input_hash = _sha256(input_manifest)
    source_hashes = index.get("source_sha256")
    if (manifest.get("schema_version") != "ayt-history-v5-static-audio-input-v1"
            or manifest.get("voice_model_sha256") != MODEL_SHA256
            or index.get("schema_version") != "v5-demo-installed-v1"
            or index.get("model_sha256") != MODEL_SHA256
            or not isinstance(source_hashes, dict)
            or source_hashes.get("question") != manifest.get("pack_checksum")
            or index.get("input_manifest_sha256") != input_hash
            or index.get("runtime_enabled") is not False
            or index.get("requires_listening_review") is not True):
        raise ValueError("candidate_review_binding_mismatch")
    source_items = manifest.get("items")
    candidate_items = index.get("items")
    if not isinstance(source_items, list) or not isinstance(candidate_items, list):
        raise TypeError("invalid_audio_item_lists")
    candidate_by_identity = {}
    for item in candidate_items:
        if not isinstance(item, dict):
            raise TypeError("invalid_candidate_audio_item")
        identity = (item.get("kind"), item.get("id"), item.get("spoken_text_sha256"))
        if identity in candidate_by_identity:
            raise ValueError("duplicate_candidate_audio_identity")
        candidate_by_identity[identity] = item

    rows_by_hash = {}
    for item in source_items:
        if (not isinstance(item, dict) or not isinstance(item.get("spoken_text"), str)
                or item.get("contains_digits") is not False):
            raise ValueError("input_contains_invalid_or_withheld_item")
        text, text_hash = item["spoken_text"], item.get("spoken_text_sha256")
        if (hashlib.sha256(text.encode("utf-8")).hexdigest() != text_hash
                or re.search(r"\d", text)):
            raise ValueError("input_text_hash_or_scope_invalid")
        installed_id = text_hash if item.get("kind") == "interface" else item.get("id")
        identity = (item.get("kind"), installed_id, text_hash)
        candidate_item = candidate_by_identity.get(identity)
        if candidate_item is None:
            raise ValueError("candidate_missing_exact_source_unit")
        filename = candidate_item.get("filename")
        relative = Path(filename) if isinstance(filename, str) else Path("invalid")
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("candidate_audio_path_invalid")
        audio_path = (candidate_root / relative).resolve()
        if not audio_path.is_relative_to(candidate_root.resolve()) or not audio_path.is_file():
            raise ValueError("candidate_audio_missing")
        if audio_path.stat().st_size != candidate_item.get("bytes") or _sha256(audio_path) != candidate_item.get("audio_sha256"):
            raise ValueError("candidate_audio_checksum_mismatch")
        with audio_path.open("rb") as stream:
            header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise ValueError("candidate_audio_invalid_wav")
        row = rows_by_hash.setdefault(text_hash, {
            "spoken_text_sha256": text_hash,
            "kind": item["kind"],
            "static_role": item.get("static_role", ""),
            "text": text,
            "audio_path": audio_path,
            "unit_ids": [],
        })
        if row["text"] != text:
            raise ValueError("text_hash_collision")
        row["unit_ids"].append(item.get("id", ""))
    if not rows_by_hash:
        raise ValueError("no_reviewable_audio")

    output.parent.mkdir(parents=True, exist_ok=True)
    review_rows = []
    for row in sorted(rows_by_hash.values(), key=lambda value: (value["kind"], value["unit_ids"][0])):
        relative_audio = Path(os.path.relpath(row["audio_path"], output.parent)).as_posix()
        review_rows.append({
            "spoken_text_sha256": row["spoken_text_sha256"],
            "kind": row["kind"],
            "static_role": row["static_role"],
            "text": row["text"],
            "audio": relative_audio,
            "unit_ids": row["unit_ids"],
        })
    data = json.dumps(review_rows, ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ErişSTEM — AYT V5 ses incelemesi</title>
<style>
body{font:1rem/1.5 system-ui,sans-serif;max-width:64rem;margin:2rem auto;padding:0 1rem;color:#152238}
h1,h2{line-height:1.2} .notice{border-left:.3rem solid #155eef;padding:.75rem 1rem;background:#f3f7ff}
fieldset{margin:1.5rem 0;padding:1rem;border:1px solid #9aa9bd;border-radius:.5rem}
label{display:block;margin:.6rem 0}audio{width:min(100%,36rem)}button{padding:.7rem 1rem;font:inherit}
select,input{font:inherit;padding:.35rem} .row{padding-top:.5rem;border-top:1px solid #dde3ec}
</style></head><body>
<h1>AYT Tarih — fine-tune ses dinleme incelemesi</h1>
<p class="notice">Bu çevrimdışı sayfa yalnız V5 aday WAV'larını çalar. Aşağıdaki her metin birebir doğrulanmıştır; rakam içeren 17 ses birimi bu pakette yoktur ve uygulamada Piper ile okunur. İncelemediğiniz birimi boş bırakın. Onay yalnız seçtiğiniz WAV birimlerine uygulanır; bu, sesin genel olarak Piper'dan üstün olduğunu kanıtlamaz.</p>
<label>İnceleyici kodu (adınızı yazmayın): <input id="reviewer" autocomplete="off" maxlength="40" pattern="[A-Za-z0-9_-]{1,40}" required></label>
<p id="progress" aria-live="polite"></p><main id="items"></main>
<button id="export" type="button">İncelenen kararları JSON olarak indir</button>
<script type="application/json" id="review-data">__DATA__</script>
<script>
const rows=JSON.parse(document.getElementById('review-data').textContent); const main=document.getElementById('items');
function select(label,values){const l=document.createElement('label');l.textContent=label+': ';const s=document.createElement('select');s.setAttribute('aria-label',label);for(const [v,t] of values){const o=document.createElement('option');o.value=v;o.textContent=t;s.append(o)}l.append(s);return s}
const controls=[];rows.forEach((row,i)=>{const f=document.createElement('fieldset');const legend=document.createElement('legend');legend.textContent=`Ses birimi ${i+1} / ${rows.length} — ${row.static_role} — ${row.unit_ids.join(', ')}`;f.append(legend);const text=document.createElement('p');text.textContent=row.text;f.append(text);const a=document.createElement('audio');a.controls=true;a.preload='none';a.src=row.audio;a.setAttribute('aria-label',`Ses birimi ${i+1} V5 kaydı`);f.append(a);const c={row,intelligibility:select('Anlaşılabilirlik',[['','Seçin'],['pass','Anlaşılır'],['fail','Anlaşılmıyor']]),pronunciation:select('Telaffuz',[['','Seçin'],['pass','Doğru'],['fail','Hatalı']]),audio_artifacts:select('Ses artefaktı',[['','Seçin'],['none','Yok'],['minor','Hafif'],['major','Belirgin']]),decision:select('Karar',[['','İncelenmedi'],['accept','Onayla'],['reject','Reddet']])};f.append(c.intelligibility.parentElement,c.pronunciation.parentElement,c.audio_artifacts.parentElement,c.decision.parentElement);main.append(f);controls.push(c)});
const progress=document.getElementById('progress');function update(){const done=controls.filter(c=>c.decision.value).length;progress.textContent=`İncelenen: ${done} / ${controls.length}. Boş kalan birimler onaylanmaz ve Piper'da kalır.`}controls.forEach(c=>c.decision.addEventListener('change',update));update();
document.getElementById('export').addEventListener('click',()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!/^[A-Za-z0-9_-]{1,40}$/.test(reviewer)){alert('Adınız yerine 1–40 karakterlik bir inceleyici kodu kullanın (harf, rakam, tire, alt çizgi).');return}const items=[];for(const c of controls){if(!c.decision.value)continue;if(!c.intelligibility.value||!c.pronunciation.value||!c.audio_artifacts.value){alert('Karar verdiğiniz her birim için üç kalite alanını da seçin.');return}if(c.decision.value==='accept'&&(c.intelligibility.value!=='pass'||c.pronunciation.value!=='pass'||c.audio_artifacts.value!=='none')){alert('Onay için anlaşılabilirlik ve telaffuz geçmeli, belirgin ses artefaktı olmamalı.');return}items.push({spoken_text_sha256:c.row.spoken_text_sha256,intelligibility:c.intelligibility.value,pronunciation:c.pronunciation.value,audio_artifacts:c.audio_artifacts.value,decision:c.decision.value})}if(!items.length){alert('Önce en az bir ses birimini dinleyip değerlendirin.');return}const data={schema:'ayt-v5-human-listener-review-v1',source_pack_sha256:'__PACK_SHA__',input_manifest_sha256:'__INPUT_SHA__',voice_model_sha256:'__MODEL_SHA__',reviewer,reviewed_at_utc:new Date().toISOString(),items};const blob=new Blob([JSON.stringify(data,null,2)+'\\n'],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='ayt-v5-listener-review.json';link.click();URL.revokeObjectURL(link.href)})
</script></body></html>"""
    page = (template.replace("__DATA__", data)
            .replace("__PACK_SHA__", html.escape(manifest["pack_checksum"], quote=True))
            .replace("__INPUT_SHA__", html.escape(input_hash, quote=True))
            .replace("__MODEL_SHA__", html.escape(MODEL_SHA256, quote=True)))
    output.write_text(page, encoding="utf-8")
    return len(review_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(f"Prepared local review page for {prepare(args.input_manifest, args.candidate_root, args.output)} unique audio texts.")


if __name__ == "__main__":
    main()
