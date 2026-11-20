from app.pipeline.build_original_ayt_authoring_queue import build


def corpus():
    books = []
    for grade in (9, 10, 11, 12):
        checksum = f"{grade:x}" * 64
        books.append({
            "grade": grade, "source_name": f"meb-tarih-{grade}.pdf", "source_checksum": checksum,
            "index": {"sections": [{"id": "1.1", "title": f"Konu {grade}"}],
                      "evidence_atoms": [
                          {"id": f"{grade}-usable", "section_id": "1.1", "source_checksum": checksum,
                           "page": 1, "bbox": [1, 2, 3, 4],
                           "text": "Bu kaynak atomu doğrudan tarihsel bilgiyi yeterince açık biçimde verir.",
                           "quality": {"warnings": []}, "pre_review": {"decision": "manual_review"}},
                          {"id": f"{grade}-visual", "section_id": "1.1", "source_checksum": checksum,
                           "page": 2, "bbox": [1, 2, 3, 4],
                           "text": "Kaynakta bir heykel tarihsel değişimi temsil eder.",
                           "quality": {"warnings": []}, "pre_review": {"decision": "manual_review"}},
                      ]},
        })
    return {"schema": "multi-history-rag-v1", "corpus_checksum": "c" * 64, "books": books}


def test_builds_source_only_original_authoring_cards():
    result = build(corpus(), limit=4)
    assert result["summary"]["card_count"] == 4
    assert len(result["queue_checksum"]) == 64
    assert result["answer_key_accessed"] is False
    assert all(row["authorship_required"] == "original" for row in result["cards"])
    assert all(row["question_text"] is None and row["choices"] is None for row in result["cards"])
    assert all("heykel" not in row["source_evidence"]["quote"] for row in result["cards"])


def test_can_build_a_non_overlapping_follow_up_sample():
    first = build(corpus(), limit=2)
    follow_up = build(corpus(), limit=2, source_offset=2, card_start=121)
    assert {row["source_evidence"]["atom_id"] for row in first["cards"]}.isdisjoint(
        row["source_evidence"]["atom_id"] for row in follow_up["cards"])
    assert [row["id"] for row in follow_up["cards"]] == ["authoring-121", "authoring-122"]
