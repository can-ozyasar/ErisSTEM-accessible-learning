"""Compare the local C++ BM25 prototype with the prepared Python baseline.

Writes content-free timings and ranking parity only. Private questions and
source snippets are passed to the child process over local stdin.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from app.history_rag import terms
from app.pipeline.ogm_ayt_evidence_queue import _eligible, _global_index, _query


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return round(ordered[math.ceil(len(ordered) * fraction) - 1], 2)


def compare(transcriptions: dict, corpus: dict) -> dict:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private transcription required")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("MEB corpus required")
    pool = _eligible(corpus)
    if not pool:
        raise ValueError("No eligible source passages")
    questions = [row for row in transcriptions.get("rows", [])
                 if row.get("transcription_status") == "private_teacher_review_required"]
    if not questions:
        raise ValueError("No clean test questions")
    index = _global_index(pool)
    expected, python_ms = [], []
    for row in questions:
        start = time.perf_counter()
        expected.append([item["id"] for item in index.rank(_query(row), limit=3)])
        python_ms.append((time.perf_counter() - start) * 1000)
    lines = [f"{len(index.chunks)} {len(questions)} 3"]
    lines.extend(f'{item["id"]}\t{item["page"]}\t{" ".join(terms(item["text"]))}'
                 for item in index.chunks)
    lines.extend(" ".join(terms(_query(row))) for row in questions)
    source = Path(__file__).with_name("bm25_batch.cpp")
    with tempfile.TemporaryDirectory(prefix="eristem-bm25-") as folder:
        binary = Path(folder) / "bm25_batch"
        compiler = shutil.which("g++")
        if compiler is None:
            raise RuntimeError("C++ compiler unavailable")
        compile_start = time.perf_counter()
        subprocess.run([compiler, "-O2", "-std=c++17", str(source), "-o", str(binary)],
                       check=True, capture_output=True)
        compile_ms = (time.perf_counter() - compile_start) * 1000
        process_start = time.perf_counter()
        output = subprocess.run([str(binary)], input="\n".join(lines) + "\n",
                                text=True, check=True, capture_output=True).stdout.splitlines()
        process_ms = (time.perf_counter() - process_start) * 1000
    observed, cpp_ms = [], []
    for _ in questions:
        count, microseconds = output.pop(0).split("\t")
        observed.append([output.pop(0).split("\t")[0] for _ in range(int(count))])
        cpp_ms.append(int(microseconds) / 1000)
    return {
        "schema": "history-bm25-cpp-parity-v1",
        "corpus_checksum": corpus["corpus_checksum"],
        "question_source_checksum": transcriptions["source_checksum"],
        "question_count": len(questions), "document_count": len(index.chunks),
        "exact_top3_count": sum(a == b for a, b in zip(expected, observed)),
        "python_prepared_p50_ms": round(statistics.median(python_ms), 2),
        "python_prepared_p95_ms": _percentile(python_ms, .95),
        "cpp_core_p50_ms": round(statistics.median(cpp_ms), 2),
        "cpp_core_p95_ms": _percentile(cpp_ms, .95),
        "cpp_batch_process_ms": round(process_ms, 2),
        "cpp_compile_ms": round(compile_ms, 2),
        "runtime_enabled": False,
        "notice": "Experimental parity and timing only; product adoption needs quality labels and deployment costs.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.transcriptions.read_text(encoding="utf-8")),
                     json.loads(args.corpus.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"corpus_checksum", "question_source_checksum", "notice"}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
