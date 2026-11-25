import hashlib

import pymupdf
import pytest

from app.pipeline.prepare_ogm_ayt_question_review import build


def _pdf(path):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Örnek AYT Tarih sorusu")
    document.save(path)


def _candidate(path):
    return {
        "schema": "ayt-target-question-candidates-v1",
        "source_checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": [{
            "candidate_id": "ogm-ayt-deneme:1:q1",
            "deneme_number": 1,
            "question": {
                "question_type": "multiple_choice", "number": 1,
                "parts": [{"text": "Örnek soru kökü"}],
                "choices": [{"label": label, "text": f"Seçenek {label}"} for label in "ABCDE"],
                "source": {"page": 1, "bbox": [60, 60, 300, 120]},
            },
        }],
    }


def test_build_renders_checksum_bound_question_crop(tmp_path):
    pdf = tmp_path / "deneme.pdf"
    _pdf(pdf)
    output = tmp_path / "review"
    pack = build(_candidate(pdf), pdf, output)
    assert pack["review_count"] == 1
    assert pack["runtime_enabled"] is False
    assert (output / pack["reviews"][0]["crop"]).is_file()
    assert pack["reviews"][0]["checks"]["pdf_text_matches"] is None


def test_build_refuses_changed_source_pdf(tmp_path):
    pdf = tmp_path / "deneme.pdf"
    _pdf(pdf)
    candidate = _candidate(pdf)
    pdf.write_bytes(pdf.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        build(candidate, pdf, tmp_path / "review")
