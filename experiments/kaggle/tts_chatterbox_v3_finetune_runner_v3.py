"""Cross-reference private Chatterbox V3 Turkish T3 fine-tune experiment.

This program runs only in a private Kaggle notebook.  It streams a permitted
single-speaker source, writes a filtered temporary corpus on the notebook
volume, fine-tunes only V3's T3 network, and emits content-free reports plus
one checksumed T3 artifact.  It never publishes audio, transcripts, or a
consent message.

V1 used same-position token targets and produced noise. V2 corrected that
target alignment, but conditioned each target on its own waveform. This
version uses next-token targets *and a different same-speaker recording* for
the voice/prompt condition, matching normal reference-audio inference.
"""

from __future__ import annotations

import hashlib
import gc
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


RUN_MODE = os.environ.get("ERISTEM_TTS_FINETUNE_MODE", "pilot")
if RUN_MODE not in {"pilot", "quality"}:
    raise RuntimeError("ERISTEM_TTS_FINETUNE_MODE must be pilot or quality")

SOURCE_DATASET = "omersaidd/tts_nisan_kumru_tur"
SOURCE_REVISION = "678712b026da89058feb010886de23983cc8563b"
OFFICIAL_CHATTERBOX_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
BASE_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
MODEL_FILES = ("ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json")
OUTPUT = Path("/kaggle/working/eristem-private-chatterbox-v3-finetune-v3")
WORK = Path("/kaggle/working/eristem-tts-finetune-work-v3")
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
    # A bounded run tests the changed conditioning path before consuming the
    # full GPU allocation. Its artifact is never a quality candidate.
    "pilot": {"corpus_seconds": 3_600.0, "max_steps": 200, "warmup_steps": 20},
    # About 3 h 15 min of accepted speech, with every train row observed.
    "quality": {"corpus_seconds": 11_700.0, "max_steps": 1500, "warmup_steps": 100},
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


