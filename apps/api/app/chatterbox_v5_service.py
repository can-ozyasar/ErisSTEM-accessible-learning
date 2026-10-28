"""Optional localhost-only V5 synthesis service; all model files are local."""

from __future__ import annotations

import hashlib
import io
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

MODEL_NAME = "t3_mtl23ls_v3.safetensors"
MODEL_SHA256 = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"
MAX_CHUNK_CHARS = 240
MAX_TEXT_CHARS = 8000
MAX_AUDIO_BYTES = 32 * 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split_text(text: str) -> list[str]:
    words = text.split()
    if not words or len(text) > MAX_TEXT_CHARS:
        raise ValueError("invalid_text_length")
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > MAX_CHUNK_CHARS:
            raise ValueError("word_too_long")
        candidate = f"{current} {word}" if current else word
        if len(candidate) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


def create_app(model_dir: Path, reference: Path, device: str = "cuda") -> FastAPI:
    """Create an offline service. Model identity is checked before loading."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    weight = model_dir / MODEL_NAME
    if not weight.is_file() or file_sha256(weight) != MODEL_SHA256:
        raise RuntimeError("v5_weight_missing_or_checksum_mismatch")
    if not reference.is_file():
        raise RuntimeError("reference_audio_missing")
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    info = sf.info(reference)
    if info.samplerate <= 0 or info.frames / info.samplerate < 6:
        raise RuntimeError("reference_audio_too_short")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_unavailable")
    model = ChatterboxMultilingualTTS.from_local(str(model_dir), device=device, t3_model="v3")
    model.t3.eval()
    model.ve.eval()
    model.s3gen.eval()
    lock = threading.Lock()
    app = FastAPI(title="ErişSTEM local V5 speech")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ready", "model": "chatterbox-v3-t3-v5", "device": device}

    @app.post("/")
    def synthesize(request: SynthesisRequest) -> Response:
        try:
            chunks = split_text(request.text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        audio = []
        with lock, torch.inference_mode():
            for chunk in chunks:
                waveform = model.generate(chunk, language_id="tr", audio_prompt_path=str(reference))
                samples = waveform.detach().float().cpu().numpy().squeeze()
                if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
                    raise HTTPException(status_code=503, detail="invalid_audio")
                samples = samples * 0.60
                if np.max(np.abs(samples)) >= 0.999:
                    raise HTTPException(status_code=503, detail="audio_peak_exceeded")
                audio.append(samples)
        output = io.BytesIO()
        sf.write(output, np.concatenate(audio), model.sr, format="WAV", subtype="PCM_16")
        data = output.getvalue()
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=503, detail="audio_too_long")
        return Response(content=data, media_type="audio/wav")

    return app


def main() -> None:
    import uvicorn

    model_dir = os.environ.get("ERISTEM_V5_MODEL_DIR", "").strip()
    reference = os.environ.get("ERISTEM_V5_REFERENCE_WAV", "").strip()
    if not model_dir or not reference:
        raise RuntimeError("set_model_dir_and_reference_wav")
    application = create_app(Path(model_dir), Path(reference), os.getenv("ERISTEM_V5_DEVICE", "cuda"))
    uvicorn.run(application, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
