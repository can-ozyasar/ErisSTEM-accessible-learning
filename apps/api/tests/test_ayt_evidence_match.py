from app.pipeline.ayt_evidence_match import build


def _question(candidate_id: str, year_status: str = "bound") -> dict:
    return {
        "candidate_id": candidate_id,
        "exam_year": 2024 if year_status == "bound" else None,
        "year_status": year_status,
        "question": {
            "parts": [{"text": "Lozan Barış Antlaşması hangi gelişme ile ilgilidir?"}],
            "choices": [{"label": "A", "text": "Millî Mücadele"}],
        },
    }


def _corpus() -> dict:
    return {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "corpus-v1",
        "books": [{
            "grade": 12,
            "source_name": "inkilap.pdf",
            "source_checksum": "book-v1",
            "index": {"chunks": [{
                "id": "lozan", "section_id": "2.6", "section_title": "Lozan Barış Antlaşması",
                "page": 95, "bbox": [1, 2, 3, 4],
                "text": "Lozan Barış Antlaşması Millî Mücadele'nin sonunda imzalandı.",
                "pre_review": {"decision": "review_for_approval"},
            }]},
        }],
    }


def test_proposals_are_checksum_bound_and_never_auto_approved():
    source = {"schema": "ayt-tarih2-candidates-v1", "source_checksum": "questions-v1",
              "candidates": [_question("bound"), _question("unbound", "review_required")]}
    result = build(source, _corpus(), limit=3)
    assert result["corpus_checksum"] == "corpus-v1"
    bound, unbound = result["proposals"]
    assert bound["status"] == "teacher_review_required"
    assert bound["suggestions"][0]["chunk_id"] == "lozan"
    assert bound["suggestions"][0]["review_status"] == "candidate"
    assert unbound["status"] == "blocked_until_exam_year_review"
    assert unbound["suggestions"] == []


def test_out_of_scope_year_never_reaches_retrieval():
    source = {"schema": "ayt-tarih2-candidates-v1", "source_checksum": "questions-v1",
              "candidates": [_question("old", "out_of_scope")]}
    result = build(source, _corpus(), limit=3)
    assert result["proposals"][0]["status"] == "out_of_scope"
    assert result["proposals"][0]["suggestions"] == []
