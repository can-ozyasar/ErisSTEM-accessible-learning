"""Build a private offline playback bundle for one blind TTS reviewer.

This is a diagnostic/review input, never a publication decision. Only the
already-eligible packet items are copied; source paths and candidate names are
not shown to the reviewer. The generated HTML runs without a server.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import wave
from pathlib import Path

from .tts_audio_assets import sha256_file

_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("invalid_private_review_input")
    return payload


def build_review_bundle(packet_path: Path, asr_input_path: Path, output_dir: Path) -> dict[str, object]:
    packet, source = _read(packet_path), _read(asr_input_path)
    if packet.get("schema_version") != "tts-listener-packet-v1" or source.get("schema_version") != "tts-asr-input-v1":
        raise ValueError("invalid_private_review_schema")
    if not all(isinstance(packet.get(key), str) and _ID.fullmatch(packet[key]) for key in ("study_id", "reviewer_id")):
        raise ValueError("invalid_private_review_ids")
    items, assets = packet.get("items"), source.get("assets")
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or not isinstance(assets, list):
        raise ValueError("invalid_private_review_items")
    by_id = {asset.get("id"): asset for asset in assets if isinstance(asset, dict)}
    if len(by_id) != len(assets):
        raise ValueError("duplicate_audio_asset_ids")
    source_root = asr_input_path.parent.resolve()
    validated: list[tuple[dict, Path]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("invalid_private_review_item")
        item_id, digest, reference = item.get("id"), item.get("audio_sha256"), item.get("reference_spoken_text")
        if not isinstance(item_id, str) or not _ID.fullmatch(item_id) or item_id in seen:
            raise ValueError("invalid_or_duplicate_review_item_id")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest) or not isinstance(reference, str) or not reference.strip():
            raise ValueError("invalid_private_review_reference")
        seen.add(item_id)
        asset = by_id.get(item_id)
        if not isinstance(asset, dict) or asset.get("audio_sha256") != digest or asset.get("kind") != item.get("kind"):
            raise ValueError("review_audio_binding_mismatch")
        relative = asset.get("audio_path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("unsafe_review_audio_path")
        audio = (source_root / relative).resolve()
        if not audio.is_relative_to(source_root) or not audio.is_file() or sha256_file(audio) != digest:
            raise ValueError("review_audio_integrity_mismatch")
        try:
            with wave.open(str(audio), "rb") as wav:
                if wav.getnchannels() not in (1, 2) or wav.getframerate() < 16_000 or wav.getnframes() == 0:
                    raise ValueError("invalid_review_wav")
        except (wave.Error, EOFError) as error:
            raise ValueError("invalid_review_wav") from error
        validated.append((item, audio))
    if output_dir.exists():
        raise FileExistsError("refusing_to_overwrite_private_review_bundle")
    (output_dir / "audio").mkdir(parents=True)
    fields = []
    for position, (item, audio) in enumerate(validated, start=1):
        item_id = item["id"]
        shutil.copyfile(audio, output_dir / "audio" / f"{item_id}.wav")
        escaped = html.escape(item["reference_spoken_text"])
        fields.append(
            f'<fieldset data-id="{item_id}" data-sha="{item["audio_sha256"]}">'
            f'<legend>Örnek {position}</legend><p>{escaped}</p>'
            f'<audio controls preload="none" src="audio/{item_id}.wav"></audio>'
            + "".join(
                f'<p>{label}: <label><input required type="radio" name="{item_id}-{name}" value="yes"> Evet</label> '
                f'<label><input type="radio" name="{item_id}-{name}" value="no"> Hayır</label></p>'
                for name, label in (("match", "Söylenen metin referansla aynı mı"), ("clear", "Anlaşılır mı"), ("artifact", "Ciddi ses bozulması var mı"))
            )
            + "</fieldset>"
        )
    page = (
        '<!doctype html><html lang="tr" data-reviewer="'
        + packet["reviewer_id"] + '" data-study="' + packet["study_id"] + '"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Özel ses dinleme değerlendirmesi</title>'
        '<style>body{font:1.1rem/1.5 system-ui;max-width:48rem;margin:auto;padding:1rem;color:#132d44}'
        'fieldset{margin:1.5rem 0;padding:1rem;border:2px solid #174f78}audio{width:100%}'
        'input{width:1.3rem;height:1.3rem}button{min-height:48px;padding:.7rem;font:inherit}'
        ':focus-visible{outline:4px solid #e05d00}</style><main><h1>Özel ses dinleme değerlendirmesi</h1>'
        '<p>Aday kimliği gizlidir. Her kaydı dinleyip üç soruyu cevaplayın. Bu dosyayı veya sesleri paylaşmayın.</p>'
        '<form id="review">' + "".join(fields) + '<button type="submit">Yanıtları JSON olarak indir</button></form>'
        '<p id="status" role="status"></p></main><script>'
        'document.getElementById("review").addEventListener("submit",event=>{event.preventDefault();'
        'const form=event.currentTarget;const responses=[...form.querySelectorAll("fieldset")].map(group=>{'
        'const answer=name=>group.querySelector(`input[name="${group.dataset.id}-${name}"]:checked`).value;'
        'return {id:group.dataset.id,audio_sha256:group.dataset.sha,matches_reference:answer("match")==="yes",'
        'intelligible:answer("clear")==="yes",serious_artifact:answer("artifact")==="yes"}});'
        'const payload={study_id:document.documentElement.dataset.study,reviewer_id:document.documentElement.dataset.reviewer,responses};'
        'const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));'
        'const link=document.createElement("a");link.href=url;link.download="listener-response.json";link.click();'
        'setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById("status").textContent="Yanıt dosyası indirildi."});'
        '</script></html>'
    )
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    return {"schema_version": "tts-private-listener-review-bundle-v1", "review_items": len(validated), "candidate_identity_exposed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a checksum-verified private offline TTS listener bundle")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--asr-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_review_bundle(args.packet, args.asr_input, args.output_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
