import hashlib
import json
from pathlib import Path

import pymupdf

from app.pipeline.native_table_evidence import (
    _tokenize,
    extract_native_table_evidence,
    score_native_table_agreement,
)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path, checksum: str) -> Path:
    manifest = path / "regions.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "route_id": "table-1",
                        "source": {"page": 1, "bbox": [40, 40, 200, 120], "source_checksum": checksum},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _draft(checksum: str) -> dict:
    return {
        "schema_version": "visual-table-draft-v1",
        "publication_status": "requires-schema-validation-and-teacher-review",
        "kind": "table",
        "source": {"region_id": "table-1", "page": 1, "bbox": [40, 40, 200, 120], "source_checksum": checksum},
        "cells": [{"row": 1, "column": 1, "role": "data", "text": "alpha beta", "confidence": 0}],
        "confidence": 0,
    }


def test_extracts_private_native_tokens_and_scores_content_free_proxy(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    source = source_root / "source.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 70), "Alpha beta")
    page.insert_text((250, 70), "outside")
    document.save(source)
    document.close()
    checksum = _checksum(source)

    evidence = extract_native_table_evidence(source, source_root, _manifest(tmp_path, checksum))
    report = score_native_table_agreement([_draft(checksum)], json.loads(json.dumps(evidence)))

    assert evidence["contains_document_content"] is True
    assert evidence["evidence"][0]["tokens"] == ["alpha", "beta"]
    assert report["contains_document_content"] is False
    assert report["not_a_gold_accuracy_score"] is True
    assert report["records"][0]["decision"] == "high-source-agreement-proxy-needs-gold"


def test_source_checksum_mismatch_is_blocked(tmp_path: Path):
    evidence = {
        "schema_version": "native-table-evidence-v1",
        "evidence": [
            {
                "region_id": "table-1",
                "source": {"page": 1, "bbox": [40, 40, 200, 120], "source_checksum": "a" * 64},
                "tokens": ["alpha"],
            }
        ],
    }

    report = score_native_table_agreement([_draft("b" * 64)], evidence)

    assert report["records"][0]["decision"] == "blocked-source-mismatch"


def test_math_tokenizer_normalizes_latex_and_prime_variants():
    assert _tokenize(r"A′ \cup B \notin C") == ["a", "prime", "∪", "b", "∉", "c"]
