from app.pipeline.ayt_target_atom_queue import build


def _record(identifier: str, section: str, text: str, decision: str = "manual_review"):
    return {"id": identifier, "section_id": section, "section_title": "Millî Mücadele’ye Hazırlık",
            "page": 10 if identifier == "short" else 11, "bbox": [0, 0, 1, 1], "text": text,
            "heading": "Başlık", "pre_review": {"decision": decision},
            "quality": {"warnings": []}}


def _inputs():
    pool = {"schema": "ayt-target-discovery-pool-v1", "corpus_checksum": "corpus", "candidate_section_ids": ["1.3", "2.1", "2.4", "2.5", "3.1", "3.2"],
            "rows": [{"candidate_id": "q1", "topic": "Millî Mücadele", "transcription_status": "private_teacher_review_required",
                      "question": {"stem": "Ankara Antlaşması ile hangi sınır belirlendi?", "choices": [{"text": "Güney sınırı"}]}}]}
    book = {"grade": 12, "source_role": "primary_candidate", "source_checksum": "local", "source_name": "inkilap.pdf",
            "index": {"evidence_atoms": [_record("short", "2.1", "Ankara Antlaşması ile güney sınırı belirlendi."), _record("wrong", "9.9", "Alakasız bilgi")],
                      "context_chunks": [_record("context", "2.1", "Ankara Antlaşması Türkiye'nin güney sınırını belirleyen anlaşmadır.")]}}
    return pool, {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus", "books": [book]}


def test_atom_context_queue_keeps_short_clean_atom_and_never_enables_runtime():
    pool, corpus = _inputs()
    queue = build(pool, corpus, candidate_limit=2, first_stage_limit=2)
    proposal = queue["proposals"][0]
    assert queue["index_counts"] == {"atom": 1, "context": 1}
    assert any(item["record_id"] == "short" for item in proposal["suggestions"])
    assert all(item["section_id"] != "9.9" for item in proposal["suggestions"])
    assert queue["runtime_enabled"] is False
    assert queue["qlora_enabled"] is False
    assert queue["answer_key_accessed"] is False


def test_atom_context_queue_fails_closed_for_checksum_mismatch():
    pool, corpus = _inputs()
    corpus["corpus_checksum"] = "changed"
    try:
        build(pool, corpus)
    except ValueError as error:
        assert "checksum" in str(error)
    else:
        raise AssertionError("mismatched corpus must fail closed")