def train(corpus: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """Train the official V3 T3 module directly, without a legacy Trainer wrapper."""
    import librosa
    import soundfile as sf
    import torch
    import torch.nn.functional as F
    from huggingface_hub import snapshot_download
    from safetensors.torch import save_file
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS, punc_norm
    from chatterbox.models.s3tokenizer import S3_SR
    from chatterbox.models.t3.modules.cond_enc import T3Cond

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_for_v3_finetune")
    device = torch.device("cuda")
    # Keep frozen feature extractors on CPU.  Only the trainable 0.5B T3 model
    # occupies GPU memory, which is appropriate for a Kaggle T4.
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    np.random.seed(SEED)
    checkpoint = Path(snapshot_download(repo_id="ResembleAI/chatterbox", revision=BASE_REVISION,
                                        allow_patterns=list(MODEL_FILES)))
    if any(not (checkpoint / name).is_file() for name in MODEL_FILES):
        raise RuntimeError("pinned_v3_checkpoint_incomplete")
    model = ChatterboxMultilingualTTS.from_local(str(checkpoint), device="cpu", t3_model="v3")
    model.ve.eval()
    model.s3gen.eval()
    t3 = model.t3.to(device).train()
    for parameter in model.ve.parameters():
        parameter.requires_grad = False
    for parameter in model.s3gen.parameters():
        parameter.requires_grad = False
    base_learning_rate = 3e-6
    optimizer = torch.optim.AdamW(t3.parameters(), lr=base_learning_rate, betas=(0.9, 0.95), weight_decay=0.01)
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
    np.random.default_rng(SEED).shuffle(train_rows)
    if RUN_MODE == "quality" and MODE["max_steps"] < len(train_rows):
        raise RuntimeError("quality_mode_would_skip_training_records")

    # Every condition comes from a different utterance than the target.  The
    # pool contains only training records, including for validation targets,
    # so held-out target audio cannot leak through the reference condition.
    # V3 takes prompt tokens from the first six seconds of a reference. A
    # shorter source would inject zero padding during training, unlike the
    # intended deployment reference. Keep the identity pool representative.
    reference_rows = [
        row for row in train_rows
        if sf.info(Path(corpus["corpus"]) / row[0]).frames / SAMPLE_RATE >= 6.0
    ]
    if len(reference_rows) < 2:
        raise RuntimeError("insufficient_distinct_reference_rows")

    def reference_for(target: tuple[str, str]) -> tuple[str, str]:
        candidates = [row for row in reference_rows if row[0] != target[0]]
        if not candidates:
            raise RuntimeError("cross_reference_selection_failed")
        number = int(hashlib.sha256(f"{SEED}:reference:{target[0]}".encode()).hexdigest()[:16], 16)
        return candidates[number % len(candidates)]

    def features(row: tuple[str, str]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        relative, text = row
        target_waveform, _ = librosa.load(Path(corpus["corpus"]) / relative, sr=S3_SR, mono=True)
        reference_relative, _ = reference_for(row)
        reference_waveform, _ = librosa.load(Path(corpus["corpus"]) / reference_relative, sr=S3_SR, mono=True)
        target_waveform = target_waveform.astype(np.float32)
        reference_waveform = reference_waveform.astype(np.float32)
        with torch.no_grad():
            speaker = torch.from_numpy(model.ve.embeds_from_wavs([reference_waveform], sample_rate=S3_SR)[0]).float()
            raw_speech, speech_lengths = model.s3gen.tokenizer.forward([target_waveform])
            speech = raw_speech.squeeze(0)[: speech_lengths.squeeze(0).item()]
            # This is deliberately a different waveform from `target_waveform`.
            # It matches the official V3 inference path's six-second window.
            prompt, _ = model.s3gen.tokenizer.forward([reference_waveform[: 6 * S3_SR]], max_len=hp.speech_cond_prompt_len)
        text_tokens = model.tokenizer.text_to_tokens(punc_norm(text), language_id="tr").squeeze(0)
        text_tokens = torch.cat((torch.tensor([hp.start_text_token]), text_tokens[: hp.max_text_tokens - 2], torch.tensor([hp.stop_text_token])))
        speech = torch.cat((torch.tensor([hp.start_speech_token]), speech[: hp.max_speech_tokens - 2], torch.tensor([hp.stop_speech_token])))
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
        # A state already contains the token at its position. It must predict
        # the NEXT token, including EOS, as autoregressive inference does.
        if output.speech_logits.size(1) != speech_tokens.size(1) or speech_tokens.size(1) < 2:
            raise RuntimeError("speech_logits_alignment_invalid")
        loss_text = F.cross_entropy(output.text_logits[:, :-1, :].transpose(1, 2).float(), text_tokens[:, 1:])
        loss_speech = F.cross_entropy(output.speech_logits[:, :-1, :].transpose(1, 2).float(), speech_tokens[:, 1:])
        return loss_text + loss_speech

    monitor_rows = validation_rows[: min(16, len(validation_rows))]
    t3.eval()
    with torch.no_grad():
        initial_validation_loss = float(np.mean([float(loss_for(row).detach().cpu()) for row in monitor_rows]))
    if not math.isfinite(initial_validation_loss) or initial_validation_loss < 0.1:
        raise RuntimeError("unexpected_initial_shifted_loss")
    best_monitor_loss = initial_validation_loss
    best_step = 0
    best_state = ({key: value.detach().cpu().clone() for key, value in t3.state_dict().items()}
                  if RUN_MODE == "quality" else None)
    validation_curve = [{"step": 0, "loss": round(initial_validation_loss, 6)}]
    losses: list[float] = []
    t3.train()
    def learning_rate(step: int) -> float:
        warmup = MODE["warmup_steps"]
        if step < warmup:
            return base_learning_rate * (step + 1) / warmup
        progress = (step - warmup) / max(1, MODE["max_steps"] - warmup)
        return base_learning_rate * 0.1 * (1 + 9 * 0.5 * (1 + math.cos(math.pi * min(1.0, progress))))

    for step in range(MODE["max_steps"]):
        row = train_rows[step % len(train_rows)]
        for group in optimizer.param_groups:
            group["lr"] = learning_rate(step)
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=torch.float16):
            loss = loss_for(row)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(t3.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        losses.append(float(loss.detach().cpu()))
        if ((step + 1) % (50 if RUN_MODE == "pilot" else 250) == 0 or step + 1 == MODE["max_steps"]):
            t3.eval()
            with torch.no_grad():
                monitor_loss = float(np.mean([float(loss_for(row).detach().cpu()) for row in monitor_rows]))
            if not math.isfinite(monitor_loss):
                raise RuntimeError("nonfinite_monitor_loss")
            validation_curve.append({"step": step + 1, "loss": round(monitor_loss, 6)})
            if RUN_MODE == "quality" and monitor_loss < best_monitor_loss:
                best_monitor_loss = monitor_loss
                best_step = step + 1
                best_state = {key: value.detach().cpu().clone() for key, value in t3.state_dict().items()}
            t3.train()
    if best_state is not None:
        t3.load_state_dict(best_state)
        del best_state
    t3.eval()
    with torch.no_grad():
        validation_losses = [float(loss_for(row).detach().cpu()) for row in validation_rows[: min(8 if RUN_MODE == "pilot" else len(validation_rows), len(validation_rows))]]
    if not all(math.isfinite(value) for value in losses + validation_losses):
        raise RuntimeError("nonfinite_training_or_validation_loss")
    t3.zero_grad(set_to_none=True)
    del optimizer, scaler
    gc.collect()
    torch.cuda.empty_cache()
    # V3 inference attaches `patched_model` as a second view of T3 weights.
    # Save the canonical state first; otherwise safetensors sees shared aliases.
    model_output = WORK / "model"
    model_output.mkdir(parents=True, exist_ok=True)
    result = model_output / "t3_mtl23ls_v3.safetensors"
    save_file({key: value.detach().cpu().contiguous() for key, value in t3.state_dict().items()}, result)
    if not result.is_file() or result.stat().st_size < 100_000_000:
        raise RuntimeError("missing_or_unexpected_t3_artifact")
    # A short held-out synthesis catches EOS failure before a 2 GB artifact is
    # accepted. Its audio stays inside the private notebook output.
    reference_path = Path(corpus["corpus"]) / reference_for(validation_rows[0])[0]
    model.ve.to(device).eval()
    model.s3gen.to(device).eval()
    model.device = "cuda"
    probe_text = "Bugün tarih dersinde eski uygarlıkları öğreniyoruz."
    probe_waveform = model.generate(probe_text, language_id="tr", audio_prompt_path=str(reference_path))
    probe_samples = probe_waveform.detach().float().cpu().numpy().squeeze()
    probe_duration = len(probe_samples) / model.sr
    if not np.isfinite(probe_samples).all() or not 1.0 <= probe_duration <= 15.0:
        raise RuntimeError(f"post_training_speech_duration_invalid:{probe_duration:.3f}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sf.write(OUTPUT / "private-smoke-speech.wav", probe_samples, model.sr)
    model.ve.cpu()
    model.s3gen.cpu()
    t3.cpu()
    torch.cuda.empty_cache()
    return result, {"steps": MODE["max_steps"], "train_items": len(train_rows),
                    "train_items_seen": min(MODE["max_steps"], len(train_rows)),
                    "initial_validation_loss": round(initial_validation_loss, 6),
                    "selected_step": best_step if RUN_MODE == "quality" else MODE["max_steps"],
                    "selected_monitor_loss": round(best_monitor_loss, 6) if RUN_MODE == "quality" else None,
                    "validation_curve": validation_curve,
                    "train_loss_last": round(losses[-1], 6),
                    "train_loss_mean": round(float(np.mean(losses)), 6),
                    "validation_loss_mean": round(float(np.mean(validation_losses)), 6),
                    "validation_items": len(validation_losses),
                    "reference_conditioning": "different_training_utterance_per_target_minimum_6_seconds",
                    "reference_pool_items": len(reference_rows),
                    "probe_duration_seconds": round(probe_duration, 3)}


def emit_reports(corpus_report: dict[str, Any], artifact: Path, metrics: dict[str, Any]) -> None:
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
        "candidate": f"chatterbox-multilingual-v3-t3-cross-reference-v3-{RUN_MODE}",
        "student_publication": "blocked_pending_heldout_evaluation",
        "base_model": {"repository": "ResembleAI/chatterbox", "revision": BASE_REVISION, "code_commit": OFFICIAL_CHATTERBOX_COMMIT, "t3_model": "v3"},
        "trainer": {"implementation": "direct-v3-t3-next-token-cross-reference-v3", "scope": "T3 only; voice encoder and S3Gen frozen", "conditioning": "different training utterance per target; reference minimum six seconds"},
        "hyperparameters": {"max_steps": MODE["max_steps"], "warmup_steps": MODE["warmup_steps"], "batch_size": 1, "optimizer": "AdamW", "learning_rate_peak": 3e-6, "schedule": "linear warmup then cosine decay to 10 percent", "precision": "fp16", "seed": SEED},
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
