import importlib.util
from pathlib import Path

import pymupdf


def module():
    path = Path(__file__).parents[3] / "experiments/kaggle/tts_history_coverage_audit.py"
    spec = importlib.util.spec_from_file_location("tts_history_coverage_audit", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def test_audit_scans_lesson_pages_and_counts_source_letters(tmp_path):
    pdf_path = tmp_path / "book.pdf"
    pdf = pymupdf.open()
    for page_number in range(1, 11):
        page = pdf.new_page()
        page.insert_text((72, 100), "Kaynak C. Tarih 1959." if page_number == 10 else "Cover 1959")
    pdf.save(pdf_path)
    pdf.close()
    report = module().audit(pdf_path)
    assert report["page_count"] == 10
    assert report["scanned_pages"] == [10, 10]
    assert report["categories"]["source_letter"]["letters"] == {"C": 1}
    assert report["categories"]["year_or_year_range"]["matches"] == 1
