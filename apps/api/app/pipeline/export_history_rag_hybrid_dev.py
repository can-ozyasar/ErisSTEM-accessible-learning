"""Export only reviewed short evidence for private Kaggle retrieval experiments.

It intentionally excludes answer labels, PDFs and the sealed split.  The
companion sealed file remains local and is never copied to Kaggle.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ..history_rag import load_index
from ..history_rag_hybrid import approval_checksum
from ..job_store import make_session_factory
from ..learning_operations import LearningOperationsStore
from ..question_bank_structure import Question
from ..tutor_dataset import split_question_ids


def write_json(path: Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


def build_export(store: LearningOperationsStore, module_id: str, index: dict) -> tuple[dict, dict]:
    """Return Kaggle-safe train/dev material and a local sealed set."""
    questions = {row["question"]["id"]: Question.model_validate(row["question"])
                 for row in store.list("qb", module_id) if row["question"].get("status") == "approved"}
    approvals = {row["chunk_id"] for row in store.list("rag", index["source_checksum"][:16])
                 if row.get("approved") and row.get("quality_checked") and row.get("source_checksum") == index["source_checksum"]}
    reviews = [row for row in store.list("rag_evidence_review", module_id)
               if row.get("approved") and row.get("evidence_quality") == "direct"
               and not row.get("visual_dependency") and row.get("source_checksum") == index["source_checksum"]]
    reviewed = {row["question_id"]: row for row in reviews if row["question_id"] in questions and set(row["source_ids"]) <= approvals}
    if len(reviewed) != 120:
        raise ValueError("Kaggle retrieval dışa aktarımı için doğrudan kanıtı onaylı tam 120 soru gerekir")
    splits = split_question_ids(reviewed)
    chunks = {row["id"]: row for row in index["chunks"]}
    used_ids = sorted({source_id for review in reviewed.values() for source_id in review["source_ids"]})
    documents = [{"id": source_id, "section_id": chunks[source_id]["section_id"], "text": chunks[source_id]["text"][:1200]}
                 for source_id in used_ids]
    output = {"train": [], "development": [], "sealed_test": []}
    for question_id, review in sorted(reviewed.items()):
        question = questions[question_id]
        # `Question.model_dump` includes answer metadata; construct the query
        # explicitly to make an accidental answer-key export impossible.
        query = " ".join([*(part.text for part in question.parts), *(choice.text for choice in question.choices)])
        item = {"id": question_id, "section_id": chunks[review["source_ids"][0]]["section_id"],
                "query": query, "gold_source_ids": review["source_ids"], "abstain": False}
        output[splits[question_id]].append(item)
    base = {"schema": "history-rag-hybrid-dev-v1", "source_checksum": index["source_checksum"],
            "approval_checksum": approval_checksum(index["source_checksum"], approvals), "documents": documents}
    kaggle = {**base, "split": "development", "queries": output["development"],
              "notice": "Short approved evidence only; no PDF, answer key or sealed rows."}
    local = {**base, "splits": output}
    return kaggle, local


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///eristem-dev.db"))
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--kaggle-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    args = parser.parse_args()
    store = LearningOperationsStore(make_session_factory(args.database_url))
    kaggle, local = build_export(store, args.module_id, load_index())
    write_json(args.kaggle_output, kaggle)
    write_json(args.sealed_output, local)
    print(json.dumps({"development_queries": len(kaggle["queries"]), "documents": len(kaggle["documents"]),
                      "sealed_output": str(args.sealed_output)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
