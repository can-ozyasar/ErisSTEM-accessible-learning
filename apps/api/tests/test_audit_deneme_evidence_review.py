"""PDF provenance gates for proposed history evidence."""

from __future__ import annotations

import copy
import hashlib

import pymupdf
import pytest

from app.pipeline.audit_deneme_evidence_review import audit


def _fixture(tmp_path):
    qpath, spath = tmp_path / "questions.pdf", tmp_path / "source.pdf"
    for path, text in ((qpath, "Bir soru metni"), (spath, "Kaynakta olay ve tarih yaziyor.")):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 60), text)
        doc.save(path)
        doc.close()
    qhash = hashlib.sha256(qpath.read_bytes()).hexdigest()
    shash = hashlib.sha256(spath.read_bytes()).hexdigest()
    with pymupdf.open(spath) as doc:
        box = list(doc[0].search_for("Kaynakta olay ve tarih yaziyor.")[0])
    qbox = [40, 40, 200, 80]
    pool = {"schema": "official-ayt-target-discovery-pool-v1", "question_source_checksum": qhash,
            "rows": [{"candidate_id": "q1", "page": 1, "bbox": qbox,
                      "target_section_options": ["1.3"]}]}
    scope = {"sections": [{"section_id": "1.3", "book_page_range": {"start": 1, "end": 1}}]}
    atom = {"atom_id": "a1", "source_checksum": shash, "page": 1,
            "bbox": box, "bbox_segments": [box], "quote": "Kaynakta olay ve tarih yaziyor.",
            "teacher_status": "candidate_quote_verified_not_approved"}
    review = {"schema": "ayt-deneme-evidence-teacher-review-v1", "question_source": "pool.json",
              "meb_pdf_checksum": shash, "questions_reviewed": 1,
              "assessment_counts": {"direct": 1}, "answer_key_accessed": False,
              "worked_solution_accessed": False, "student_runtime_enabled": False,
              "qlora_enabled": False,
              "rows": [{"candidate_id": "q1", "teacher_section_id": "1.3", "question_pdf_page": 1,
                        "question_bbox": qbox, "answer_key_or_solution_used": False,
                        "production_or_qlora_approved": False, "assessment": "direct",
                        "evidence_count": 1, "evidence_atoms": [atom]}]}
    return qpath, spath, pool, scope, review


def _audit(data):
    qpath, spath, pool, scope, review = data
    return audit(review, pool, scope, question_pdf=qpath, source_pdf=spath,
                 review_source_name="pool.json")


def test_exact_source_quote_passes_but_is_not_approved(tmp_path):
    result = _audit(_fixture(tmp_path))
    assert result["quote_provenance_passed"] is True
    assert result["semantic_approval"] is False
    assert result["flags"] == []


def test_wrong_crop_is_reported_and_blocks_provenance(tmp_path):
    data = list(_fixture(tmp_path))
    data[4] = copy.deepcopy(data[4])
    data[4]["rows"][0]["evidence_atoms"][0]["quote"] = "Bu bilgi kesitte yok."
    result = _audit(data)
    assert result["quote_provenance_passed"] is False
    assert result["flags"][0]["kind"] == "quote_not_contiguous_in_crop"


def test_source_checksum_change_rejected(tmp_path):
    data = list(_fixture(tmp_path))
    data[4] = copy.deepcopy(data[4])
    data[4]["meb_pdf_checksum"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        _audit(data)


def test_answer_key_access_rejected(tmp_path):
    data = list(_fixture(tmp_path))
    data[4] = copy.deepcopy(data[4])
    data[4]["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="Cevap anahtarı"):
        _audit(data)
