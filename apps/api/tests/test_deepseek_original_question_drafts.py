from app.pipeline.deepseek_original_question_drafts import draft
import pytest


def gate():
    return {"schema": "ayt-history-authoring-source-gate-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64,
            "accepted_for_pdf_crop_review": [{"pdf_crop_review_required": True,
                "card": {"id": "authoring-001", "source_evidence": {"quote": "Kaynak kanıtı."}},
                "ai_review": {"verdict": "direct_fact"}}]}


def test_creates_original_text_only_draft_from_source_card():
    def fake(_request, _key, _timeout):
        return {"choices": [{"message": {"content": '{"drafts":[{"id":"authoring-001","question":"Bu gelişmenin sonucu hangisidir?","spoken_question":"Bu gelişmenin sonucu hangisidir?","choices":["A seçeneği","B seçeneği","C seçeneği","D seçeneği","E seçeneği"],"correct_label":"A","explanation":"Kaynak, bu sonucu doğrudan belirtir."}]}'}}]}
    result = draft(gate(), "secret", request_fn=fake)
    assert result["drafts"][0]["authorship"] == "original"
    assert result["drafts"][0]["runtime_enabled"] is False
    assert result["drafts"][0]["choices"]["ABCDE".index(result["drafts"][0]["correct_label"])] == "A seçeneği"


def test_rejects_batch_larger_than_five_to_prevent_truncated_json():
    with pytest.raises(ValueError, match="offset veya limit"):
        draft(gate(), "secret", limit=6, request_fn=lambda *_: {})
