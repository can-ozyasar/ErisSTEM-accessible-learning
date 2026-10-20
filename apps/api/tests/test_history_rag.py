from pathlib import Path

import pytest

from app.history_rag import build_index, matching_sections, retrieve, terms


def test_topic_gate_and_approved_retrieval():
    index = {"sections": [
        {"id": "1.1", "title": "Tarih Öğrenmenin Faydaları"},
        {"id": "2.1", "title": "Tarım Devrimi’nin Eski Çağ’a Etkileri"},
    ], "chunks": [
        {"id": "a", "section_id": "1.1", "text": "Tarih öğrenimi ortak hafızayı geliştirir ve toplumsal kimliği güçlendirir.", "page": 12},
        {"id": "b", "section_id": "2.1", "text": "Tarım üretimi yerleşik yaşamın gelişmesini sağladı.", "page": 70},
    ]}
    assert "öğrenmenin" in terms("ÖĞRENMENİN")
    assert matching_sections(index, "Tarih Öğrenmenin Faydaları") == ["1.1"]
    assert matching_sections(index, "Tarih Öğrenmenin Faydaları, Tarım Devrimi’nin Eski Çağ’a Etkileri") == ["1.1", "2.1"]
    assert retrieve(index, {"a", "b"}, "Tarih Öğrenmenin Faydaları", "ortak hafıza")[0]["id"] == "a"
    assert retrieve(index, {"b"}, "Tarih Öğrenmenin Faydaları", "ortak hafıza") == []
    assert retrieve(index, {"a", "b"}, "Belirsiz konu", "ortak hafıza") == []


BOOK = Path(__file__).parents[3] / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"


@pytest.mark.skipif(not BOOK.is_file(), reason="Local MEB source not installed")
def test_real_index_uses_toc_and_excludes_assessment_pages():
    index = build_index(BOOK)
    assert len(index["sections"]) == 13
    assert all(item["page"] <= {"1": 60, "2": 154, "3": 243}[item["section_id"][0]]
               for item in index["chunks"])
    assert any(item["section_id"] == "1.1" and item["page"] == 12 for item in index["chunks"])
