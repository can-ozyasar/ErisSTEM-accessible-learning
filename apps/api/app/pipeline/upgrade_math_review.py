"""Move existing broken raw-math draft blocks into the formula review lane."""

from __future__ import annotations

import argparse

from ..job_store import DocumentStore, make_session_factory
from .materialize import looks_like_fragmented_math


def upgrade_document(document_id: str) -> int:
    """Preserve teacher-approved work; upgrade only still-unreviewed fragments."""
    documents = DocumentStore(make_session_factory())
    payload = documents.get(document_id)
    if payload is None:
        raise ValueError("document_not_found")
    upgraded = 0
    for block in payload["blocks"]:
        if block["status"] != "review_required" or not looks_like_fragmented_math(block.get("text") or ""):
            continue
        block.update(kind="formula-display", text=None, latex=None, mathml=None, spoken_text=None)
        block["validation"] = {
            "schema_passed": True, "render_score": 0, "source_agreement": 0, "confidence": 0,
            "reasons": ["Bozuk matematiksel PDF parçası; görsel formül tanıma ve öğretmen denetimi gerekli."],
        }
        block["source"]["extraction_step"] = "math-ocr-pending"
        upgraded += 1
    if upgraded:
        documents.save_draft(payload)
        documents.add_audit(document_id, "admin", "fragmented_math_routed", None, f"{upgraded} raw maths blocks routed")
    return upgraded


def main() -> int:
    parser = argparse.ArgumentParser(description="Route broken raw maths to formula review")
    parser.add_argument("--document-id", required=True)
    args = parser.parse_args()
    print(upgrade_document(args.document_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
