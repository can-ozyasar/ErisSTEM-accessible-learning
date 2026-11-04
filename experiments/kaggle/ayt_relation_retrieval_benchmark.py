"""Private Kaggle benchmark for lexical and semantic AYT evidence discovery.

Input is the private ``ogm-ayt-discovery-calibration-v1`` export.  It contains
question transcriptions and MEB candidate text, but never answer labels, answer
keys, worked explanations, PDFs or student data.  This runner produces ranked
candidate IDs only.  A separate PDF-crop review remains the sole way to create
Gold evidence labels.

Kaggle setup (private dataset only):
    pip install -q FlagEmbedding rank-bm25
    python ayt_relation_retrieval_benchmark.py
"""
from __future__ import annotations

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
OUTPUT = Path(os.environ.get("AYT_DISCOVERY_OUTPUT", "/kaggle/working/ayt-relation-retrieval-rankings-v1.json"))
MODEL_ID = os.environ.get("BGE_M3_MODEL", "BAAI/bge-m3")
TOP_K = int(os.environ.get("TOP_K", "24"))
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)


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


def _rrf(*rankings: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + position)
    return sorted(scores, key=lambda item_id: (-scores[item_id], item_id))


def _sparse_score(query: dict, document: dict) -> float:
    # BGE-M3's sparse output is a token-weight mapping.  Computing its overlap
    # here keeps sparse scoring inspectable and makes no relevance claim.
    return sum(float(weight) * float(document.get(token, 0.0))
               for token, weight in query.items() if token in document)


def _rank_ids(scores, documents: list[dict]) -> list[str]:
    return [documents[index]["id"] for index in sorted(
        range(len(documents)), key=lambda index: (-float(scores[index]), documents[index]["id"]))]


def _ensure_dependencies() -> None:
    """Install only the two packages absent from standard Kaggle images."""
    try:
        import FlagEmbedding  # noqa: F401
        import rank_bm25  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "FlagEmbedding", "rank-bm25"], check=True)


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    _assert_private_calibration(data)
    _ensure_dependencies()
    import numpy as np
    import torch
    from FlagEmbedding import BGEM3FlagModel
    from rank_bm25 import BM25Okapi

    documents, queries = data["documents"], data["queries"]
    corpus_text = [item["search_text"] for item in documents]
    bm25 = BM25Okapi([tokens(text) for text in corpus_text])
    model = BGEM3FlagModel(MODEL_ID, use_fp16=torch.cuda.is_available())
    document_vectors = model.encode(corpus_text, batch_size=8, max_length=2048,
                                    return_dense=True, return_sparse=True, return_colbert_vecs=False)
    dense_documents = np.asarray(document_vectors["dense_vecs"])
    sparse_documents = document_vectors["lexical_weights"]
    rankings, timings = {}, {name: [] for name in ("bm25", "bge_dense", "bge_sparse", "rrf")}
    for query in queries:
        text = query["query"]
        started = time.perf_counter()
        lexical = _rank_ids(bm25.get_scores(tokens(text)), documents)
        timings["bm25"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        query_vectors = model.encode([text], batch_size=1, max_length=2048,
                                     return_dense=True, return_sparse=True, return_colbert_vecs=False)
        dense_scores = dense_documents @ np.asarray(query_vectors["dense_vecs"])[0]
        dense = _rank_ids(dense_scores, documents)
        timings["bge_dense"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        sparse_scores = [_sparse_score(query_vectors["lexical_weights"][0], document)
                         for document in sparse_documents]
        sparse = _rank_ids(sparse_scores, documents)
        timings["bge_sparse"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        rrf = _rrf(lexical, dense, sparse)
        timings["rrf"].append((time.perf_counter() - started) * 1000)
        rankings[query["id"]] = {
            "bm25": lexical[:TOP_K], "bge_dense": dense[:TOP_K],
            "bge_sparse": sparse[:TOP_K], "rrf": rrf[:TOP_K],
        }
    OUTPUT.write_text(json.dumps({
        "schema": "ogm-ayt-relation-retrieval-rankings-v1",
        "source_checksum": data["source_checksum"], "corpus_checksum": data["corpus_checksum"],
        "model": MODEL_ID, "document_count": len(documents), "query_count": len(queries),
        "top_k": TOP_K, "rankings": rankings, "latencies_by_method_ms": timings,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Candidate rankings only; they are not approved sources or a runtime retrieval artifact.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
