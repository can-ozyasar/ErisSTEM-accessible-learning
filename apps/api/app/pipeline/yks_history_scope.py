"""Build a private, metadata-only YKS History scope decision report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..yks_selection import ExamTag, rank_scope

FORBIDDEN = {"question_text", "choices", "answer", "answer_key", "correct_choice", "pdf", "source_url"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Private, reviewed metadata JSON")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body = json.loads(args.input.read_text(encoding="utf-8"))
    if body.get("schema") != "yks-history-metadata-v1" or not isinstance(body.get("items"), list):
        raise ValueError("yks-history-metadata-v1 şeması gerekli")
    if FORBIDDEN & set(body):
        raise ValueError("Ham soru veya cevap anahtarı dışa aktarılamaz")
    tags = []
    for row in body["items"]:
        if FORBIDDEN & set(row):
            raise ValueError("Soru satırı ham soru veya cevap anahtarı içeremez")
        tags.append(ExamTag(**row))
    result = rank_scope(tags)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "yks-history-scope-report-v1", **result}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
