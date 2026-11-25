"""Validate a Kaggle Qwen retrieval challenger against its frozen input."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_METHODS = ["bm25", "qwen_dense", "rrf"]


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return round(ordered[round((len(ordered) - 1) * ratio)], 2)


def validate(calibration: dict[str, Any], ranking: dict[str, Any], *, ranking_checksum: str) -> dict[str, Any]:
    if calibration.get("schema") != "ogm-ayt-discovery-calibration-v1":
        raise ValueError("Dondurulmuş Qwen calibration girdisi gerekli")
    if ranking.get("schema") != "ogm-ayt-relation-retrieval-rankings-v1":
        raise ValueError("Qwen sıralama çıktısı şeması desteklenmiyor")
    for field in ("source_checksum", "corpus_checksum"):
        if ranking.get(field) != calibration.get(field):
            raise ValueError(f"{field} calibration girdisiyle uyuşmuyor")
    queries, documents = calibration.get("queries"), calibration.get("documents")
    if not isinstance(queries, list) or not isinstance(documents, list):
        raise TypeError("Calibration sorgu ve doküman listeleri gerekli")
    query_ids, document_ids = {row.get("id") for row in queries}, {row.get("id") for row in documents}
    if len(query_ids) != 24 or len(document_ids) != 3011 or None in query_ids or None in document_ids:
        raise ValueError("Dondurulmuş 24 sorgu ve 3011 atom gerekli")
    if ranking.get("query_count") != len(query_ids) or ranking.get("document_count") != len(document_ids):
        raise ValueError("Sıralama sorgu/doküman sayısı calibration ile uyuşmuyor")
    if ranking.get("ranking_methods") != EXPECTED_METHODS:
        raise ValueError("Sadece BM25, Qwen dense ve RRF karşılaştırması kabul edilir")
    top_k = ranking.get("top_k")
    if not isinstance(top_k, int) or top_k < 3:
        raise ValueError("Top-k en az üç olmalı")
    rankings = ranking.get("rankings")
    if not isinstance(rankings, dict) or set(rankings) != query_ids:
        raise ValueError("Sıralamalar dondurulmuş sorgu kümesini tam kapsamalı")
    for query_id, by_method in rankings.items():
        if not isinstance(by_method, dict) or set(by_method) != set(EXPECTED_METHODS):
            raise ValueError(f"{query_id} yöntem kümesi geçersiz")
        for method in EXPECTED_METHODS:
            ranked_ids = by_method[method]
            if not isinstance(ranked_ids, list) or len(ranked_ids) != top_k or len(set(ranked_ids)) != top_k:
                raise ValueError(f"{query_id}/{method} tekil top-k adayları taşımalı")
            if not set(ranked_ids) <= document_ids:
                raise ValueError(f"{query_id}/{method} corpus dışında atom taşıyor")
    latencies = ranking.get("latencies_by_method_ms")
    if not isinstance(latencies, dict):
        raise TypeError("Yöntem gecikmeleri gerekli")
    latency_summary = {}
    for method in EXPECTED_METHODS:
        values = latencies.get(method)
        if not isinstance(values, list) or len(values) != len(query_ids) or any(not isinstance(value, (int, float)) or value < 0 for value in values):
            raise ValueError(f"{method} için her sorguda geçerli gecikme gerekli")
        numeric = [float(value) for value in values]
        latency_summary[method] = {"p50_ms": _percentile(numeric, 0.5), "p95_ms": _percentile(numeric, 0.95)}
    return {
        "schema": "ayt-history-qwen-calibration-validation-v1",
        "ranking_file_checksum": ranking_checksum,
        "source_checksum": ranking["source_checksum"],
        "corpus_checksum": ranking["corpus_checksum"],
        "query_count": len(query_ids), "document_count": len(document_ids),
        "ranking_methods": EXPECTED_METHODS, "top_k": top_k,
        "embedding_model": ranking.get("embedding_model"), "gpu": ranking.get("gpu"),
        "latency_summary_ms": latency_summary,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Structural validation only. Retrieval quality requires rank-blind PDF evidence review before a product decision.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ranking = json.loads(args.ranking.read_text(encoding="utf-8"))
    result = validate(json.loads(args.calibration.read_text(encoding="utf-8")), ranking,
                      ranking_checksum=_file_checksum(args.ranking))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
