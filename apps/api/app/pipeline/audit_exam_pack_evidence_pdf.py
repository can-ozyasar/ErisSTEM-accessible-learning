"""Audit exam evidence against the text layer of checksum-bound PDF crops."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

from app.exam_practice import AytHistoryExamPack, verify_pack_sources


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", re.sub(r"\u00ad\s*", "", text).casefold(), flags=re.UNICODE)


def audit(payload: dict, root: Path, threshold: float = .9) -> dict:
    if not 0 < threshold <= 1:
        raise ValueError("eşik 0 ile 1 arasında olmalı")
    pack = AytHistoryExamPack.model_validate(payload)
    verify_pack_sources(pack, root)
    docs: dict[str, pymupdf.Document] = {}
    rows = []
    try:
        for source in pack.sources:
            docs[source.id] = pymupdf.open(root / source.relative_path)
        for question in pack.questions:
            for evidence in question.evidence:
                page = docs[evidence.source_id][evidence.page - 1]
                rect = pymupdf.Rect(evidence.bbox)
                words = " ".join(w[4] for w in page.get_text("words") if pymupdf.Rect(w[:4]).intersects(rect))
                expected, actual = Counter(_tokens(evidence.quote)), Counter(_tokens(words))
                count = sum(expected.values())
                recall = sum((expected & actual).values()) / count if count else 0.0
                rows.append({"question_id": question.id, "source_id": evidence.source_id,
                             "source_checksum": evidence.source_checksum, "page": evidence.page,
                             "bbox": list(evidence.bbox), "quote_sha256": hashlib.sha256(evidence.quote.encode()).hexdigest(),
                             "token_recall": round(recall, 4), "requires_review": recall < threshold})
    finally:
        for doc in docs.values():
            doc.close()
    return {"schema": "exam-pack-evidence-pdf-audit-v1", "pack_id": pack.pack_id,
            "pack_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "question_count": len(pack.questions), "evidence_count": len(rows), "threshold": threshold,
            "requires_review_count": sum(row["requires_review"] for row in rows), "evidence": rows,
            "notice": "Text-layer token agreement is a screening signal, not visual or historical verification."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.pack.read_text(encoding="utf-8")), args.source_root)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("question_count", "evidence_count", "requires_review_count")}))


if __name__ == "__main__":
    main()
