"""Export the abstained OGM queue as answer-free Qwen dense retrieval input."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .prepare_ogm_real_question_evidence_queue import _documents


def build(queue: dict, corpus: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("OGM kanıt kuyruğu gerekli")
    if queue.get("retrieval", {}).get("answer_key_used") is not False:
        raise ValueError("cevap anahtarı erişimli kuyruk kullanılamaz")
    if corpus.get("schema") != "multi-history-rag-v1" or queue.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("checksum bağlı MEB corpus gerekli")
    queries = [{"id": row["candidate_id"], "query": row["question_text"], "question_source": "ogm_abstained_answer_blind"}
               for row in queue.get("proposals", [])]
    if not queries or len({row["id"] for row in queries}) != len(queries):
        raise ValueError("benzersiz, boş olmayan sorgular gerekli")
    documents = _documents(corpus)
    return {"schema": "ogm-ayt-discovery-calibration-v1", "source_checksum": queue["question_source_checksum"],
            "corpus_checksum": corpus["corpus_checksum"], "queries": queries,
            "documents": [{"id": row["id"], "search_text": row["text"]} for row in documents],
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private answer-free Qwen dense retrieval input for previously abstained OGM questions only."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True); parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.queue), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "documents": len(result["documents"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
