"""Private Kaggle BM25, BGE-M3 and RRF candidate benchmark.

The input contains short teacher-approved snippets and development labels.
The script never reads sealed test rows, PDFs, or answer labels.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

ROOT = Path("/kaggle/input/history-rag-hybrid-dev-v1")
INPUT = ROOT / "history-rag-hybrid-dev-v1.json"
OUT = Path("/kaggle/working/history-rag-hybrid-report.json")
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "pdf_path", "raw_pdf"}
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)


def tokens(value: str) -> list[str]:
    return TOKENS.findall(value.translate(str.maketrans("Iİ", "ıi")).casefold())


def load() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if data.get("schema") != "history-rag-hybrid-dev-v1" or data.get("split") != "development":
        raise ValueError("Private development schema required")
    if FORBIDDEN & set(data) or any(FORBIDDEN & set(q) for q in data.get("queries", [])):
        raise ValueError("Answer keys, PDFs and sealed data are forbidden")
    return data


def fuse(lexical: list[str], dense: list[str]) -> list[str]:
    scores = {}
    for ids in (lexical, dense):
        for place, item_id in enumerate(ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (60 + place)
    return sorted(scores, key=lambda item_id: (-scores[item_id], item_id))


def main() -> None:
    data = load()
    docs, queries = data["documents"], data["queries"]
    if not docs or not queries:
        raise ValueError("Documents and development queries required")
    import numpy as np
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer

    bm25 = BM25Okapi([tokens(doc["text"]) for doc in docs])
    model_id = data.get("bge_m3_model", "BAAI/bge-m3")
    model = SentenceTransformer(model_id, trust_remote_code=True)
    vectors = model.encode([doc["text"] for doc in docs], normalize_embeddings=True,
                           show_progress_bar=True)
    rankings = {}
    timings = {method: [] for method in ("bm25", "dense", "rrf")}
    for query in queries:
        started = time.perf_counter()
        lexical_scores = bm25.get_scores(tokens(query["query"]))
        lexical = [docs[index]["id"] for index in sorted(
            range(len(docs)), key=lambda index: (-float(lexical_scores[index]), docs[index]["id"]))]
        timings["bm25"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        query_vector = model.encode(query["query"], normalize_embeddings=True)
        similarities = np.asarray(vectors) @ np.asarray(query_vector)
        dense = [docs[index]["id"] for index in sorted(
            range(len(docs)), key=lambda index: (-float(similarities[index]), docs[index]["id"]))]
        timings["dense"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        fused = fuse(lexical, dense)
        timings["rrf"].append(timings["bm25"][-1] + timings["dense"][-1]
                              + (time.perf_counter() - started) * 1000)
        rankings[query["id"]] = {"bm25": lexical[:20], "dense": dense[:20], "rrf": fused[:20]}
    OUT.write_text(json.dumps({
        "schema": "history-rag-hybrid-result-v2",
        "input_source_checksum": data["source_checksum"],
        "input_approval_checksum": data["approval_checksum"],
        "model": model_id, "gpu": os.environ.get("KAGGLE_KERNEL_RUN_TYPE", "unknown"),
        "document_count": len(docs), "query_count": len(queries),
        "rankings": rankings, "latencies_by_method_ms": timings,
    }, ensure_ascii=False), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
