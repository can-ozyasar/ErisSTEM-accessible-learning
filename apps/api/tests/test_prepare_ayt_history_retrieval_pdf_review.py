import hashlib

import pymupdf

from app.pipeline.prepare_ayt_history_retrieval_pdf_review import _write_html, build


def _inputs(tmp_path):
    pdf = tmp_path / "book.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Kaynak kanit metni")
    document.save(pdf)
    document.close()
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    questions, records, cases, atoms = [], [], [], []
    for index in range(120):
        identifier, atom_id = f"q-{index:03d}", f"a-{index:03d}"
        questions.append({"id": identifier, "question": f"Soru {index}", "choices": ["A", "B", "C", "D", "E"]})
        records.append({"id": identifier, "split": "retrieval_test" if index < 24 else "development"})
        atoms.extend([{"id": f"{atom_id}-{card}", "page": 1, "bbox": [60, 60, 220, 100], "text": f"Kanıt {index}-{card}"} for card in range(3)])
        if index < 24:
            cases.append({"id": identifier, "retrieved_atom_ids": [f"{checksum}:{atom_id}-{card}" for card in range(3)]})
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "corpus_checksum": "b" * 64, "questions": questions}
    split = {"schema": "ayt-history-candidate-split-v1", "candidate_checksum": "a" * 64, "records": records}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "b" * 64,
              "books": [{"source_checksum": checksum, "index": {"evidence_atoms": atoms}}]}
    baseline = {"schema": "ayt-history-provisional-atom-bm25-baseline-v1", "candidate_checksum": "a" * 64,
                "corpus_checksum": "b" * 64, "split_checksum": "s", "k": 3, "cases": cases}
    catalog = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"source_checksum": checksum, "relative_path": "book.pdf"}]}
    return pack, split, corpus, baseline, catalog


def test_prepares_rank_blind_pdf_crop_review_without_answer_or_reference_fields(tmp_path):
    result = build(*_inputs(tmp_path), tmp_path, tmp_path / "review")
    assert result["review_count"] == 24
    assert all(len(row["cards"]) == 3 for row in result["reviews"])
    assert all(card["decision"] is None for row in result["reviews"] for card in row["cards"])
    assert result["answer_key_accessed"] is False
    assert result["reference_atom_accessed"] is False
    assert result["runtime_enabled"] is False


def test_rejects_baseline_with_unexpected_retrieval_case(tmp_path):
    pack, split, corpus, baseline, catalog = _inputs(tmp_path)
    baseline["cases"][0]["id"] = "unknown"
    try:
        build(pack, split, corpus, baseline, catalog, tmp_path, tmp_path / "review")
    except ValueError as error:
        assert "24 kilitli" in str(error)
    else:
        raise AssertionError("Kilitli küme dışındaki vaka reddedilmeliydi")


def test_local_review_page_exports_completed_json_without_showing_answer_material(tmp_path):
    result = build(*_inputs(tmp_path), tmp_path, tmp_path / "review")
    _write_html(result, tmp_path / "review")
    page = (tmp_path / "review" / "index.html").read_text(encoding="utf-8")
    assert "Completed JSON indir" in page
    assert "relevant','wrong','insufficient" in page
    assert "correct_label" not in page
    assert "reference_atom_id" not in page
