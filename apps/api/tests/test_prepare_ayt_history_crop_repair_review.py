import hashlib
import json

import pymupdf
import pytest

from app.pipeline.prepare_ayt_history_crop_repair_review import build


def _checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _pack(checksum):
    questions = [{"id": f"authoring-{index:03d}", "question": "Özgün tarih sorusu.",
                  "choices": ["A", "B", "C", "D", "E"], "correct_label": "A", "runtime_enabled": False,
                  "status": "source_crop_validation_required", "source_evidence": {"source_id": "meb-01", "source_checksum": checksum,
                  "page": 1, "bbox": [1, 1, 60, 40], "quote": "Kaynak alıntısı."}} for index in range(120)]
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64, "questions": questions}


def _audit(candidate_checksum):
    records = [{"id": f"authoring-{index:03d}", "source_id": "meb-01", "page": 1, "bbox": [1, 1, 60, 40],
                "quote_present_in_bbox": index not in {0, 1}, "character_similarity": 0.5 if index == 0 else 0.95}
               for index in range(120)]
    return {"schema": "ayt-history-candidate-pdf-crop-text-audit-v1", "candidate_checksum": candidate_checksum, "records": records}


def test_creates_prioritized_private_repair_queue_without_enabling_runtime(tmp_path):
    pdf = tmp_path / "source.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=100, height=100)
        page.insert_text((5, 20), "Kaynak alıntısı.")
        document.save(pdf)
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    pack = _pack(checksum)
    catalog = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-01", "source_checksum": checksum, "relative_path": pdf.name}]}
    output = tmp_path / "repair"
    result = build(pack, _audit(pack["candidate_checksum"]), catalog, tmp_path, output)
    assert result["review_count"] == 2
    assert [row["id"] for row in result["reviews"]] == ["authoring-000", "authoring-001"]
    assert result["reviews"][0]["reason"] == "material_text_mismatch"
    assert result["runtime_enabled"] is False
    assert len(list((output / "context-crops").glob("*.png"))) == 2


def test_rejects_audit_from_a_different_candidate_pack(tmp_path):
    with pytest.raises(ValueError, match="eşleşen PDF kırpım denetimi"):
        build({"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64, "questions": [{}] * 120},
              {"schema": "ayt-history-candidate-pdf-crop-text-audit-v1", "candidate_checksum": "b" * 64, "records": []},
              {"schema": "ayt-history-meb-source-catalog-v1", "sources": []}, tmp_path, tmp_path / "out")
