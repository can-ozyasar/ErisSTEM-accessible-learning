"""Regression checks for fail-closed review of real coaching drafts."""

from app.pipeline.audit_teacher_coaching_groups import audit
from app.tutor_dataset import CASES

QUESTION_ID = "ogm-ayt-deneme:test:q27"
QUESTION = "Hz. Ömer Dönemi'nde yapılan düzenlemelerden hangisi değildir?"
UNRELATED_QUOTE = "Ömer Hayyam, Melikşah döneminde astronomi ve takvim çalışmaları yaptı."


def _inputs():
    records = [{
        "question_id": QUESTION_ID,
        "case": case,
        "guide_response": "Bu sorunun hangi dönemi sorduğunu düşünür müsün?",
        "source_ids": ["source-1"],
        "source_evidence": [{"source_id": "source-1", "excerpt": UNRELATED_QUOTE}],
        "evidence_quotes": [UNRELATED_QUOTE],
        "early_answer_disclosed": False,
    } for case in CASES]
    draft = {"answer_key_accessed": False, "worked_explanation_accessed": False,
             "records": records}
    transcription = {
        "schema": "ogm-ayt-private-transcription-v1", "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "rows": [{"candidate_id": QUESTION_ID,
                  "question": {"stem": QUESTION, "choices": []}}],
    }
    return draft, transcription


def test_shared_name_does_not_authorize_training():
    draft, transcription = _inputs()
    result = audit([draft, draft], transcription)
    row = result["reviews"][0]
    assert row["status"] == "semantic_review_required"
    assert row["mechanically_valid"] is True
    assert row["training_eligible"] is False
    assert [item["stage"] for item in row["stage_responses"]] == list(CASES)
    assert all(item["coach_response"] for item in row["stage_responses"])
    assert result["qlora_enabled"] is False


def test_conflicting_revision_is_rejected():
    draft, transcription = _inputs()
    changed = {**draft, "records": [{**row} for row in draft["records"]]}
    changed["records"][0]["evidence_quotes"] = ["Farklı bir alıntı"]
    result = audit([draft, changed], transcription)
    assert result["reviews"][0]["status"] == "rejected"
    assert "six_complete_unique_stages_required" in result["reviews"][0]["issues"]


def test_source_quote_mismatch_is_rejected():
    draft, transcription = _inputs()
    draft["records"][0]["evidence_quotes"] = ["Kaynağın söylemediği başka bir bilgi."]
    result = audit([draft], transcription)
    assert result["reviews"][0]["status"] == "rejected"
    assert "source_quote_mismatch" in result["reviews"][0]["issues"]


def test_math_question_and_generic_coach_are_excluded():
    draft, transcription = _inputs()
    transcription["rows"][0]["question"]["stem"] = "a = cos2x ise doğru sıralanışı bulunuz."
    draft["records"][0]["guide_response"] = (
        "Bu ifadede olay, kişi, ilişki veya çıkarım hangisi öne çıkıyor?"
    )
    result = audit([draft], transcription)
    row = result["reviews"][0]
    assert row["status"] == "rejected"
    assert "question_domain_not_history" in row["issues"]
    assert "non_pedagogical_template" in row["issues"]


def test_history_word_sinyal_is_not_trigonometry():
    draft, transcription = _inputs()
    transcription["rows"][0]["question"]["stem"] = (
        "Mustafa Kemal bu sözle hangi siyasi gelişmenin sinyalini verdi?"
    )
    row = audit([draft], transcription)["reviews"][0]
    assert "question_domain_not_history" not in row["issues"]


def test_quote_must_exist_in_matching_corpus_source():
    draft, transcription = _inputs()
    corpus = {"schema": "multi-history-rag-v1", "books": [{
        "source_checksum": "checksum", "index": {"source_checksum": "checksum",
        "chunks": [{"id": "source-1", "text": "Bambaşka bir metin."}],
        "context_chunks": [], "evidence_atoms": []},
    }]}
    row = audit([draft], transcription, corpus=corpus)["reviews"][0]
    assert row["status"] == "rejected"
    assert "quote_missing_from_corpus_source" in row["issues"]


def test_visual_question_cannot_enter_text_coaching_audit():
    draft, transcription = _inputs()
    transcription["rows"][0]["question"]["stem"] = (
        "Aşağıdaki haritaya göre olayın gerçekleştiği yer neresidir?"
    )
    row = audit([draft], transcription)["reviews"][0]
    assert row["status"] == "rejected"
    assert "visual_question_out_of_scope" in row["issues"]


def test_embedded_visual_is_excluded_even_when_question_text_is_plain():
    draft, transcription = _inputs()
    transcription["rows"][0]["question"]["visuals"] = [{"id": "map"}]
    row = audit([draft], transcription)["reviews"][0]
    assert row["status"] == "rejected"
    assert "visual_question_out_of_scope" in row["issues"]


def test_source_free_opening_tours_are_not_rejected_for_missing_quotes():
    draft, transcription = _inputs()
    for record in draft["records"]:
        if record["case"] in CASES[:2]:
            record["source_ids"] = []
            record["source_evidence"] = []
            record["evidence_quotes"] = []
    row = audit([draft], transcription)["reviews"][0]
    assert "invalid_evidence_count" not in row["issues"]
    assert "invalid_source_binding" not in row["issues"]


def test_stale_transcription_cannot_bypass_current_pdf_candidates():
    draft, transcription = _inputs()
    current = {"answer_key_accessed": False, "worked_explanation_accessed": False,
               "rows": [{"candidate_id": "ogm-ayt-deneme:test:q28",
                         "question": {"parts": [{"text": "Tarih sorusu"}], "choices": []}}]}
    row = audit([draft], transcription, [current])["reviews"][0]
    assert "question_transcription_missing" in row["issues"]


def test_pdf_crop_review_requires_matching_file_and_coordinates():
    draft, transcription = _inputs()
    transcription["rows"][0]["question"]["source"] = {
        "source_checksum": "a" * 64, "page": 7, "bbox": [1, 2, 3, 4],
    }
    row = audit([draft], transcription, question_pdf_checksums={"b" * 64})["reviews"][0]
    assert row["status"] == "rejected"
    assert "question_pdf_unavailable_for_crop_review" in row["issues"]
    assert row["question_locator"]["page"] == 7
    assert row["question_locator"]["bbox"] == [1, 2, 3, 4]
    row = audit([draft], transcription, question_pdf_checksums={"a" * 64})["reviews"][0]
    assert "question_pdf_unavailable_for_crop_review" not in row["issues"]
    assert "question_crop_coordinates_missing" not in row["issues"]


def test_same_pdf_crop_under_two_ids_is_deduplicated():
    draft, transcription = _inputs()
    source = {"source_checksum": "a" * 64, "page": 7, "bbox": [1, 2, 3, 4]}
    transcription["rows"][0]["question"]["source"] = source
    duplicate_id = "ogm-ayt-deneme:test:q28"
    transcription["rows"].append({"candidate_id": duplicate_id, "question": {
        "stem": QUESTION, "choices": [], "source": source,
    }})
    draft["records"].extend({**record, "question_id": duplicate_id} for record in list(draft["records"]))
    result = audit([draft], transcription, question_pdf_checksums={"a" * 64})
    rows = {row["question_id"]: row for row in result["reviews"]}
    assert sum("duplicate_question_crop" in row["issues"] for row in rows.values()) == 1
    duplicate = next(row for row in rows.values() if "duplicate_question_crop" in row["issues"])
    assert duplicate["duplicate_of"] in rows
    assert duplicate["status"] == "rejected"
