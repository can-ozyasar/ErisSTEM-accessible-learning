import hashlib

import pymupdf
import pytest

from app.pipeline.register_meb_exam_source import register


def make_pdf(path):
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()


def test_registers_only_private_pdf_with_official_meb_url(tmp_path):
    pdf = tmp_path / "tarih.pdf"
    make_pdf(pdf)
    result = register(pdf, "meb-tarih-12-2026", "MEB Tarih 12. Sınıf Ders Kitabı",
                      "https://ogmmateryal.eba.gov.tr/kitap/tarih-12.pdf")
    source = result["sources"][0]
    assert source["kind"] == "meb_textbook"
    assert source["source_checksum"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert source["page_count"] == 1
    assert result["pdf_exported"] is False


@pytest.mark.parametrize("url", ["https://example.org/tarih.pdf", "https://meb.example.org/tarih.pdf"])
def test_rejects_non_official_source_url(tmp_path, url):
    pdf = tmp_path / "tarih.pdf"
    make_pdf(pdf)
    with pytest.raises(ValueError, match="resmî MEB"):
        register(pdf, "meb-tarih-12-2026", "MEB Tarih 12. Sınıf Ders Kitabı", url)


def test_rejects_pdf_without_readable_pages(tmp_path):
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.7 but not an actual PDF")
    with pytest.raises(ValueError, match="ayrıştırılamadı|sayfa sayısı"):
        register(pdf, "meb-tarih-12-2026", "MEB Tarih 12. Sınıf Ders Kitabı",
                 "https://ogmmateryal.eba.gov.tr/kitap/tarih-12.pdf")
