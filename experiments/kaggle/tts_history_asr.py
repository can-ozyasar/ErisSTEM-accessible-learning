"""One private Whisper run for both history voices, with source-matched scoring."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import kaggle_ops
import tts_history_listening as listening

ROOT = kaggle_ops.repo_root()
PRIVATE = kaggle_ops.private_root()
SOURCE = PRIVATE / "eristem_history_tts_eval_v1/tts-history-eval-v1.json"
INPUT_DIR = PRIVATE / "eristem_history_tts_asr_v2"
DATASET = "muhammedcanozyasar/eristem-history-tts-asr-v2"
KERNEL = "muhammedcanozyasar/eristem-history-tts-whisper-v2"
CANDIDATE = "history-piper-vs-chatterbox-v2"
# This is the private download directory created for the 20 October 2026 V3
# run.  It prevents a prior stochastic V3 synthesis from contaminating the
# baseline comparison.
CHATTERBOX_OUTPUT_RUN = "20261020T091906Z"


def prepare() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source_hash = kaggle_ops.sha256(SOURCE)
    piper = listening.load_report(listening.PIPER / "run_records.json", source_hash)
    cb_dir, cb = listening.chatterbox_audio(source_hash, CHATTERBOX_OUTPUT_RUN)
    cb_files = {item["id"]: item for item in cb["manifest"]["files"]}
    piper_records = {item["id"]: item for item in piper["records"]}
    cb_records = {item["id"]: item for item in cb["report"]["records"]}
    if INPUT_DIR.exists():
        raise FileExistsError("Whisper giriş paketi zaten var; var olan girdiler korunuyor")
    assets = []
    for item in source["items"]:
        item_id = item["id"]
        for voice, original, record in (
            ("piper", listening.PIPER / f"{item_id}.wav", piper_records[item_id]),
            ("chatterbox", cb_dir / cb_files[item_id]["path"], cb_records[item_id]),
        ):
            if kaggle_ops.sha256(original) != record["audio_sha256"]:
                raise ValueError("Whisper girdisi ses checksum uyuşmuyor")
            name = f"{voice}.{item_id}"
            assets.append((name, item["kind"], original, record["audio_sha256"]))
    INPUT_DIR.mkdir(parents=True)
    audio_dir = INPUT_DIR / "audio"
    audio_dir.mkdir()
    records = []
    for name, kind, original, digest in assets:
        target = audio_dir / f"{name}.wav"
        shutil.copy2(original, target)
        records.append({"id": name, "kind": kind, "audio_path": f"audio/{name}.wav", "audio_sha256": digest})
    (INPUT_DIR / "tts-asr-input.json").write_text(json.dumps({
        "schema_version": "tts-asr-input-v1", "candidate": CANDIDATE,
        "source_history_input_sha256": source_hash, "assets": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"assets": len(records), "private_input": str(INPUT_DIR)}


def package() -> Path:
    destination = kaggle_ops.kernel_package_directory(KERNEL)
    if destination.exists():
        kaggle_ops.load_kernel_metadata(destination, KERNEL, DATASET)
        return destination
    return kaggle_ops.prepare_notebook_package(
        KERNEL, DATASET, ROOT / "experiments/kaggle/tts_chatterbox_v3_whisper_asr_runner.py",
        "Eristem History Tts Whisper V2", enable_internet=True,
        source_replacements=(
            ("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-chatterbox-v3-audio-v1",
             "/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-asr-v2"),
            ("/kaggle/working/eristem-private-tts-chatterbox-v3-asr-whisper-large-v3-v1",
             "/kaggle/working/eristem-history-tts-whisper-v2"),
        ),
    )


def fetch_and_score() -> dict:
    if "KernelWorkerStatus.COMPLETE" not in kaggle_ops.notebook_status(KERNEL):
        raise RuntimeError("Whisper koşusu henüz tamamlanmadı")
    output, _ = kaggle_ops.download_summaries(KERNEL)
    records = list(output.rglob("run_records.json"))
    if len(records) != 1:
        raise ValueError("Whisper raporu bulunamadı")
    report = json.loads(records[0].read_text(encoding="utf-8"))
    manifest = json.loads((INPUT_DIR / "tts-asr-input.json").read_text(encoding="utf-8"))
    expected_ids = {item["id"] for item in manifest["assets"]}
    if (report.get("candidate") != CANDIDATE or report.get("items_failed") != 0
            or {item.get("id") for item in report.get("records", [])} != expected_ids):
        raise ValueError("Whisper raporunda eksik veya yanlış örnek var")
    transcript_dir = kaggle_ops.output_directory(KERNEL)
    kaggle_ops.run_cli([
        "kernels", "output", KERNEL, "--path", str(transcript_dir), "--force", "--quiet",
        "--file-pattern", kaggle_ops.output_filename_pattern("candidate_transcripts.json"),
    ])
    files = list(transcript_dir.rglob("candidate_transcripts.json"))
    if len(files) != 1:
        raise ValueError("Tek bir Whisper transkripti bulunamadı")
    kaggle_ops.validate_tts_candidate_transcripts(files[0], expected_ids, CANDIDATE)
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    expected = {item["id"]: item for item in json.loads(SOURCE.read_text(encoding="utf-8"))["items"]}
    sys.path.insert(0, str(ROOT / "apps/api"))
    from app.pipeline.tts_text_metrics import speech_character_accuracy, speech_tokens

    results = []
    for item in payload["results"]:
        voice, item_id = item["id"].split(".", 1)
        reference = expected[item_id]
        observed = item["observed_spoken_text"]
        actual_tokens = set(speech_tokens(observed))
        missed = [token for token in reference["critical_tokens"]
                  if not set(speech_tokens(token)).issubset(actual_tokens)]
        results.append({"id": item_id, "voice": voice,
                        "character_accuracy": round(speech_character_accuracy(reference["expected_spoken_text"], observed), 3),
                        "critical_tokens_missed": missed,
                        "observed_spoken_text": observed})
    score_path = PRIVATE / "tts_history_asr_scores_v2.json"
    if score_path.exists():
        raise FileExistsError("Tarih ASR puanı zaten var; eski değerlendirme korunuyor")
    score_path.write_text(json.dumps({"schema_version": "tts-history-asr-screen-v1",
        "input_sha256": kaggle_ops.sha256(SOURCE), "model": "Whisper large-v3",
        "notice": "ASR yalnız ön elemedir; insan dinlemesinin yerine geçmez.",
        "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {}
    for voice in ("piper", "chatterbox"):
        rows = [item for item in results if item["voice"] == voice]
        summary[voice] = {"samples": len(rows),
                          "mean_character_accuracy": round(sum(item["character_accuracy"] for item in rows) / len(rows), 3),
                          "critical_miss_samples": sum(bool(item["critical_tokens_missed"]) for item in rows)}
    return {"private_scores": str(score_path), "summary": summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tarih sesleri için özel Whisper ön elemesi")
    parser.add_argument("command", choices=("prepare", "run", "status", "fetch"))
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare()
    elif args.command == "run":
        identity = kaggle_ops.verify()
        if identity.get("authenticated_user") != KERNEL.split("/", 1)[0]:
            raise ValueError("Kaggle hesabı notebook sahibi değil")
        if not INPUT_DIR.exists():
            prepare()
        notebook = package()
        kaggle_ops.upload_dataset(INPUT_DIR, DATASET, "Private paired history TTS WAV screen v1")
        kaggle_ops.push_notebook(notebook, KERNEL, DATASET, 3600, "NvidiaTeslaT4")
        result = {"started": True, "notebook": KERNEL}
    elif args.command == "status":
        result = {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    else:
        result = fetch_and_score()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
