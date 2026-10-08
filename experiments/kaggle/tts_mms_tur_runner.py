"""Kaggle T4: private Turkish MMS-TTS comparison candidate.

The runner accepts only the sealed private ``tts-gold-v1`` package and writes
WAVs plus content-free integrity records.  It is an inference comparison, not
fine-tuning and never approves student publication.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-gold-v1")
OUTPUT = Path("/kaggle/working/eristem-private-tts-mms-tur-v1")
GOLD_FILENAME = "tts-gold-v1.json"
MODEL_ID = "facebook/mms-tts-tur"
CANDIDATE = "facebook-mms-tts-tur-transformers"
MODEL_LICENSE = "cc-by-nc-4.0"
MAX_ITEMS = 200
MAX_UTTERANCE_CHARS = 8_000
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
VALID_KINDS = {"text", "formula", "table", "chart", "exercise"}


class TtsInputError(ValueError):
    """The sealed TTS Gold input does not meet the bounded runner contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(source: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in source.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root):
            raise TtsInputError("zip_member_outside_private_input")
    source.extractall(destination)


def resolve_gold() -> Path:
    candidates = list(INPUT.rglob(GOLD_FILENAME))
    if not candidates:
        archives = list(INPUT.rglob("*.zip"))
        if len(archives) != 1:
            raise TtsInputError("expected_one_tts_gold_manifest")
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(archives[0]) as source:
            safe_extract(source, unpacked)
        candidates = list(unpacked.rglob(GOLD_FILENAME))
    if len(candidates) != 1:
        raise TtsInputError("expected_one_tts_gold_manifest")
    return candidates[0]


def load_gold(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["items"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise TtsInputError("invalid_tts_gold") from error
    if payload.get("schema_version") != "tts-gold-v1" or not isinstance(items, list):
        raise TtsInputError("invalid_tts_gold_schema")
    if not 1 <= len(items) <= MAX_ITEMS:
        raise TtsInputError("invalid_tts_gold_item_count")
    seen: set[str] = set()
    checked = []
    for item in items:
        if not isinstance(item, dict):
            raise TtsInputError("invalid_tts_gold_item")
        item_id, text, kind = item.get("id"), item.get("expected_spoken_text"), item.get("kind")
        if (
            not isinstance(item_id, str)
            or not ITEM_ID_PATTERN.fullmatch(item_id)
            or item_id in seen
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_UTTERANCE_CHARS
            or kind not in VALID_KINDS
        ):
            raise TtsInputError("invalid_tts_gold_item")
        seen.add(item_id)
        checked.append({"id": item_id, "text": text, "kind": kind})
    return checked


def item_seed(item_id: str) -> int:
    """Make VITS's stochastic duration prediction reproducible per utterance."""
    return int.from_bytes(hashlib.sha256(item_id.encode("utf-8")).digest()[:8], "big") % (2**31)


def install_mms_runtime() -> None:
    """Install a VITS-capable Transformers runtime in ephemeral Kaggle."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "transformers>=4.33,<5", "accelerate"],
        check=True,
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    install_mms_runtime()
    import torch
    import torchaudio as ta
    from transformers import AutoTokenizer, VitsModel

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_for_mms_tur_benchmark")
    gold_path = resolve_gold()
    items = load_gold(gold_path)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = VitsModel.from_pretrained(MODEL_ID).to("cuda").eval()
    audio_dir = OUTPUT / "private-audio"
    audio_dir.mkdir(exist_ok=True)
    records = []
    for position, item in enumerate(items, start=1):
        item_id = str(item["id"])
        print(f"[{position}/{len(items)}] Synthesising: {item_id}")
        started = time.monotonic()
        try:
            seed = item_seed(item_id)
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            inputs = tokenizer(str(item["text"]), return_tensors="pt").to("cuda")
            with torch.inference_mode():
                waveform = model(**inputs).waveform[0].detach().cpu()
            destination = audio_dir / f"{item_id}.wav"
            ta.save(str(destination), waveform.unsqueeze(0), model.config.sampling_rate)
            records.append(
                {
                    "id": item_id,
                    "kind": item["kind"],
                    "status": "generated",
                    "duration_seconds": int(waveform.numel()) / model.config.sampling_rate,
                    "generation_seconds": time.monotonic() - started,
                    "audio_sha256": sha256(destination),
                }
            )
        except (OSError, RuntimeError, ValueError) as error:
            records.append({"id": item_id, "kind": item["kind"], "status": "failed", "error_type": type(error).__name__})
    generated = sum(record["status"] == "generated" for record in records)
    summary = {
        "schema_version": "tts-synthesis-run-v1",
        "candidate": CANDIDATE,
        "language": "tr",
        "input_private": True,
        "student_publication": "blocked_pending_local_quality_evaluation",
        "items_total": len(records),
        "items_generated": generated,
        "items_failed": len(records) - generated,
        "records": records,
    }
    (OUTPUT / "run_records.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps(
            {
                "candidate": CANDIDATE,
                "model_id": MODEL_ID,
                "model_license": MODEL_LICENSE,
                "language": "tr",
                "device": torch.cuda.get_device_name(0),
                "torch_version": torch.__version__,
                "transformers_version": importlib.metadata.version("transformers"),
                "input_private": True,
                "student_publication": "blocked_pending_local_quality_evaluation",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Finished: {generated}/{len(records)} private audio samples generated; publication blocked.")


if __name__ == "__main__":
    main()
