import json

from app.pipeline.export_contextual_coach_qlora_experiment import build
from app.tutor_dataset import CASES


def _row(group_id: str) -> dict:
    return {"group_id": group_id, "case": "soruyu_anlama", "error_type": "genel", "section_key": "grade:9:section:1.1",
            "source_id": "checksum:atom", "evidence_quote": "Kaynak.", "learner_state": "Öğrenci düşünüyor.",
            "prompt": "Soru\nKoç:", "completion": "Bunu nasıl yorumlarsın?", "runtime_enabled": False}


def test_export_strips_source_coordinates_and_keeps_sealed_test_local(tmp_path):
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"schema": "ayt-history-contextual-coach-qlora-candidates-v1", "contains_answer_keys": False, "question_bank_checksum": "q"}), encoding="utf-8")
    for name, group_id in (("train", "train-q"), ("dev", "dev-q")):
        rows = []
        for case in CASES:
            row = _row(group_id)
            row["case"] = case
            rows.append(json.dumps(row, ensure_ascii=False))
        (source / f"{name}.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    result = build(source, tmp_path / "out")
    exported = json.loads((tmp_path / "out" / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(exported) == {"group_id", "case", "error_type", "prompt", "completion"}
    assert result["sealed_test_uploaded"] is False
    assert not (tmp_path / "out" / "sealed_test.jsonl").exists()


def test_export_preserves_fixed_three_epoch_contract_for_resumable_training(tmp_path):
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"schema": "ayt-history-contextual-coach-qlora-candidates-v1", "contains_answer_keys": False, "question_bank_checksum": "q"}), encoding="utf-8")
    for name, group_id in (("train", "train-q"), ("dev", "dev-q")):
        rows = []
        for case in CASES:
            row = _row(group_id)
            row["case"] = case
            rows.append(json.dumps(row, ensure_ascii=False))
        (source / f"{name}.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = build(source, tmp_path / "out")

    assert result["training_contract"]["epochs"] == 3
    assert result["acceptance_gate"]["dev_is_for_selection_only"] is True
