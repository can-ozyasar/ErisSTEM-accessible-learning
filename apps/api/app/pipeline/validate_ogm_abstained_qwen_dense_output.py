"""Fail closed on a Kaggle dense-retrieval result before evidence review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(input_data: dict, result: dict) -> dict:
    if input_data.get("schema") != "ogm-ayt-discovery-calibration-v1":
        raise ValueError("cevap-anahtarı kapalı dense girdi gerekli")
    if result.get("schema") != "ogm-ayt-relation-retrieval-rankings-v1":
        raise ValueError("Qwen retrieval sonuç şeması geçersiz")
    for field in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
        if input_data.get(field) is not False or result.get(field) is not False:
            raise ValueError(f"{field} false olmalı")
    if result.get("source_checksum") != input_data.get("source_checksum") or result.get("corpus_checksum") != input_data.get("corpus_checksum"):
        raise ValueError("sorgu veya corpus checksum uyuşmazlığı")
    if result.get("embedding_model") != "Qwen/Qwen3-Embedding-4B":
        raise ValueError("yalnız dondurulmuş Qwen3-Embedding-4B sonucu kabul edilir")
    expected_queries = {row["id"] for row in input_data.get("queries", [])}
    document_ids = {row["id"] for row in input_data.get("documents", [])}
    rankings = result.get("rankings")
    if not isinstance(rankings, dict) or set(rankings) != expected_queries:
        raise ValueError("sonuç sıralamaları 84 sorguyu tam ve yalnız bir kez kapsamalı")
    required_methods = {"bm25", "qwen_dense", "rrf"}
    if not required_methods <= set(result.get("ranking_methods", [])):
        raise ValueError("BM25, dense ve RRF karşılaştırması eksik")
    top_k = result.get("top_k")
    if not isinstance(top_k, int) or top_k < 12:
        raise ValueError("en az top-12 aday gerekli")
    for identifier, methods in rankings.items():
        if not required_methods <= set(methods):
            raise ValueError(f"sorguda yöntem eksik: {identifier}")
        for method in required_methods:
            ids = methods[method]
            if len(ids) < 12 or len(set(ids[:12])) != 12 or not set(ids[:12]) <= document_ids:
                raise ValueError(f"geçersiz {method} aday sıralaması: {identifier}")
    latencies = result.get("latencies_by_method_ms", {})
    if any(not isinstance(latencies.get(method), list) or len(latencies[method]) != len(expected_queries)
           for method in required_methods):
        raise ValueError("yöntem gecikmeleri tüm sorgular için kaydedilmeli")
    def percentile(values: list[float], p: float) -> float:
        ordered = sorted(float(value) for value in values)
        return ordered[round((len(ordered) - 1) * p)]
    return {"valid": True, "query_count": len(expected_queries), "document_count": len(document_ids),
            "model": result["embedding_model"], "gpu": result.get("gpu"),
            "p50_ms": {method: round(percentile(latencies[method], .5), 3) for method in required_methods},
            "p95_ms": {method: round(percentile(latencies[method], .95), 3) for method in required_methods},
            "runtime_enabled": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True); parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(); load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(validate(load(args.input), load(args.result)), ensure_ascii=False))


if __name__ == "__main__": main()
