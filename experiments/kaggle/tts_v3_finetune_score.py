"""Score the private paired V3 fine-tune ASR screen against sealed history text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.pipeline.tts_text_metrics import speech_character_accuracy, speech_tokens  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(gold_path: Path, synthesis_path: Path, asr_path: Path, transcripts_path: Path) -> dict:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
    asr = json.loads(asr_path.read_text(encoding="utf-8"))
    transcripts = json.loads(transcripts_path.read_text(encoding="utf-8"))
    items = gold.get("items")
    if gold.get("schema_version") != "tts-history-eval-v1" or not isinstance(items, list) or len(items) != 14:
        raise ValueError("Sabit 14 örneklik tarih kümesi değişmiş")
    expected = {row["id"]: row for row in items}
    if len(expected) != 14 or synthesis.get("input_sha256") != sha256(gold_path):
        raise ValueError("Ses üretimi tarih Gold kümesiyle eşleşmiyor")
    records = synthesis.get("records")
    if not isinstance(records, list) or len(records) != 28 or any(row.get("status") != "generated" for row in records):
        raise ValueError("Eş ses kayıtları eksik")
    if asr.get("items_total") != 28 or not isinstance(asr.get("records"), list) or len(asr["records"]) != 28:
        raise ValueError("ASR koşusu eksik")
    if transcripts.get("schema_version") != "tts-candidate-v1" or transcripts.get("candidate") != "base-v3-vs-t3-finetune-v1":
        raise ValueError("ASR transkript şeması yanlış")
    observed = {row["id"]: row["observed_spoken_text"] for row in transcripts.get("results", [])}
    keys = {f"{candidate}.{item_id}" for candidate in ("base", "tuned") for item_id in expected}
    asr_status = {row["id"]: row for row in asr["records"]}
    if len(asr_status) != 28 or set(asr_status) != keys or len(observed) != asr.get("items_transcribed") or not set(observed).issubset(keys):
        raise ValueError("ASR kimlikleri eşleşmiyor")
    if asr.get("items_failed") != 28 - len(observed) or any(
        (row["status"] == "transcribed") != (key in observed)
        or (row["status"] == "failed" and row.get("reason") != "empty_or_oversized_transcript")
        for key, row in asr_status.items()
    ):
        raise ValueError("ASR başarısızlıkları sınıflandırılamadı")
    synthesis_by_key = {(row["candidate"], row["id"]): row for row in records}
    if len(synthesis_by_key) != 28 or set(synthesis_by_key) != {(key.split(".", 1)[0], key.split(".", 1)[1]) for key in keys}:
        raise ValueError("Ses üretimi kimlikleri eşleşmiyor")

    results = []
    for candidate in ("base", "tuned"):
        for item_id, item in expected.items():
            transcript = observed.get(f"{candidate}.{item_id}", "")
            tokens = set(speech_tokens(transcript))
            missed = [token for token in item.get("critical_tokens", []) if not set(speech_tokens(token)).issubset(tokens)]
            record = synthesis_by_key[(candidate, item_id)]
            results.append({
                "id": item_id, "candidate": candidate,
                "asr_status": "transcribed" if transcript else "unrecognized",
                "character_accuracy": round(speech_character_accuracy(item["expected_spoken_text"], transcript), 4) if transcript else 0.0,
                "critical_miss_count": len(missed),
                "critical_tokens_missed": missed,
                "generation_seconds": record["generation_seconds"],
                "audio_duration_seconds": record["duration_seconds"],
            })
    summary = {}
    for candidate in ("base", "tuned"):
        rows = [row for row in results if row["candidate"] == candidate]
        summary[candidate] = {
            "samples": len(rows),
            "asr_unrecognized_samples": sum(row["asr_status"] == "unrecognized" for row in rows),
            "mean_character_accuracy": round(sum(row["character_accuracy"] for row in rows) / len(rows), 4),
            "critical_miss_samples": sum(row["critical_miss_count"] > 0 for row in rows),
            "critical_tokens_missed": sum(row["critical_miss_count"] for row in rows),
            "mean_generation_seconds": round(sum(row["generation_seconds"] for row in rows) / len(rows), 2),
            "mean_real_time_factor": round(sum(row["generation_seconds"] / row["audio_duration_seconds"] for row in rows) / len(rows), 3),
        }
    return {
        "schema_version": "tts-v3-finetune-paired-screen-v1",
        "gold_sha256": sha256(gold_path),
        "synthesis_sha256": sha256(synthesis_path),
        "asr_sha256": sha256(asr_path),
        "transcripts_sha256": sha256(transcripts_path),
        "asr_model": "Whisper large-v3",
        "notice": "ASR yalnız ön taramadır; ses doğallığı ve kritik tarih okuması kör dinlemeyle doğrulanmalıdır.",
        "summary": summary,
        "paired_delta_character_accuracy": round(summary["tuned"]["mean_character_accuracy"] - summary["base"]["mean_character_accuracy"], 4),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--synthesis", type=Path, required=True)
    parser.add_argument("--asr", type=Path, required=True)
    parser.add_argument("--transcripts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / "data/private").resolve()
    if any(not path.resolve().is_relative_to(private) for path in (args.gold, args.synthesis, args.asr, args.transcripts, args.output)):
        raise ValueError("Tüm değerlendirme yolları data/private altında olmalı")
    result = score(args.gold, args.synthesis, args.asr, args.transcripts)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": result["summary"], "paired_delta_character_accuracy": result["paired_delta_character_accuracy"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
