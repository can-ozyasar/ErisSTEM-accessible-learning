from app.pipeline.normalize_contextual_coach_evidence import normalize


def test_repairs_only_manifest_bound_ocr_duplication_and_records_provenance():
    payload = {"schema": "deepseek-contextual-source-bound-coaching-drafts-v1", "records": [{"question_id": "q", "turns": [{"source_ids": ["sum:atom"], "evidence_quotes": ["A tekrar tekrar B"]}]}]}
    overrides = {"overrides": [{"question_id": "q", "source_checksum": "sum", "atom_id": "atom", "page": 1, "bbox": [1], "raw_fragment": "tekrar tekrar", "normalized_fragment": "tekrar"}]}
    result = normalize(payload, overrides)
    turn = result["records"][0]["turns"][0]
    assert turn["evidence_quotes"] == ["A tekrar B"]
    assert turn["evidence_normalization"]["kind"] == "reviewed_ocr_duplication_repair"
