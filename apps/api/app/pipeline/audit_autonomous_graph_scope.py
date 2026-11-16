"""Audit source-bound generated questions inside the locked AYT pilot scope.

The report is private. Mechanical acceptance is not historical or pedagogical
approval, and this command never exports QLoRA examples.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..ayt_autonomy import GeneratedDraftQualityGate, GraphToQuestionGenerator
from ..ayt_knowledge_graph import KnowledgeGraph


def audit(graph_payload: dict, scope: dict) -> dict:
    graph = KnowledgeGraph.model_validate({
        key: graph_payload[key] for key in ("schema", "corpus_checksum", "nodes", "edges")
    })
    binding = scope["source_binding"]
    if graph.corpus_checksum != binding["corpus_checksum"]:
        raise ValueError("Kapsam manifesti ile graf corpus checksum'ı uyuşmuyor")
    ranges = [(row["book_page_range"]["start"], row["book_page_range"]["end"])
              for row in scope["sections"]]
    drafts = GraphToQuestionGenerator(
        graph, source_checksum=binding["meb_source_checksum"], page_ranges=ranges,
    ).generate(limit=len(graph.edges) or 1)
    reviews = [GeneratedDraftQualityGate().review(draft) for draft in drafts]
    accepted = [draft for draft, review in zip(drafts, reviews) if review.accepted]
    return {
        "schema": "autonomous-graph-scope-audit-v2",
        "corpus_checksum": graph.corpus_checksum,
        "meb_source_checksum": binding["meb_source_checksum"],
        "grade": scope["grade"],
        "target_sections": [row["section_id"] for row in scope["sections"]],
        "target_question_count": scope["target_question_count"],
        "generated_candidate_count": len(drafts),
        "mechanical_pass_count": len(accepted),
        "mechanical_reject_count": len(drafts) - len(accepted),
        "mechanical_issue_counts": dict(sorted(Counter(
            issue for review in reviews for issue in review.issues
        ).items())),
        "pass_relation_counts": dict(sorted(Counter(draft.relation_type for draft in accepted).items())),
        "accepted_for_teacher_review": [
            {"question_id": draft.id, "stem": draft.runtime_question.stem,
             "relation_type": draft.relation_type, "source_ids": draft.source_ids,
             "source_quote": draft.source_quote, "page": draft.page,
             "bbox": draft.bbox,
             "choices": [choice.model_dump(mode="json") for choice in draft.runtime_question.choices]}
            for draft in accepted
        ],
        "production_ready_count": 0,
        "qlora_enabled": False,
        "runtime_enabled": False,
        "notice": "Mechanical pass only. PDF crop, historical accuracy, options and coaching turns need separate review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.graph.read_text(encoding="utf-8")),
                   json.loads(args.scope.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items()
                      if key != "accepted_for_teacher_review"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
