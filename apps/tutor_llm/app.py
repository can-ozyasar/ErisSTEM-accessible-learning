"""GPU-only local Qwen3 service for the history coach.

It has no PDF/question-bank mounts and receives only the bounded, answer-key
free prompt produced by the API.  The model is loaded from a versioned local
manifest; it never downloads weights during a learner session.
"""
from __future__ import annotations

import json
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MANIFEST = Path(os.getenv("TUTOR_MODEL_MANIFEST", "/models/manifest.json"))


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=6000)
    max_tokens: int = Field(default=96, ge=1, le=96)
    temperature: float = Field(default=0.2, ge=0, le=1)
    response_format: str = "text"


def manifest() -> dict:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise HTTPException(503, "Yerel koç model manifesti hazır değil") from error
    required = {"model_id", "revision", "model_path", "tokenizer_path", "quantization", "adapter_path"}
    if not isinstance(value, dict) or required - set(value):
        raise HTTPException(503, "Yerel koç model manifesti geçersiz")
    if value["quantization"] != "nf4-4bit-fp16" or not str(value["model_id"]).startswith("Qwen/Qwen3-14B"):
        raise HTTPException(503, "Bu servis yalnız sabit Qwen3-14B NF4 manifestini kabul eder")
    for key in ("model_path", "tokenizer_path", "adapter_path"):
        if not Path(value[key]).is_dir():
            raise HTTPException(503, f"Manifestteki {key} yolu bulunamadı")
    return value


@lru_cache(maxsize=1)
def load_model():
    config = manifest()
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as error:
        raise HTTPException(503, "GPU koç çalışma zamanı kurulmamış") from error
    if not torch.cuda.is_available():
        raise HTTPException(503, "GPU bulunamadı; LLM koçu bu cihazda açılmaz")
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    tokenizer = AutoTokenizer.from_pretrained(config["tokenizer_path"], local_files_only=True)
    base = AutoModelForCausalLM.from_pretrained(config["model_path"], local_files_only=True,
                                                  quantization_config=quant, device_map={"": 0}, dtype=torch.float16)
    model = PeftModel.from_pretrained(base, config["adapter_path"], local_files_only=True).eval()
    return tokenizer, model


app = FastAPI(title="Eriştem Local Tutor LLM", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    config = manifest()
    return {"ready": True, "model_id": config["model_id"], "revision": config["revision"]}


@app.post("/generate")
def generate(request: GenerateRequest):
    if request.response_format != "text":
        raise HTTPException(422, "Yalnız text yanıt biçimi desteklenir")
    tokenizer, model = load_model()
    import torch

    messages = [{"role": "user", "content": request.prompt}]
    try:
        inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                               return_dict=True, return_tensors="pt", enable_thinking=False)
    except TypeError:  # pinned model versions prior to the flag still work in non-reasoning prompts
        inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                               return_dict=True, return_tensors="pt")
    inputs = inputs.to("cuda:0")
    torch.cuda.synchronize()
    started = time.monotonic()
    from transformers import TextIteratorStreamer

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    generation = {**inputs, "max_new_tokens": request.max_tokens, "do_sample": False, "use_cache": True,
                  "pad_token_id": tokenizer.eos_token_id, "streamer": streamer}
    thread = threading.Thread(target=model.generate, kwargs=generation, daemon=True)
    thread.start()
    pieces: list[str] = []
    first_token_ms: int | None = None
    for piece in streamer:
        if first_token_ms is None:
            first_token_ms = int((time.monotonic() - started) * 1000)
        pieces.append(piece)
    thread.join()
    torch.cuda.synchronize()
    elapsed = int((time.monotonic() - started) * 1000)
    text = "".join(pieces).strip()
    return {"text": text, "first_token_ms": first_token_ms, "total_ms": elapsed,
            "output_tokens": len(tokenizer.encode(text, add_special_tokens=False))}
