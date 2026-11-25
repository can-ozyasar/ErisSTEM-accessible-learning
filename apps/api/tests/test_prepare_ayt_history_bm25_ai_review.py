from app.pipeline.benchmark_ayt_history_atom_bm25 import build as bm25_build
from app.pipeline.prepare_ayt_history_bm25_ai_review import build


def _inputs():
    questions, splits, atoms = [], [], []
    for index in range(120):
        identifier, atom_id, marker = f"q-{index:03d}", f"a-{index:03d}", f"olay{index:03d}"
        questions.append({"id": identifier, "question": f"{marker} ortak nedir?", "choices": [marker, "B", "C", "D", "E"],
                          "source_evidence": {"source_checksum": "source", "atom_id": atom_id}})
        splits.append({"id": identifier, "split": "retrieval_test" if index < 24 else "system_acceptance" if index < 48 else "development"})
        atoms.append({"id": atom_id, "page": index + 1, "text": f"{marker} ortak kaynak kanıtıdır."})
    return ({"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
             "corpus_checksum": "b" * 64, "questions": questions},
            {"schema": "ayt-history-candidate-split-v1", "candidate_checksum": "a" * 64, "records": splits},
            {"schema": "multi-history-rag-v1", "corpus_checksum": "b" * 64,
             "books": [{"source_checksum": "source", "index": {"evidence_atoms": atoms}}]})


def test_builds_answer_blind_cards_for_exactly_the_frozen_retrieval_cases():
    pack, split, corpus = _inputs()
    baseline = bm25_build(pack, split, corpus)
    queue, calibration = build(pack, split, corpus, baseline)
    assert len(queue["proposals"]) == len(calibration["queries"]) == 24
    assert all(len(row["suggestions"]) == 3 for row in queue["proposals"])
    assert all(set(row) == {"id", "query"} for row in calibration["queries"])
    assert all(set(card) == {"source_checksum", "chunk_id", "text"}
               for proposal in queue["proposals"] for card in proposal["suggestions"])
    assert queue["answer_key_accessed"] is False
    assert calibration["is_human_teacher_approval"] is False


def test_rejects_baseline_from_another_source_revision():
    pack, split, corpus = _inputs()
    baseline = bm25_build(pack, split, corpus)
    baseline["corpus_checksum"] = "other"
    try:
        build(pack, split, corpus, baseline)
    except ValueError as error:
        assert "sürümüyle eşleşmiyor" in str(error)
    else:
        raise AssertionError("Farklı corpus sürümündeki baseline reddedilmeliydi")
