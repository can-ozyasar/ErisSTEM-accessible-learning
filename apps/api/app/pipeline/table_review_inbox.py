"""Convert private vector/native results into strict teacher-review envelopes.

This adapter accepts no visual-model result. It deliberately preserves the
source checksum/page/bbox for server-side binding while keeping raw extraction
artefacts out of the browser projection.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..table_review import VectorNativeTableIngress

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")
_CANDIDATE_STATUS = "candidate-vector-native-needs-gold-and-review"


def to_review_inbox(results: list[dict], document_id: str) -> list[dict]:
    """Return only reviewable vector/native candidates in the API's strict shape."""
    inbox = []
    for result in results:
        if result.get("status") != _CANDIDATE_STATUS or not isinstance(result.get("draft"), dict):
            continue
        draft = result["draft"]
        source = draft.get("source")
        if not isinstance(source, dict):
            continue
        region = source.get("region_id")
        checksum = source.get("source_checksum")
        if not isinstance(region, str) or not isinstance(checksum, str):
            continue
        safe_region = _SAFE_ID.sub("-", region).strip("-")
        payload = {
            "id": f"vector-native-{checksum[:16]}-{safe_region}",
            "document_id": document_id,
            "schema_version": draft.get("schema_version"),
            "kind": draft.get("kind"),
            "source": source,
            "cells": draft.get("cells"),
            "confidence": draft.get("confidence"),
            "publication_status": draft.get("publication_status"),
            "candidate_status": result.get("status"),
        }
        inbox.append(VectorNativeTableIngress.model_validate(payload).model_dump(mode="json"))
    return inbox


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare private vector/native table teacher-review inbox")
    parser.add_argument("--input", type=Path, required=True, help="pdf_region_vector_table output")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise TypeError("Vector/native sonuç dosyası bir liste olmalı")
    inbox = to_review_inbox(results, args.document_id)
    args.output.write_text(json.dumps(inbox, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reviewable_tables": len(inbox), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
