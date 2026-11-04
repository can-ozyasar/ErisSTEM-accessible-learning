import pytest

from app.pipeline.ogm_ayt_agent_review_view import render


def test_private_review_view_escapes_question_and_checks_source_identity():
    audit = {"schema": "ogm-ayt-full-agent-audit-v1", "source_checksum": "q",
             "reviews": [{"candidate_id": "question-1", "cards": [{
                 "source_checksum": "s", "chunk_id": "one", "verdict": "direct",
                 "reason": "Kaynakta ilişki yazılı.", "quote": "Kaynak alıntısı"}]}]}
    pack = {"schema": "ogm-ayt-teacher-review-pack-v1", "review_count": 1,
            "reviews": [{"candidate_id": "question-1", "topic": "Tarih",
                         "question": {"stem": "<script>alert(1)</script>", "choices": []},
                         "evidence_cards": [{"source_checksum": "s", "chunk_id": "one",
                                             "section_title": "Başlık", "page": 1,
                                             "crop": "crops/one.png"}]}]}
    validation = {"schema": "ogm-ayt-agent-audit-validation-v1", "source_checksum": "q",
                  "question_count": 1, "card_count": 1, "verdict_counts": {"direct": 1}}
    body = render(audit, pack, validation)
    assert "&lt;script&gt;" in body
    assert "<script>alert" not in body
    assert "öğretmen onayı" in body
    audit["reviews"][0]["cards"][0]["source_checksum"] = "changed"
    with pytest.raises(ValueError, match="sırası"):
        render(audit, pack, validation)
