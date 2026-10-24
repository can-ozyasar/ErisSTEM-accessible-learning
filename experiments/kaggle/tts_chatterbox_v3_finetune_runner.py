"""Private, reproducible Chatterbox V3 Turkish voice fine-tune experiment.

This program runs only in a private Kaggle notebook.  It streams a permitted
single-speaker source, writes a filtered temporary corpus on the notebook
volume, fine-tunes only V3's T3 network, and emits content-free reports plus
one checksumed T3 artifact.  It never publishes audio, transcripts, or a
consent message.

The official Chatterbox repository provides V3 inference, but no maintained
V3 trainer.  The trainer used here is a pinned community implementation after
a compatibility patch and a smoke run.  Treat its results as experimental.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


RUN_MODE = os.environ.get("ERISTEM_TTS_FINETUNE_MODE", "quality")
if RUN_MODE not in {"smoke", "quality"}:
    raise RuntimeError("ERISTEM_TTS_FINETUNE_MODE must be smoke or quality")

SOURCE_DATASET = "omersaidd/tts_nisan_kumru_tur"
SOURCE_REVISION = "678712b026da89058feb010886de23983cc8563b"
OFFICIAL_CHATTERBOX_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
TRAINER_REPOSITORY = "https://github.com/99eren99/chatterbox-multilingual-finetuning.git"
TRAINER_COMMIT = "bf2017ddc1266acedb23189a4e9c823c91be8586"
OUTPUT = Path("/kaggle/working/eristem-private-chatterbox-v3-finetune")
WORK = Path("/kaggle/working/eristem-tts-finetune-work")
# Content-free attached control dataset.  The actual voice source is streamed
# from its pinned Hugging Face revision and is never uploaded from this repo.
CONTROL_INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-finetune-control-v1")
SAMPLE_RATE = 24_000
SEED = 2_026_1020


@dataclass(frozen=True)
class QualityPolicy:
    min_seconds: float = 1.2
    max_seconds: float = 15.0
    min_rms_dbfs: float = -42.0
    max_rms_dbfs: float = -12.0
    max_abs_peak: float = 0.995
    max_clip_fraction: float = 0.001
    min_active_fraction: float = 0.55
    min_text_characters: int = 4
    max_text_characters: int = 340


POLICY = QualityPolicy()
MODE = {
    # The smoke run proves V3/trainer compatibility only; its artifact is never
    # presented as a quality candidate.
    "smoke": {"corpus_seconds": 540.0, "max_steps": 2},
    # About 3 h 15 min of accepted speech leaves ~15 min for the trainer's
    # deterministic 8% held-out validation split.
    "quality": {"corpus_seconds": 11_700.0, "max_steps": 600},
}[RUN_MODE]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def install_environment() -> None:
    run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    # Kaggle's base image can pair incompatible torchvision/PEFT builds with
    # a newest Transformers release. The T3 trainer uses neither package.
    run([sys.executable, "-m", "pip", "uninstall", "--yes", "peft", "torchvision"])
    run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "datasets==3.6.0", "transformers==4.52.4", "accelerate==1.7.0", "soundfile>=0.12", "librosa>=0.10", "tensorboard", "safetensors"])
    run([sys.executable, "-m", "pip", "install", "--quiet", f"git+https://github.com/resemble-ai/chatterbox.git@{OFFICIAL_CHATTERBOX_COMMIT}"])


def patched_trainer() -> Path:
    destination = WORK / "trainer"
    run(["git", "clone", "--quiet", TRAINER_REPOSITORY, str(destination)])
    run(["git", "checkout", "--quiet", TRAINER_COMMIT], cwd=destination)
    # The community trainer vendors an older Chatterbox package under src/.
    # Executing its script would put that package first on sys.path and silently
    # bypass V3.  Keep only the trainer script; import the pinned official code.
    shutil.rmtree(destination / "src" / "chatterbox")
    script = destination / "src" / "finetune_t3.py"
    body = script.read_text(encoding="utf-8")
    # The audited implementation predates V3 and otherwise silently chooses V2.
    body = body.replace("from_pretrained(device=\"cpu\")", "from_pretrained(device=\"cpu\", t3_model=\"v3\")")
    body = body.replace('"t3_mtl23ls_v2.safetensors"', '"t3_mtl23ls_v3.safetensors"')
    body = body.replace("from chatterbox.tts import ChatterboxTTS, Conditionals, punc_norm, REPO_ID", "from chatterbox.mtl_tts import punc_norm, REPO_ID")
    # Current official V3 calculates shifted-token losses internally.  The
    # pinned community wrapper was written for an older loss API that accepted
    # externally built labels and fails before its first optimizer step.
    old_loss_labels = "            labels_text=labels_text,\n            labels_speech=labels_speech,\n"
    if old_loss_labels not in body:
        raise RuntimeError("expected_legacy_t3_loss_call_not_found")
    body = body.replace(old_loss_labels, "")
    # V3 requires the padded tensors to end exactly at the largest real length
    # in the batch and returns two losses (the old trainer expects three).
    forward_anchor = "    ):\n        current_t3_cond = T3Cond(\n"
    forward_replacement = (
        "    ):\n"
        "        text_tokens = text_tokens[:, :int(text_token_lens.max().item())]\n"
        "        speech_tokens = speech_tokens[:, :int(speech_token_lens.max().item())]\n"
        "        current_t3_cond = T3Cond(\n"
    )
    if forward_anchor not in body:
        raise RuntimeError("expected_t3_wrapper_forward_anchor_not_found")
    body = body.replace(forward_anchor, forward_replacement, 1)
    if "loss_text, loss_speech, speech_logits = self.t3.loss(" not in body or "return total_loss, speech_logits" not in body:
        raise RuntimeError("expected_legacy_t3_loss_return_not_found")
    body = body.replace("loss_text, loss_speech, speech_logits = self.t3.loss(", "loss_text, loss_speech = self.t3.loss(")
    body = body.replace("return total_loss, speech_logits", "return (total_loss,)")
    script.write_text(body, encoding="utf-8")
    probe = (
        "import inspect; from chatterbox.mtl_tts import ChatterboxMultilingualTTS; "
        "from chatterbox.models.t3.t3 import T3; "
        "assert 't3_model' in inspect.signature(ChatterboxMultilingualTTS.from_pretrained).parameters; "
        "assert 'labels_text' not in inspect.signature(T3.loss).parameters; "
        "assert {'t3_cond','text_tokens','text_token_lens','speech_tokens','speech_token_lens'} <= set(inspect.signature(T3.loss).parameters)"
    )
    run([sys.executable, "-c", probe], cwd=script.parent)
    final_body = script.read_text(encoding="utf-8")
    required_patches = (
        "text_tokens = text_tokens[:, :int(text_token_lens.max().item())]",
        "speech_tokens = speech_tokens[:, :int(speech_token_lens.max().item())]",
        "loss_text, loss_speech = self.t3.loss(",
        "return (total_loss,)",
    )
    if not all(token in final_body for token in required_patches):
        raise RuntimeError("incomplete_v3_trainer_compatibility_patch")
    return script


def mono_float(audio: Any) -> tuple[np.ndarray, int]:
    array = np.asarray(audio["array"], dtype=np.float32)
    sample_rate = int(audio["sampling_rate"])
    if array.ndim == 2:
        array = np.mean(array, axis=1 if array.shape[0] > array.shape[1] else 0)
    if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
        raise ValueError("invalid_audio")
    return np.clip(array, -1.0, 1.0), sample_rate


def acoustic_metrics(waveform: np.ndarray, sample_rate: int) -> dict[str, float]:
    duration = len(waveform) / sample_rate
    rms = float(np.sqrt(np.mean(np.square(waveform), dtype=np.float64)))
    rms_dbfs = 20 * math.log10(max(rms, 1e-9))
    frame = max(1, int(sample_rate * 0.04))
    usable = waveform[: len(waveform) - len(waveform) % frame]
    frame_rms = np.sqrt(np.mean(np.square(usable.reshape(-1, frame)), axis=1)) if len(usable) else np.array([0.0])
    active_threshold = max(rms * 0.18, 10 ** (-48 / 20))
    return {
        "duration_seconds": duration,
        "rms_dbfs": rms_dbfs,
        "peak": float(np.max(np.abs(waveform))),
        "clip_fraction": float(np.mean(np.abs(waveform) >= 0.999)),
        "active_fraction": float(np.mean(frame_rms >= active_threshold)),
    }


def accepted(text: Any, metrics: dict[str, float], source_index: int) -> bool:
    # Source item zero is the known music/melody recording and is always excluded.
    if source_index == 0 or not isinstance(text, str):
        return False
    text = " ".join(text.split())
    if not POLICY.min_text_characters <= len(text) <= POLICY.max_text_characters:
        return False
    return (
        POLICY.min_seconds <= metrics["duration_seconds"] <= POLICY.max_seconds
        and POLICY.min_rms_dbfs <= metrics["rms_dbfs"] <= POLICY.max_rms_dbfs
        and metrics["peak"] <= POLICY.max_abs_peak
        and metrics["clip_fraction"] <= POLICY.max_clip_fraction
        and metrics["active_fraction"] >= POLICY.min_active_fraction
    )


def resample_to_24k(waveform: np.ndarray, source_rate: int) -> np.ndarray:
    if source_rate == SAMPLE_RATE:
        return waveform
    import librosa
    return librosa.resample(waveform, orig_sr=source_rate, target_sr=SAMPLE_RATE).astype(np.float32)


def build_filtered_corpus() -> dict[str, Any]:
    from datasets import Audio, load_dataset
    import soundfile as sf

    corpus = WORK / "corpus"
    audio_dir = corpus / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    metadata = corpus / "metadata.tsv"
    dataset = load_dataset(SOURCE_DATASET, revision=SOURCE_REVISION, split="train", streaming=True)
    dataset = dataset.cast_column("audio", Audio(decode=True))
    counters: dict[str, Any] = {"seen": 0, "accepted": 0, "rejected": 0, "rejections": {}, "selected_seconds": 0.0}
    with metadata.open("w", encoding="utf-8") as target:
        for fallback_index, row in enumerate(dataset):
            # The source's first row is the known melody; keeping natural
            # streaming order lets this exclusion be exact and auditable.
            source_index = fallback_index
            counters["seen"] += 1
            try:
                waveform, source_rate = mono_float(row["audio"])
                metrics = acoustic_metrics(waveform, source_rate)
                if not accepted(row.get("text"), metrics, source_index):
                    raise ValueError("quality_policy")
                if counters["selected_seconds"] >= MODE["corpus_seconds"]:
                    continue
                waveform = resample_to_24k(waveform, source_rate)
                item_id = f"u{source_index:05d}"
                relative = f"audio/{item_id}.wav"
                sf.write(audio_dir / f"{item_id}.wav", waveform, SAMPLE_RATE, subtype="PCM_16")
                text = " ".join(str(row["text"]).split()).replace("\t", " ").replace("\n", " ")
                target.write(f"{relative}\t{text}\n")
                counters["accepted"] += 1
                counters["selected_seconds"] += metrics["duration_seconds"]
            except Exception as error:
                counters["rejected"] += 1
                reason = str(error).split(":", 1)[0][:80]
                counters["rejections"][reason] = counters["rejections"].get(reason, 0) + 1
            if counters["selected_seconds"] >= MODE["corpus_seconds"]:
                break
    counters["selected_seconds"] = round(counters["selected_seconds"], 3)
    if counters["selected_seconds"] < MODE["corpus_seconds"] * 0.95:
        raise RuntimeError("insufficient_filtered_audio")
    return {"corpus": corpus, "metadata": metadata, "report": counters}


def train(corpus: dict[str, Any]) -> tuple[Path, dict[str, float | int]]:
    """Train the official V3 T3 module directly, without a legacy Trainer wrapper."""
    import librosa
    import torch
    import torch.nn.functional as F
    from safetensors.torch import save_file
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS, punc_norm
    from chatterbox.models.s3tokenizer import S3_SR
    from chatterbox.models.t3.modules.cond_enc import T3Cond

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_for_v3_finetune")
    device = torch.device("cuda")
    # Keep frozen feature extractors on CPU.  Only the trainable 0.5B T3 model
    # occupies GPU memory, which is appropriate for a Kaggle T4.
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu", t3_model="v3")
    model.ve.eval()
    model.s3gen.eval()
    t3 = model.t3.to(device).train()
    for parameter in model.ve.parameters():
        parameter.requires_grad = False
    for parameter in model.s3gen.parameters():
        parameter.requires_grad = False
    optimizer = torch.optim.AdamW(t3.parameters(), lr=1e-5, betas=(0.9, 0.95), weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda")
    hp = t3.hp

    rows: list[tuple[str, str]] = []
    for line in Path(corpus["metadata"]).read_text(encoding="utf-8").splitlines():
        relative, text = line.split("\t", 1)
        rows.append((relative, text))
    train_rows = [row for index, row in enumerate(rows) if int(hashlib.sha256(f"{SEED}:{index}".encode()).hexdigest()[:8], 16) % 100 >= 8]
    validation_rows = [row for index, row in enumerate(rows) if int(hashlib.sha256(f"{SEED}:{index}".encode()).hexdigest()[:8], 16) % 100 < 8]
    if not train_rows or not validation_rows:
        raise RuntimeError("deterministic_train_validation_split_empty")

    def features(row: tuple[str, str]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        relative, text = row
        waveform, _ = librosa.load(Path(corpus["corpus"]) / relative, sr=S3_SR, mono=True)
        waveform = waveform.astype(np.float32)
        with torch.no_grad():
            speaker = torch.from_numpy(model.ve.embeds_from_wavs([waveform], sample_rate=S3_SR)[0]).float()
            raw_speech, speech_lengths = model.s3gen.tokenizer.forward([waveform])
            speech = raw_speech.squeeze(0)[: speech_lengths.squeeze(0).item()]
            prompt, _ = model.s3gen.tokenizer.forward([waveform[: 3 * S3_SR]], max_len=hp.speech_cond_prompt_len)
        text_tokens = model.tokenizer.text_to_tokens(punc_norm(text), language_id="tr").squeeze(0)
        text_tokens = torch.cat((torch.tensor([hp.start_text_token]), text_tokens, torch.tensor([hp.stop_text_token])))[: hp.max_text_tokens]
        speech = torch.cat((torch.tensor([hp.start_speech_token]), speech, torch.tensor([hp.stop_speech_token])))[: hp.max_speech_tokens]
        prompt = prompt.squeeze(0).long()
        prompt = prompt[: hp.speech_cond_prompt_len]
        prompt = F.pad(prompt, (0, hp.speech_cond_prompt_len - prompt.size(0)))
        return text_tokens.long(), speech.long(), speaker, prompt, torch.tensor([[[0.5]]], dtype=torch.float32)

    def loss_for(row: tuple[str, str]) -> torch.Tensor:
        text_tokens, speech_tokens, speaker, prompt, emotion = features(row)
        text_tokens = text_tokens.unsqueeze(0).to(device)
        speech_tokens = speech_tokens.unsqueeze(0).to(device)
        text_lens = torch.tensor([text_tokens.size(1)], dtype=torch.long, device=device)
        speech_lens = torch.tensor([speech_tokens.size(1)], dtype=torch.long, device=device)
        condition = T3Cond(speaker_emb=speaker.unsqueeze(0).to(device), cond_prompt_speech_tokens=prompt.unsqueeze(0).to(device), cond_prompt_speech_emb=None, emotion_adv=emotion.to(device))
        output = t3.forward(t3_cond=condition, text_tokens=text_tokens, text_token_lens=text_lens, speech_tokens=speech_tokens, speech_token_lens=speech_lens, training=True)
        # The logits are [batch, tokens, vocabulary]; state the vocabulary
        # axis explicitly instead of inheriting the legacy wrapper's loss code.
        loss_text = F.cross_entropy(output.text_logits.transpose(1, 2), text_tokens)
        loss_speech = F.cross_entropy(output.speech_logits.transpose(1, 2), speech_tokens)
        return loss_text + loss_speech

    losses: list[float] = []
    for step in range(MODE["max_steps"]):
        row = train_rows[step % len(train_rows)]
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=torch.float16):
            loss = loss_for(row)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(t3.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        losses.append(float(loss.detach().cpu()))
    t3.eval()
    with torch.no_grad():
        validation_losses = [float(loss_for(row).detach().cpu()) for row in validation_rows[: min(8, len(validation_rows))]]
    model_output = WORK / "model"
    model_output.mkdir(parents=True, exist_ok=True)
    result = model_output / "t3_mtl23ls_v3.safetensors"
    save_file(t3.cpu().state_dict(), result)
    if not result.is_file() or result.stat().st_size < 100_000_000:
        raise RuntimeError("missing_or_unexpected_t3_artifact")
    return result, {"steps": MODE["max_steps"], "train_loss_last": round(losses[-1], 6), "train_loss_mean": round(float(np.mean(losses)), 6), "validation_loss_mean": round(float(np.mean(validation_losses)), 6), "validation_items": len(validation_losses)}


def emit_reports(corpus_report: dict[str, Any], artifact: Path, metrics: dict[str, float | int]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifact_target = OUTPUT / artifact.name
    shutil.copy2(artifact, artifact_target)
    created = datetime.now(UTC).isoformat()
    data_report = {
        "schema_version": "tts-finetune-data-audit-v1",
        "created_at": created,
        "source_dataset": SOURCE_DATASET,
        "source_revision": SOURCE_REVISION,
        "contains_audio": False,
        "contains_transcripts": False,
        "mode": RUN_MODE,
        "quality_policy": asdict(POLICY),
        "known_music_source_item_excluded": True,
        "selection": corpus_report,
        "heldout_validation": {"method": "trainer deterministic random split", "seed": SEED, "fraction": 0.08, "audio_or_transcript_in_report": False},
    }
    metadata = {
        "schema_version": "tts-finetune-run-v1",
        "created_at": created,
        "candidate": f"chatterbox-multilingual-v3-t3-finetune-{RUN_MODE}",
        "student_publication": "blocked_pending_heldout_evaluation",
        "base_model": {"repository": "ResembleAI/chatterbox", "revision": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18", "code_commit": OFFICIAL_CHATTERBOX_COMMIT, "t3_model": "v3"},
        "trainer": {"implementation": "direct-official-v3-t3-training-loop-v1", "scope": "T3 only; voice encoder and S3Gen frozen"},
        "hyperparameters": {"max_steps": MODE["max_steps"], "batch_size": 1, "optimizer": "AdamW", "learning_rate": 1e-5, "precision": "fp16", "seed": SEED},
        "metrics": metrics,
    }
    manifest = {
        "schema_version": "tts-finetune-artifact-v1",
        "created_at": created,
        "local_restore": "Install the pinned official Chatterbox code and replace its t3_mtl23ls_v3.safetensors with this file in the local checkpoint directory.",
        "files": [{"path": artifact_target.name, "sha256": sha256(artifact_target), "bytes": artifact_target.stat().st_size}],
    }
    (OUTPUT / "training_data_report.json").write_text(json.dumps(data_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("This runner is restricted to a private Kaggle notebook")
    if not CONTROL_INPUT.exists():
        raise RuntimeError("private_finetune_control_dataset_not_attached")
    install_environment()
    WORK.mkdir(parents=True, exist_ok=True)
    corpus = build_filtered_corpus()
    artifact, metrics = train(corpus)
    emit_reports(corpus["report"], artifact, metrics)


if __name__ == "__main__":
    main()
