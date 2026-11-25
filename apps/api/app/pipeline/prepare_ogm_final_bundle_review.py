"""Prepare answer-blind review of the exact bundles selected for the pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build(pack: dict, candidates: dict, queue: dict) -> dict:
    if pack.get("content_mode") != "ai_source_reviewed_local_pilot":
        raise ValueError("AI kaynak incelemeli pilot paketi gerekli")
    if candidates.get("schema") != "ogm-ayt-history-source-grounded-pilot-candidates-v1" or candidates.get("runtime_enabled") is not False:
        raise ValueError("çalışma zamanına kapalı aday paketi gerekli")
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("soru kaynak inceleme kuyruğu gerekli")
    checksum = candidates.get("source_checksum")
    if not checksum or checksum != queue.get("question_source_checksum") or checksum != pack.get("licensed_question_source_checksum"):
        raise ValueError("soru kaynak checksum uyuşmazlığı")
    by_id = {row["candidate_id"]: row for row in queue["proposals"]}
    pilot = {row["id"]: row for row in pack["questions"] if row.get("authorship") == "ai_source_reviewed_local_pilot"}
    proposals = []
    seen = set()
    for candidate in candidates["questions"]:
        identifier = candidate["candidate_id"]
        pid = "ai-reviewed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20]
        if identifier in seen or identifier not in by_id or pid not in pilot:
            raise ValueError("aday kimliği yineleniyor veya paketle eşleşmiyor")
        seen.add(identifier)
        original = by_id[identifier]
        suggestions = candidate.get("evidence_bundle", [])
        if not 1 <= len(suggestions) <= 3 or len({item["id"] for item in suggestions}) != len(suggestions):
            raise ValueError("son kanıt demeti 1–3 benzersiz parça içermeli")
        source_by_id = {row["id"]: row for row in original["suggestions"]}
        for item in suggestions:
            source = source_by_id.get(item["id"])
            if source is None or any(item[key] != source.get(key) for key in ("source_name", "source_checksum", "page", "bbox", "excerpt")):
                raise ValueError("kanıt parçası kaynak kuyruğuyla eşleşmiyor")
        runtime_evidence = pilot[pid]["evidence"]
        expected = [(item["source_name"], item["source_checksum"], item["page"], item["bbox"], item["excerpt"]) for item in suggestions]
        actual = [(item["source_id"], item["source_checksum"], item["page"], item["bbox"], item["quote"]) for item in runtime_evidence]
        if expected != actual:
            raise ValueError("son kanıt demeti aktif pilot paketiyle eşleşmiyor")
        question = pilot[pid]
        choices = question.get("choices", [])
        if len(choices) != 5 or not all(isinstance(choice, str) and choice.strip() for choice in choices):
            raise ValueError("pilot sorusunda beş dolu şık gerekli")
        question_text = question["question"] + "\n" + "\n".join(
            f"{label}) {choice}" for label, choice in zip("ABCDE", choices, strict=True)
        )
        proposals.append({"candidate_id": identifier, "question_text": question_text, "suggestions": suggestions})
    if len(proposals) != len(pilot) or candidates.get("candidate_count") != len(proposals):
        raise ValueError("aday ve pilot soru sayıları eşleşmiyor")
    return {"schema": "ogm-ayt-real-question-evidence-queue-v1", "question_source_checksum": checksum,
            "corpus_checksum": queue["corpus_checksum"], "question_count": len(proposals), "proposals": proposals,
            "answer_key_accessed": False, "runtime_enabled": False,
            "notice": "Exact final bundles for AI source review; neither teacher approval nor runtime authorization."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pack), load(args.candidates), load(args.queue))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": result["question_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
