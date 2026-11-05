"""Private Kaggle A/B test for Qwen3 embedding instructions on Turkish history."""
from __future__ import annotations

import gc
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DATASET_HANDLE = "muhammedcanozyasar/eristem-ayt-relation-discovery-calibration-v1"
INPUT = Path(os.environ.get(
    "AYT_DISCOVERY_INPUT",
    "/kaggle/input/datasets/muhammedcanozyasar/eristem-ayt-relation-discovery-calibration-v1/"
    "qlora-relation-discovery-calibration-v1.json",
))
OUTPUT = Path(os.environ.get("AYT_DISCOVERY_OUTPUT", "/kaggle/working/ayt-qwen-instruction-rankings-v1.json"))
MODEL_ID = "Qwen/Qwen3-Embedding-4B"
TOP_K = 24
MAX_LENGTH = 2048
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
INSTRUCTIONS = {
    "qwen_dense_en": (
        "Given a Turkish high-school history exam question, retrieve textbook passages "
        "that directly support answering the question."
    ),
    "qwen_dense_tr": (
        "Verilen lise düzeyi tarih sorusunu cevaplamayı doğrudan destekleyen ders kitabı "
        "parçalarını getir."
    ),
}


def tokens(value: str) -> list[str]:
    return TOKENS.findall(value.translate(str.maketrans("Iİ", "ıi")).casefold())


def _assert_private_calibration(data: dict) -> None:
    if data.get("schema") != "ogm-ayt-discovery-calibration-v1":
        raise ValueError("Private AYT relation-discovery calibration input required")
    if FORBIDDEN & set(data):
        raise ValueError("Forbidden answer or PDF material in calibration input")
    for group in (data.get("queries", []), data.get("documents", [])):
        if any(FORBIDDEN & set(item) for item in group):
            raise ValueError("Forbidden material in calibration rows")
    if not data.get("queries") or not data.get("documents"):
        raise ValueError("Queries and documents are required")


def _ensure_dependencies() -> None:
    try:
        import rank_bm25  # noqa: F401
        import sentence_transformers  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "sentence-transformers>=5", "transformers>=4.51", "rank-bm25"],
            check=True,
        )


def _rank_ids(scores, documents: list[dict]) -> list[str]:
    return [documents[index]["id"] for index in sorted(
        range(len(documents)), key=lambda index: (-float(scores[index]), documents[index]["id"])
    )]


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    _assert_private_calibration(data)
    _ensure_dependencies()
    import numpy as np
    import torch
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer

    documents, queries = data["documents"], data["queries"]
    corpus_text = [item["search_text"] for item in documents]
    bm25 = BM25Okapi([tokens(text) for text in corpus_text])
    model = SentenceTransformer(
        MODEL_ID,
        device="cuda" if torch.cuda.is_available() else "cpu",
        model_kwargs={"torch_dtype": torch.float16} if torch.cuda.is_available() else {},
    )
    model.max_seq_length = MAX_LENGTH
    dense_documents = model.encode(corpus_text, batch_size=2, show_progress_bar=True, normalize_embeddings=True)
    rankings = {}
    timings = {name: [] for name in ("bm25", *INSTRUCTIONS)}
    for query in queries:
        text = query["query"]
        started = time.perf_counter()
        rankings[query["id"]] = {"bm25": _rank_ids(bm25.get_scores(tokens(text)), documents)[:TOP_K]}
        timings["bm25"].append((time.perf_counter() - started) * 1000)
        for method, instruction in INSTRUCTIONS.items():
            started = time.perf_counter()
            vector = model.encode(
                [f"Instruct: {instruction}\nQuery: {text}"],
                batch_size=1, show_progress_bar=False, normalize_embeddings=True,
            )
            rankings[query["id"]][method] = _rank_ids(np.asarray(dense_documents) @ np.asarray(vector)[0], documents)[:TOP_K]
            timings[method].append((time.perf_counter() - started) * 1000)
    model.cpu()
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    OUTPUT.write_text(json.dumps({
        "schema": "ogm-ayt-relation-retrieval-rankings-v1",
        "source_checksum": data["source_checksum"], "corpus_checksum": data["corpus_checksum"],
        "embedding_model": MODEL_ID, "instructions": INSTRUCTIONS, "max_length": MAX_LENGTH,
        "document_count": len(documents), "query_count": len(queries), "top_k": TOP_K,
        "ranking_methods": ["bm25", *INSTRUCTIONS], "rankings": rankings,
        "latencies_by_method_ms": timings,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Candidate rankings only; private instruction ablation with no answers, PDFs or sealed test.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
