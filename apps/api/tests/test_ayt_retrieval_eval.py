from app.pipeline.ayt_retrieval_eval import build_template, evaluate_bm25


def _questions():
    return {
        "source_checksum": "questions-v1",
        "candidates": [{"candidate_id": "q1", "question": {
            "parts": [{"text": "Lozan Barış Antlaşması hangi sürecin sonunda imzalandı?"}],
            "choices": [],
        }}],
    }


def _proposals():
    return {
        "schema": "ayt-evidence-proposals-v1", "question_source_checksum": "questions-v1",
        "corpus_checksum": "corpus-v1", "proposals": [{
            "candidate_id": "q1", "exam_year": 2024, "status": "teacher_review_required",
            "suggestions": [{"source_checksum": "book-v1", "chunk_id": "lozan", "grade": 12,
                             "page": 95, "section_title": "Lozan", "pre_review": {}}],
        }],
    }


def _corpus():
    return {
        "corpus_checksum": "corpus-v1", "books": [{
            "grade": 12, "source_checksum": "book-v1", "index": {"chunks": [{
                "id": "lozan", "page": 95, "text": "Lozan Barış Antlaşması Millî Mücadele sonunda imzalandı.",
                "pre_review": {"decision": "review_for_approval"},
            }]},
        }],
    }


def test_template_requires_source_checked_primary_judgment_for_evaluation():
    template = build_template(_questions(), _proposals())
    assert template["cases"][0]["outcome"] == "pending"
    case = template["cases"][0]
    case.update({"outcome": "evidence_selected", "crop_checked": True, "reviewer": "teacher-1"})
    case["judgments"][0]["role"] = "primary"
    result = evaluate_bm25(template, _questions(), _proposals(), _corpus())
    assert result["evaluated_cases"] == 1
    assert result["summary"]["recall_at_k"] == 1.0
    assert result["summary"]["top1_wrong_rate"] == 0.0
