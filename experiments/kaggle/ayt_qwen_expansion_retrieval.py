"""Private Qwen dense retrieval expansion for source-bound AYT coaching."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-ayt-qwen-expansion-v1/input.json")
OUTPUT = Path("/kaggle/working/ayt-qwen-expansion-rankings-v1.json")
MODEL = "Qwen/Qwen3-Embedding-4B"
INSTRUCTION = "Given a Turkish high-school history exam question, retrieve textbook passages that directly support answering the question."
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)


def _tokens(value: str) -> list[str]:
    return TOKENS.findall(value.translate(str.maketrans("Iİ", "ıi")).casefold())


def _rank(scores, documents: list[dict]) -> list[str]:
    return [documents[index]["id"] for index in sorted(range(len(documents)), key=lambda index: (-float(scores[index]), documents[index]["id"]))]


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if data.get("schema") != "ogm-ayt-discovery-calibration-v1" or FORBIDDEN & set(data):
        raise ValueError("Yanıt ve PDF içermeyen private retrieval girdisi gerekli")
    if any(FORBIDDEN & set(row) for group in (data.get("queries", []), data.get("documents", [])) for row in group):
        raise ValueError("Retrieval satırında yasaklı alan var")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "sentence-transformers>=5", "rank-bm25"], check=True)
    import numpy as np
    import torch
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer

    documents, queries = data["documents"], data["queries"]
    texts = [item["search_text"] for item in documents]
    bm25 = BM25Okapi([_tokens(text) for text in texts])
    model = SentenceTransformer(MODEL, device="cuda", model_kwargs={"torch_dtype": torch.float16})
    model.max_seq_length = 2048
    vectors = model.encode(texts, batch_size=2, normalize_embeddings=True, show_progress_bar=True)
    rankings, timings = {}, {"bm25": [], "qwen_dense_en": []}
    for query in queries:
        started = time.perf_counter(); rankings[query["id"]] = {"bm25": _rank(bm25.get_scores(_tokens(query["query"])), documents)[:24]}; timings["bm25"].append((time.perf_counter() - started) * 1000)
        started = time.perf_counter(); vector = model.encode([f"Instruct: {INSTRUCTION}\nQuery: {query['query']}"], normalize_embeddings=True, show_progress_bar=False)[0]
        rankings[query["id"]]["qwen_dense_en"] = _rank(np.asarray(vectors) @ np.asarray(vector), documents)[:24]; timings["qwen_dense_en"].append((time.perf_counter() - started) * 1000)
    OUTPUT.write_text(json.dumps({"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": data["source_checksum"], "corpus_checksum": data["corpus_checksum"], "embedding_model": MODEL, "instructions": {"qwen_dense_en": INSTRUCTION}, "document_count": len(documents), "query_count": len(queries), "top_k": 24, "ranking_methods": ["bm25", "qwen_dense_en"], "rankings": rankings, "latencies_by_method_ms": timings, "gpu": torch.cuda.get_device_name(0), "runtime_enabled": False, "qlora_enabled": False, "notice": "Candidate rankings only; no answers, PDFs, source approval, runtime or QLoRA data."}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
