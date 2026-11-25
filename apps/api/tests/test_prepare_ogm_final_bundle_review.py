import copy
import hashlib

import pytest

from app.pipeline.prepare_ogm_final_bundle_review import build


def _inputs():
    identifier = "question-1"
    item = {"id": "e1", "source_name": "meb.pdf", "source_checksum": "s", "page": 2,
            "bbox": [1, 2, 3, 4], "excerpt": "Kaynak metni"}
    pid = "ai-reviewed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20]
    pack = {"content_mode": "ai_source_reviewed_local_pilot", "licensed_question_source_checksum": "q",
            "questions": [{"id": pid, "authorship": "ai_source_reviewed_local_pilot", "question": "Soru?",
                           "choices": ["Bir", "İki", "Üç", "Dört", "Beş"], "evidence": [{
                "source_id": "meb.pdf", "source_checksum": "s", "page": 2, "bbox": [1, 2, 3, 4], "quote": "Kaynak metni"}]}]}
    candidates = {"schema": "ogm-ayt-history-source-grounded-pilot-candidates-v1", "runtime_enabled": False,
                  "source_checksum": "q", "candidate_count": 1,
                  "questions": [{"candidate_id": identifier, "correct_choice": "A", "evidence_bundle": [item]}]}
    queue = {"schema": "ogm-ayt-real-question-evidence-queue-v1", "question_source_checksum": "q", "corpus_checksum": "c",
             "proposals": [{"candidate_id": identifier, "question_text": "Soru ve seçenekler", "suggestions": [copy.deepcopy(item)]}]}
    return pack, candidates, queue


def test_exact_final_bundle_is_answer_blind():
    result = build(*_inputs())
    assert result["question_count"] == 1
    assert result["runtime_enabled"] is False
    assert "correct_choice" not in str(result)
    assert "E) Beş" in result["proposals"][0]["question_text"]


def test_changed_runtime_quote_is_rejected():
    pack, candidates, queue = _inputs()
    pack["questions"][0]["evidence"][0]["quote"] = "Farklı metin"
    with pytest.raises(ValueError, match="aktif pilot"):
        build(pack, candidates, queue)
