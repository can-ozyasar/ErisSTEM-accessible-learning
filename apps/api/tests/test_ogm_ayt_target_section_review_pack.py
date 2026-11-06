import pytest

from app.pipeline.ogm_ayt_target_section_review_pack import build


def test_answer_bearing_queue_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        build(
            {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q", "rows": []},
            {"schema": "ayt-target-atom-context-review-queue-v1", "answer_key_accessed": True},
            {"schema": "multi-history-rag-v1"}, [], tmp_path,
        )
