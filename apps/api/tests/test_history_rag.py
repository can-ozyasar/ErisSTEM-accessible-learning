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
    assert any(item["section_id"] == "1.1" for item in index["chunks"])
    assert index["exclusions"].get("edebi_alinti_riski", 0) >= 1


def test_review_flags_activity_fragments_and_captions_without_changing_approval():
    from app.history_rag import candidate_review_warnings
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings(
        'III. Adım: Oynayanlar grubundan her bir kişiye Çatalhöyük’teki sosyal yaşamdan bir rol seçtirilir')
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings(
        've bu rolün neler yaşamış olabileceğini kendi bakış açıları ile canlandırmaları sağlatılır.')
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings('Kaynakları inceleyerek soruları cevap layınız.')
    assert 'gorsel_aciklama_olabilir' in candidate_review_warnings('Şanlıurfa Arkeoloji ve Mozaik Müzesi, Şanlıurfa')
    assert 'gorsel_aciklama_olabilir' in candidate_review_warnings('Banyoles Bölge Arkeoloji Müzesi')
    assert candidate_review_warnings('Tarım toplumsal yaşamda iş bölümünün gelişmesine katkı sağladı.') == []


def test_duplicate_chunks_are_collapsed_and_conflicting_ids_rejected():
    from app.history_rag import deduplicate_chunks
    chunk = {'id': 'same', 'text': 'Kaynak metni', 'page': 1}
    assert deduplicate_chunks([chunk, dict(chunk)]) == [chunk]
    with pytest.raises(ValueError, match='çakışan'):
        deduplicate_chunks([chunk, {**chunk, 'text': 'Farklı metin'}])

def test_pre_review_keeps_poetry_and_instructions_out_of_evidence_pool():
    from app.history_rag import source_review_recommendation
    poem = "Süleymaniye’de Bayram Sabahı (...) Ne kadar duygulu, engin ve mübârek bu seher! Kadın erkek ve çocuk, gönlü dolanlar, yer yer, Dinliyor hepsi büyük hâtıralar rüzgârını."
    assert source_review_recommendation(poem)["decision"] == "do_not_use"
    assert source_review_recommendation("III. Adım: Soruları cevaplayınız.")["decision"] == "do_not_use"
    assert source_review_recommendation("Tarım üretimi yerleşik yaşamın gelişmesini sağladı.")["decision"] == "review_for_approval"
