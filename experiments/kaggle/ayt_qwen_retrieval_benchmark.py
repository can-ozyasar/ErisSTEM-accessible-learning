"""Private Kaggle quality challenger for AYT evidence retrieval.

This runner is intentionally separate from the BGE benchmark.  Qwen's 4B
embedding and 4B reranker are loaded sequentially on a T4: document vectors
and query vectors are retained, then the embedding model is released before
the cross encoder loads.  The run exports candidate IDs only.
"""
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
OUTPUT = Path(os.environ.get("AYT_DISCOVERY_OUTPUT", "/kaggle/working/ayt-qwen-retrieval-rankings-v1.json"))
EMBEDDING_MODEL_ID = os.environ.get("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B")
RERANKER_MODEL_ID = os.environ.get("QWEN_RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B")
TOP_K = int(os.environ.get("TOP_K", "24"))
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "32"))
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "2048"))
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
QUERY_INSTRUCTION = (
    "Given a Turkish high-school history exam question, retrieve textbook passages "
    "that directly support answering the question."
)
RERANK_INSTRUCTION = (
    "Given a Turkish high-school history exam question, determine whether the textbook "
    "passage directly supports answering the question."
)


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


def _load_embedding(model_id: str, torch):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        model_id,
        device="cuda" if torch.cuda.is_available() else "cpu",
        model_kwargs={"torch_dtype": torch.float16} if torch.cuda.is_available() else {},
    )
    model.max_seq_length = MAX_LENGTH
    return model


def _load_reranker(model_id: str, torch):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        model_id,
        device="cuda" if torch.cuda.is_available() else "cpu",
        model_kwargs={"torch_dtype": torch.float16} if torch.cuda.is_available() else {},
        max_length=MAX_LENGTH,
        prompts={"history_evidence": RERANK_INSTRUCTION},
        default_prompt_name="history_evidence",
    )


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    _assert_private_calibration(data)
    _ensure_dependencies()
    import numpy as np
    import torch
    from rank_bm25 import BM25Okapi

    documents, queries = data["documents"], data["queries"]
    documents_by_id = {item["id"]: item for item in documents}
    corpus_text = [item["search_text"] for item in documents]
    bm25 = BM25Okapi([tokens(text) for text in corpus_text])

    embedding = _load_embedding(EMBEDDING_MODEL_ID, torch)
    dense_documents = embedding.encode(
        corpus_text, batch_size=2, show_progress_bar=True, normalize_embeddings=True,
    )
    dense_queries = embedding.encode(
        [f"Instruct: {QUERY_INSTRUCTION}\nQuery: {item['query']}" for item in queries],
        batch_size=1, show_progress_bar=True, normalize_embeddings=True,
    )
    embedding.cpu()
    del embedding
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    reranker = _load_reranker(RERANKER_MODEL_ID, torch)
    rankings, timings = {}, {name: [] for name in ("bm25", "qwen_dense", "qwen_dense_rerank")}
    for query_index, query in enumerate(queries):
        text = query["query"]
        started = time.perf_counter()
        lexical = _rank_ids(bm25.get_scores(tokens(text)), documents)
        timings["bm25"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        dense = _rank_ids(np.asarray(dense_documents) @ np.asarray(dense_queries)[query_index], documents)
        timings["qwen_dense"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        candidate_ids = dense[:RERANK_CANDIDATES]
        pair_scores = reranker.predict(
            [(text, documents_by_id[candidate_id]["search_text"]) for candidate_id in candidate_ids],
            batch_size=1,
            show_progress_bar=False,
        )
        if len(pair_scores) != len(candidate_ids):
            raise RuntimeError("Qwen reranker skor sayısı aday penceresiyle eşleşmiyor")
        reranked = [item_id for _, item_id in sorted(
            zip(pair_scores, candidate_ids, strict=True), key=lambda pair: (-float(pair[0]), pair[1])
        )]
        timings["qwen_dense_rerank"].append((time.perf_counter() - started) * 1000)
        rankings[query["id"]] = {
            "bm25": lexical[:TOP_K], "qwen_dense": dense[:TOP_K], "qwen_dense_rerank": reranked[:TOP_K],
        }

    OUTPUT.write_text(json.dumps({
        "schema": "ogm-ayt-relation-retrieval-rankings-v1",
        "source_checksum": data["source_checksum"], "corpus_checksum": data["corpus_checksum"],
        "embedding_model": EMBEDDING_MODEL_ID, "reranker_model": RERANKER_MODEL_ID,
        "query_instruction": QUERY_INSTRUCTION, "rerank_candidates": RERANK_CANDIDATES,
        "document_count": len(documents), "query_count": len(queries), "top_k": TOP_K,
        "ranking_methods": ["bm25", "qwen_dense", "qwen_dense_rerank"],
        "rankings": rankings, "latencies_by_method_ms": timings,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Candidate rankings only; they are not approved sources or a runtime retrieval artifact.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
