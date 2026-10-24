"""Private Whisper screen for paired base V3 and corrected fine-tuned V2 audio."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-finetune-eval-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-v3-finetune-asr-v2")
KERNEL_OUTPUT_DIR = "eristem-tts-v3-finetune-eval-v2"
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inputs() -> list[dict]:
    gold_paths = list(SOURCE.rglob("tts-history-eval-v1.json"))
    report_paths = [path for path in Path("/kaggle/input").rglob("run_records.json") if path.parent.name == KERNEL_OUTPUT_DIR]
    if len(gold_paths) != 1 or len(report_paths) != 1:
        raise RuntimeError("Tarih Gold veya eş ses raporu tekil değil")
    gold = json.loads(gold_paths[0].read_text(encoding="utf-8"))
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))
    ids, records = {item.get("id") for item in gold.get("items", [])}, report.get("records")
    if gold.get("schema_version") != "tts-history-eval-v1" or len(ids) != 14 or report.get("schema_version") != "tts-v3-finetune-paired-eval-v2" or report.get("input_sha256") != sha256(gold_paths[0]) or not isinstance(records, list) or len(records) != 28:
        raise RuntimeError("Eş ses raporu sabit tarih kümesiyle uyuşmuyor")
    observed, checked = set(), []
    for row in records:
        item_id, candidate = row.get("id"), row.get("candidate")
        if row.get("status") != "generated" or item_id not in ids or candidate not in {"base", "tuned_v2"}:
            raise RuntimeError("Eksik eş ses örneği")
        key = (candidate, item_id)
        if key in observed or not isinstance(item_id, str) or not ID_PATTERN.fullmatch(item_id):
            raise RuntimeError("Yinelenen veya geçersiz ses kimliği")
        observed.add(key)
        audio = (report_paths[0].parent / row.get("audio_path", "")).resolve()
        if not audio.is_relative_to(report_paths[0].parent.resolve()) or audio.name != f"{candidate}.{item_id}.wav" or not audio.is_file() or sha256(audio) != row.get("audio_sha256"):
            raise RuntimeError("Eş ses dosyasının bütünlüğü bozuk")
        checked.append({"id": item_id, "candidate": candidate, "audio": audio})
    if len(observed) != 28:
        raise RuntimeError("Eş ses çiftleri eksik")
    return checked


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("Bu ASR değerlendirmesi yalnız private Kaggle notebook içinde çalışır")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "--force-reinstall", "faster-whisper==1.2.1", "av>=14,<17"], check=True)
    import ctranslate2
    from faster_whisper import WhisperModel

    if not ctranslate2.get_supported_compute_types("cuda"):
        raise RuntimeError("Whisper large-v3 için GPU gerekli")
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    transcripts, records = [], []
    for clip in inputs():
        started = time.monotonic()
        try:
            segments, _ = model.transcribe(str(clip["audio"]), language="tr", task="transcribe", beam_size=5, vad_filter=True, condition_on_previous_text=False, without_timestamps=True)
            observed = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
            if not observed or len(observed) > 8000:
                raise RuntimeError("Boş veya aşırı uzun ASR çıktısı")
            key = f"{clip['candidate']}.{clip['id']}"
            transcripts.append({"id": key, "observed_spoken_text": observed})
            records.append({"id": key, "status": "transcribed", "seconds": round(time.monotonic() - started, 3)})
        except (RuntimeError, OSError, ValueError) as error:
            message = str(error).lower()
            records.append({"id": f"{clip['candidate']}.{clip['id']}", "status": "failed", "error_type": type(error).__name__, "reason": "empty_or_oversized_transcript" if "boş veya aşırı uzun asr" in message else "cuda_out_of_memory" if "out of memory" in message else "asr_runtime_error"})
    (OUTPUT / "candidate_transcripts.json").write_text(json.dumps({"schema_version": "tts-candidate-v1", "candidate": "base-v3-vs-t3-finetune-v2", "results": transcripts}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_records.json").write_text(json.dumps({"schema_version": "tts-asr-run-v2", "candidate": "base-v3-vs-t3-finetune-v2", "asr_model": "Whisper large-v3", "items_total": 28, "items_transcribed": len(transcripts), "items_failed": 28-len(transcripts), "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({"candidate": "base-v3-vs-t3-finetune-v2", "asr_model": "Whisper large-v3", "language": "tr", "input_private": True, "student_publication": "blocked_pending_blind_listening"}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
