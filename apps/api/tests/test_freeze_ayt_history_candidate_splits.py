import hashlib

import pytest

from app.pipeline.freeze_ayt_history_candidate_splits import TARGETS, build


def _pack():
    rows = []
    # Four sources with group sizes that permit the fixed 5/5/3/11 holdouts.
    source_groups = {"s9": [3, 3, 3, 3, 2, 2, 2, 2, 2, 2], "s10": [3, 3, 3, 3, 2, 2, 2, 2, 2, 2],
                     "s11": [3, 3, 3, 2, 1, 1, 1], "s12": [3] * 18 + [2, 2]}
    number = 0
    for source_id, sizes in source_groups.items():
        for section, size in enumerate(sizes, start=1):
            for _ in range(size):
                number += 1
                rows.append({"id": f"q-{number:03d}", "question": f"Özgün soru {number}", "runtime_enabled": False,
                             "status": "source_crop_validation_required", "source_evidence": {"source_id": source_id,
                             "source_checksum": hashlib.sha256(source_id.encode()).hexdigest(), "section_id": str(section), "page": section}})
    assert len(rows) == 120
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "corpus_checksum": "b" * 64, "questions": rows}


def test_freezes_exact_source_section_grouped_72_24_24_split():
    result = build(_pack())
    assert result["summary"]["counts"] == TARGETS
    assert result["runtime_enabled"] is False
    by_group = {}
    for row in result["records"]:
        by_group.setdefault((row["source_id"], row["section_id"]), set()).add(row["split"])
    assert all(len(splits) == 1 for splits in by_group.values())
    assert result == build(_pack())


def test_rejects_exact_question_duplicate_across_source_sections():
    pack = _pack()
    pack["questions"][-1]["question"] = pack["questions"][0]["question"]
    with pytest.raises(ValueError, match="split sızıntısı"):
        build(pack)
