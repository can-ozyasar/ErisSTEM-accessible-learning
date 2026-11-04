"""Create a content-free, question-group split before AYT evidence review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "ogm-ayt-qlora-staging-split-v1"


def _stable(ids: list[str]) -> list[str]:
    return sorted(ids, key=lambda item: hashlib.sha256(item.encode("utf-8")).hexdigest())


def build(pool: dict, seen_ids: set[str] | None = None) -> dict:
    if pool.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private AYT OCR hazırlık havuzu gerekli")
    ids = [row.get("candidate_id") for row in pool.get("rows", [])]
    if len(ids) != 120 or any(not isinstance(item, str) for item in ids) or len(set(ids)) != 120:
        raise ValueError("Bölme için tam 120 benzersiz soru kimliği gerekli")
    seen_ids = seen_ids or set()
    unseen = [item for item in ids if item not in seen_ids]
    if len(unseen) < 18:
        raise ValueError("Kapalı test için en az 18 daha önce görülmemiş soru gerekli")
    sealed = set(_stable(unseen)[:18])
    remaining = _stable([item for item in ids if item not in sealed])
    splits = {item: "train" if position < 84 else "dev" for position, item in enumerate(remaining)}
    splits.update({item: "sealed_test" for item in sealed})
    return {"schema": SCHEMA, "source_checksum": pool["source_checksum"], "question_count": 120,
            "splits": splits, "split_counts": {name: list(splits.values()).count(name)
                                                    for name in ("train", "dev", "sealed_test")},
            "retrieval_development_seen_count": len(set(ids) & seen_ids),
            "sealed_test_seen_count": sum(item in seen_ids for item in sealed),
            "answer_key_accessed": False, "source_approved_count": 0,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Question-group split only. It contains no question text or source evidence and does not authorize training."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--seen", type=Path, help="Önceki retrieval geliştirme soru kimliklerini taşıyan private kuyruk")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seen_payload = json.loads(args.seen.read_text(encoding="utf-8")) if args.seen else {}
    seen_ids = {row["candidate_id"] for key in ("proposals", "rows", "candidates")
                for row in seen_payload.get(key, []) if isinstance(row.get("candidate_id"), str)}
    report = build(json.loads(args.pool.read_text(encoding="utf-8")), seen_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["split_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
