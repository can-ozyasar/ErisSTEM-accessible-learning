"""Fail closed handoff from independent evidence audit to human source review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

QUEUE_SCHEMAS = {"ogm-ayt-evidence-review-queue-v1", "ogm-ayt-evidence-review-queue-v2"}
AUDIT_SCHEMA = "ogm-ayt-claim-coverage-agent-audit-v1"
OUT_SCHEMA = "ogm-ayt-evidence-human-review-queue-v1"
OUTCOMES = {"plausibly_direct", "reretrieve", "abstain"}


def build(queue: dict, audit: dict) -> tuple[dict, dict]:
    """Retain only independently audited direct leads for human PDF approval.

    An agent verdict is deliberately not an approval.  The output is still a
    private teacher queue and keeps runtime/QLoRA disabled until a human checks
    the rendered PDF crop and records an approval separately.
    """
    if queue.get("schema") not in QUEUE_SCHEMAS:
        raise ValueError("Claim-coverage kanıt kuyruğu gerekli")
    if audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("Claim-coverage bağımsız denetimi gerekli")
    if audit.get("source_checksum") != queue.get("source_checksum"):
        raise ValueError("Kanıt kuyruğu ve denetim checksum'ı eşleşmiyor")
    proposed = {row["candidate_id"]: row for row in queue.get("proposals", [])
                if row.get("status") == "teacher_agent_source_review_required"}
    reviews = {row.get("candidate_id"): row for row in audit.get("reviews", [])}
    if set(reviews) != set(proposed):
        raise ValueError("Denetim, claim-coverage adaylarının tamamını ve yalnız onları içermeli")
    if any(row.get("outcome") not in OUTCOMES for row in reviews.values()):
        raise ValueError("Geçersiz kanıt denetimi sonucu")
    if any(row.get("source_approval") is not False for row in reviews.values()):
        raise ValueError("Agent kanıt onayı veremez")

    human, reretrieve, abstain = [], [], []
    for candidate_id, proposal in proposed.items():
        outcome = reviews[candidate_id]["outcome"]
        if outcome == "plausibly_direct":
            # The audit identifies the first candidate as the inspected lead;
            # do not expose lower-ranked generic context as review evidence.
            human.append({**proposal, "status": "teacher_human_source_approval_required",
                          "suggestions": proposal["suggestions"][:1]})
        elif outcome == "reretrieve":
            reretrieve.append({"candidate_id": candidate_id, "topic": proposal.get("topic"),
                               "reason": "agent_requires_subject_relation_object_reretrieval"})
        else:
            abstain.append({"candidate_id": candidate_id, "topic": proposal.get("topic"),
                            "reason": "agent_found_no_safe_direct_evidence"})
    content = {
        "schema": OUT_SCHEMA,
        "source_checksum": queue["source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "proposals": human,
        "notice": ("Private human-review queue. Independent agent verdicts are not source approvals; "
                   "runtime and QLoRA remain disabled."),
    }
    report = {
        "schema": "ogm-ayt-evidence-semantic-gate-report-v1",
        "input_claim_coverage_lead_count": len(proposed),
        "human_review_lead_count": len(human),
        "reretrieve_count": len(reretrieve),
        "abstain_count": len(abstain),
        "reretrieve_queue": reretrieve,
        "abstain_queue": abstain,
        "runtime_enabled": False,
        "qlora_enabled": False,
    }
    return content, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    content, report = build(json.loads(args.queue.read_text(encoding="utf-8")),
                            json.loads(args.audit.read_text(encoding="utf-8")))
    for target, body in ((args.output, content), (args.report_output, report)):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
