"""Small development-only probe; output contains metadata, not source text."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from app.deepseek_exam_coach import hint
from app.exam_practice import AytHistoryExamPack
from app.tutor_coach import CoachContext, coach


def evaluate(pack: dict, split: dict, limit: int = 3) -> dict:
    parsed = AytHistoryExamPack.model_validate(pack)
    if split.get("schema") != "ogm-ayt-source-grounded-research-split-v1" or split.get("source_checksum") != parsed.licensed_question_source_checksum:
        raise ValueError("soru split kaynak checksum uyuşmazlığı")
    if limit < 1 or limit > 13 or not os.getenv("DEEPSEEK_API_KEY"):
        raise ValueError("geliştirme örnek sınırı veya API anahtarı geçersiz")
    questions = {q.id: q for q in parsed.questions}
    eligible = []
    for candidate_id, label in sorted(split["splits"].items()):
        if label != "development":
            continue
        qid = "licensed-" + hashlib.sha256(candidate_id.encode()).hexdigest()[:20]
        if qid in questions:
            eligible.append((candidate_id, questions[qid]))
    if len(eligible) < limit:
        raise ValueError("yeterli geliştirme sorusu yok")
    rows = []
    for identifier, q in eligible[:limit]:
        incorrect = next(choice for idx, choice in enumerate(q.choices) if "ABCDE"[idx] != q.correct_label)
        context = CoachContext(question_id=q.id, question_text=q.question, choice_text=incorrect,
                               section_title=q.topic, source_ids=[e.source_id for e in q.evidence],
                               evidence=q.evidence[0].quote, error_type="genel")
        baseline = coach(context, None, "", False, None, None)
        start = time.perf_counter()
        diagnostic: dict = {}
        candidate = hint(context, "", q.choices["ABCDE".index(q.correct_label)], diagnostic=diagnostic)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        rows.append({"candidate_id": identifier, "baseline_stage": baseline.stage,
                     "baseline_has_question": baseline.student_prompt.endswith("?"),
                     "candidate_accepted_by_guard": candidate is not None, "guard_reason": diagnostic.get("reason", "unknown"), "latency_ms": elapsed,
                     "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest() if candidate else None})
    return {"schema": "deepseek-exam-development-probe-v1", "source_checksum": split["source_checksum"],
            "split": "development", "count": len(rows), "rows": rows,
            "accepted_by_guard": sum(r["candidate_accepted_by_guard"] for r in rows),
            "notice": "Preliminary development-only guard probe; no ground-truth pedagogy, no user data, no sealed-test claim."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True); parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(); load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    result = evaluate(load(args.pack), load(args.split), args.limit)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": result["count"], "accepted_by_guard": result["accepted_by_guard"]}))


if __name__ == "__main__":
    main()
