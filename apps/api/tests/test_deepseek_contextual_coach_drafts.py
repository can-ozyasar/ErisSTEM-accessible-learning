from app.pipeline.deepseek_contextual_coach_drafts import draft
from app.tutor_dataset import CASES


def test_can_regenerate_only_named_question_without_changing_pack_binding():
    pack = {
        "schema": "ayt-history-question-bank-training-candidate-v1",
        "corpus_checksum": "corpus",
        "frozen_checksum": "pack",
        "questions": [
            {"id": "keep", "question": "Kök", "source_evidence": {"quote": "Kanıt.", "source_checksum": "s", "atom_id": "a"}},
            {"id": "repair", "question": "Kök iki", "source_evidence": {"quote": "Kanıt iki.", "source_checksum": "s", "atom_id": "b"}},
        ],
    }
    turns = [{"case": case, "strategy": "adım", "response": "Bunu kendi cümlenle ilişkilendirir misin?"} for case in CASES]
    def request_fn(*_args):
        return {"choices": [{"message": {"content": '{"groups":[{"question_id":"repair","turns":' + __import__('json').dumps(turns, ensure_ascii=False) + '}]} '}}]}

    result = draft(pack, "key", question_ids={"repair"}, request_fn=request_fn)
    assert result["question_bank_checksum"] == "pack"
    assert [row["question_id"] for row in result["records"]] == ["repair"]
