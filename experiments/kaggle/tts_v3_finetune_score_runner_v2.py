"""Private aggregate ASR scoring for corrected V3 fine-tune; emits no text."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-finetune-eval-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-v3-finetune-score-v2")
EVAL_DIR = "eristem-tts-v3-finetune-eval-v2"
ASR_DIR = "eristem-tts-v3-finetune-asr-v2"
CANDIDATES = ("base", "tuned_v2")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def words(value: str) -> list[str]:
    return re.findall(r"[a-zçğıöşü0-9]+", value.casefold())


def character_accuracy(expected: str, observed: str) -> float:
    left, right = " ".join(words(expected)), " ".join(words(observed))
    prior = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        current = [index]
        for offset, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, prior[offset] + 1, prior[offset - 1] + (char != other)))
        prior = current
    return max(0.0, 1.0 - prior[-1] / max(1, len(left)))


def lone_file(name: str, directory: str) -> Path:
    matches = [path for path in Path("/kaggle/input").rglob(name) if path.parent.name == directory]
    if len(matches) != 1:
        raise RuntimeError(f"Tek {name} bulunamadı: {directory}")
    return matches[0]


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("Bu puanlama yalnız private Kaggle notebook içinde çalışır")
    gold = json.loads(next(SOURCE.rglob("tts-history-eval-v1.json")).read_text(encoding="utf-8"))
    synthesis_path = lone_file("run_records.json", EVAL_DIR)
    asr_path = lone_file("run_records.json", ASR_DIR)
    transcript_path = lone_file("candidate_transcripts.json", ASR_DIR)
    synthesis, asr, transcripts = (json.loads(path.read_text(encoding="utf-8")) for path in (synthesis_path, asr_path, transcript_path))
    items = gold.get("items")
    if gold.get("schema_version") != "tts-history-eval-v1" or not isinstance(items, list) or len(items) != 14 or synthesis.get("schema_version") != "tts-v3-finetune-paired-eval-v2" or asr.get("schema_version") != "tts-asr-run-v2" or transcripts.get("candidate") != "base-v3-vs-t3-finetune-v2":
        raise RuntimeError("Puanlama girdileri uyuşmuyor")
    expected = {row["id"]: row for row in items}
    observed = {row["id"]: row["observed_spoken_text"] for row in transcripts.get("results", [])}
    synth = {(row["candidate"], row["id"]): row for row in synthesis.get("records", [])}
    keyset = {f"{candidate}.{item_id}" for candidate in CANDIDATES for item_id in expected}
    if len(expected) != 14 or len(observed) != 28 or set(observed) != keyset or len(synth) != 28:
        raise RuntimeError("Puanlama örnekleri eksik")
    summary = {}
    for candidate in CANDIDATES:
        accuracy, miss_samples, missed_tokens, latencies, durations = [], 0, 0, [], []
        for item_id, item in expected.items():
            transcript = observed[f"{candidate}.{item_id}"]
            accuracy.append(character_accuracy(item["expected_spoken_text"], transcript))
            found = set(words(transcript))
            missed = [token for token in item.get("critical_tokens", []) if not set(words(token)).issubset(found)]
            miss_samples += bool(missed)
            missed_tokens += len(missed)
            record = synth[candidate, item_id]
            latencies.append(record["generation_seconds"])
            durations.append(record["duration_seconds"])
        summary[candidate] = {"samples": 14, "asr_unrecognized_samples": 0, "mean_character_accuracy": round(sum(accuracy) / 14, 4), "critical_miss_samples": miss_samples, "critical_tokens_missed": missed_tokens, "mean_generation_seconds": round(sum(latencies) / 14, 2), "mean_real_time_factor": round(sum(latency / duration for latency, duration in zip(latencies, durations)) / 14, 3)}
    report = {"schema_version": "tts-v3-finetune-paired-screen-v2", "gold_sha256": sha256(next(SOURCE.rglob("tts-history-eval-v1.json"))), "synthesis_sha256": sha256(synthesis_path), "asr_sha256": sha256(asr_path), "transcripts_sha256": sha256(transcript_path), "asr_model": "Whisper large-v3", "notice": "ASR yalnız ön taramadır; ses doğallığı ve kritik tarih okuması kör dinlemeyle doğrulanmalıdır.", "summary": summary, "paired_delta_character_accuracy": round(summary["tuned_v2"]["mean_character_accuracy"] - summary["base"]["mean_character_accuracy"], 4)}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "run_metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "paired_delta_character_accuracy": report["paired_delta_character_accuracy"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
