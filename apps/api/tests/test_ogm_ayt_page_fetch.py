import pytest

from app.pipeline.ogm_ayt_page_fetch import fetch, parse_pages


def test_page_ranges_are_normalized():
    assert parse_pages("31,29-30,31") == [29, 30, 31]
    with pytest.raises(ValueError, match="1 ile 313"):
        parse_pages("0")


def test_fetch_stores_only_private_checksum_metadata(tmp_path):
    jpeg = b"\xff\xd8\xff" + b"x" * 10_000
    result = fetch([30], tmp_path, fetcher=lambda _url: jpeg)
    assert result["pages"][0]["page"] == 30
    assert result["content_exported"] is False
    assert (tmp_path / "pages" / "030.jpg").is_file()
    with pytest.raises(ValueError, match="JPEG"):
        fetch([31], tmp_path, fetcher=lambda _url: b"not-an-image")
