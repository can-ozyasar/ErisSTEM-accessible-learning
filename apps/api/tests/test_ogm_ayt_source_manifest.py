import json

import pytest

from app.pipeline.ogm_ayt_source_manifest import build, parse_pages


def test_manifest_parses_data_without_evaluating_javascript(tmp_path):
    source = tmp_path / "search_config.js"
    source.write_text('var textForPages = ["TARİH Orta Çağ’da Dünya ÇÖZÜMLÜ SORULAR", "CEVAP ANAHTARI"]; evil();', encoding="utf-8")
    manifest = build(source)
    assert manifest["page_count"] == 2
    assert manifest["content_exported"] is False
    assert manifest["answer_key_exported"] is False
    assert manifest["topic_candidate_counts"] == {"Orta Çağ'da Dünya": 1}
    assert "TARİH" not in json.dumps(manifest, ensure_ascii=False)


def test_manifest_rejects_missing_or_non_json_text_array():
    with pytest.raises(ValueError, match="textForPages"):
        parse_pages("const nothing = []")
    with pytest.raises(ValueError, match="JSON"):
        parse_pages("var textForPages = ['not-json']")
