from pathlib import Path

import pymupdf
import pytest

from app.pipeline.pdf_text_layer import PdfSafetyError, extract_text_layer

FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def create_pdf(path: Path, text: str = "Pisagor bağıntısı") -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_font(fontname="DejaVu", fontfile=FONT_FILE)
    page.insert_text((72, 72), text, fontname="DejaVu")
    document.save(path)
    document.close()


def test_extracts_text_with_source_coordinate(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "matematik.pdf"
    create_pdf(pdf_path)

    result = extract_text_layer(pdf_path, source_root)

    assert result.page_count == 1
    assert result.blocks[0].text == "Pisagor bağıntısı"
    assert result.blocks[0].source.page == 1
    assert result.blocks[0].source.bbox[0] < result.blocks[0].source.bbox[2]
    assert len(result.source_checksum) == 64


def test_rejects_source_outside_private_root(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = tmp_path / "outside.pdf"
    create_pdf(pdf_path)

    with pytest.raises(PdfSafetyError, match="dışında"):
        extract_text_layer(pdf_path, source_root)


def test_rejects_non_pdf_magic_bytes(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    bad_pdf = source_root / "bad.pdf"
    bad_pdf.write_bytes(b"not-a-pdf")

    with pytest.raises(PdfSafetyError, match="magic-byte"):
        extract_text_layer(bad_pdf, source_root)


def test_allows_official_textbook_size_budget(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "kitap.pdf"
    create_pdf(pdf_path)
    # Sınır değeri testte küçültülür; gerçek kodun kabul aralığı 75 MiB'tir.
    monkeypatch.setattr("app.pipeline.pdf_text_layer.MAX_BYTES", pdf_path.stat().st_size)
    assert extract_text_layer(pdf_path, source_root).page_count == 1
