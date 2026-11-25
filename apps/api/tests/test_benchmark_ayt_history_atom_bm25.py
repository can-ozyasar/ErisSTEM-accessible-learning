from app.pipeline.benchmark_ayt_history_atom_bm25 import build


def _inputs():
    questions = []
    splits = []
    atoms = []
    for index in range(120):
        identifier = f"q-{index:03d}"
        atom_id = f"a-{index:03d}"
        marker = f"olay{index:03d}"
        questions.append({"id": identifier, "question": f"{marker} nedir?", "choices": [marker, "B", "C", "D", "E"],
                          "runtime_enabled": False, "status": "source_crop_validation_required",
                          "source_evidence": {"source_checksum": "source", "atom_id": atom_id}})
        split = "retrieval_test" if index < 24 else "system_acceptance" if index < 48 else "development"
        splits.append({"id": identifier, "split": split})
        atoms.append({"id": atom_id, "page": index + 1, "text": f"{marker} kaynak kanıtıdır."})
    return ({"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
             "corpus_checksum": "b" * 64, "questions": questions},
            {"schema": "ayt-history-candidate-split-v1", "candidate_checksum": "a" * 64, "records": splits},
            {"schema": "multi-history-rag-v1", "corpus_checksum": "b" * 64,
             "books": [{"source_checksum": "source", "index": {"evidence_atoms": atoms}}]})


def test_measures_frozen_retrieval_split_without_answer_fields():
    pack, split, corpus = _inputs()
    result = build(pack, split, corpus)
    assert result["metrics"]["query_count"] == 24
    assert result["metrics"]["recall_at_3"] == 1
    assert result["answer_key_accessed"] is False
    assert result["runtime_enabled"] is False
    assert all("answer_label" not in row for row in result["cases"])


def test_rejects_wrong_split_size():
    pack, split, corpus = _inputs()
    split["records"][0]["split"] = "development"
    try:
        build(pack, split, corpus)
    except ValueError as error:
        assert "24 kayıtlı" in str(error)
    else:
        raise AssertionError("Eksik kilitli retrieval split reddedilmeliydi")


def test_deduplicates_only_identical_source_atom_rows():
    pack, split, corpus = _inputs()
    atom = corpus["books"][0]["index"]["evidence_atoms"][0]
    corpus["books"][0]["index"]["evidence_atoms"].append(dict(atom))
    assert build(pack, split, corpus)["exact_duplicate_atoms_deduplicated"] == 1
    corpus["books"][0]["index"]["evidence_atoms"][-1]["text"] = "Çelişkili metin"
    try:
        build(pack, split, corpus)
    except ValueError as error:
        assert "farklı içerikle" in str(error)
    else:
        raise AssertionError("Çelişkili atom yinelenmesi reddedilmeliydi")
