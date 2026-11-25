import hashlib
import json

import pymupdf
import pytest

from app.pipeline.register_meb_exam_source import append_catalog, register


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
    assert source["relative_path"] == "tarih.pdf"
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


def test_rejects_unsafe_mounted_pdf_path(tmp_path):
    pdf = tmp_path / "tarih.pdf"
    make_pdf(pdf)
    with pytest.raises(ValueError, match="Göreli"):
        register(pdf, "meb-tarih-12-2026", "MEB Tarih 12. Sınıf Ders Kitabı",
                 "https://ogmmateryal.eba.gov.tr/kitap/tarih-12.pdf", "../tarih.pdf")


def test_allows_official_eba_subdomain_and_appends_without_overwriting(tmp_path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_pdf(first)
    make_pdf(second)
    catalog_path = tmp_path / "sources.json"
    one = register(first, "meb-tarih-09-2026", "MEB Tarih 9. Sınıf Ders Kitabı",
                   "https://tymm.meb.gov.tr/kitap/43/tarih-9.sinif-ders-kitabi")
    two = register(second, "meb-inkilap-12-2026", "MEB İnkılap Tarihi 12. Sınıf Ders Kitabı",
                   "https://ders.eba.gov.tr/ders/redirectContent.jsp?resourceId=example")
    catalog_path.write_text(json.dumps(append_catalog(catalog_path, one["sources"][0])))
    merged = append_catalog(catalog_path, two["sources"][0])
    assert [source["id"] for source in merged["sources"]] == ["meb-tarih-09-2026", "meb-inkilap-12-2026"]
    with pytest.raises(ValueError, match="zaten var"):
        append_catalog(catalog_path, one["sources"][0])
