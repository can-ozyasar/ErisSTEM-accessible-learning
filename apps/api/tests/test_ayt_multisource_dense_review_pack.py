import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.pipeline.ayt_multisource_dense_review_pack import build
from app.pipeline.prepare_ayt_multisource_dense_review import build as prepare

ROOT = Path(__file__).parents[3]


def _queue() -> dict:
    discovery = json.loads(
        (ROOT / "data/private/yks-ayt-source-v1/official-ayt-multisource-dense-discovery-local11-12-v1.json").read_text(encoding="utf-8")
    )
    document_ids = [document["id"] for document in discovery["documents"]]
    rankings = {
        "schema": "official-ayt-multisource-dense-discovery-rankings-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "rankings": {
            query["id"]: {"qwen_dense_tr": document_ids[:20], "bm25": document_ids[1:21], "rrf": document_ids[2:22]}
            for query in discovery["queries"]
        },
    }
    return prepare(discovery, rankings)


def _sources(queue: dict) -> dict[str, Path]:
    paths = {
        11: ROOT / "data/meb/tarih-11sinif-ders-kitabi_20260908.pdf",
        12: ROOT / "data/private/yks-ayt-source-v1/inkilap-yardimci-aday.pdf",
    }
    return {binding["source_checksum"]: paths[binding["grade"]] for binding in queue["source_bindings"]}


def test_renders_checksum_verified_private_crop_pack(tmp_path: Path):
    queue = _queue()
    result = build(queue, _sources(queue), tmp_path, per_question=1)
    assert result["review_count"] == 10
    assert result["crop_count"] == 10
    assert (tmp_path / "index.html").is_file()
    assert result["runtime_enabled"] is False


def test_rejects_incomplete_source_mapping(tmp_path: Path):
    queue = _queue()
    sources = _sources(queue)
    sources.pop(next(iter(sources)))
    with pytest.raises(ValueError, match="tam eşleşmeli"):
        build(queue, sources, tmp_path, per_question=1)


def test_rejects_excerpt_from_unrelated_crop(tmp_path: Path):
    queue = _queue()
    queue["rows"][0]["suggestions"][0]["excerpt"] = "Bu ifade bu PDF kesitinde bulunmayan bir bilgidir."
    with pytest.raises(ValueError, match="metin kapsamını"):
        build(queue, _sources(queue), tmp_path, per_question=1)


def test_full_queue_uses_explicit_full_pack_schema(tmp_path: Path):
    queue = deepcopy(_queue())
    queue["schema"] = "official-ayt-full-multisource-dense-review-queue-v1"
    result = build(queue, _sources(queue), tmp_path, per_question=1)
    assert result["schema"] == "ayt-full-multisource-dense-review-pack-v1"
