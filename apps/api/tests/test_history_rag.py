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
BOOK_12 = Path(__file__).parents[3] / "data/meb/inkilap-12-aday-eba.pdf"


@pytest.mark.skipif(not BOOK.is_file(), reason="Local MEB source not installed")
def test_real_index_uses_toc_and_excludes_assessment_pages():
    index = build_index(BOOK)
    assert len(index["sections"]) == 13
    assert all(item["page"] <= {"1": 60, "2": 154, "3": 243}[item["section_id"][0]]
               for item in index["chunks"])
    assert any(item["section_id"] == "1.1" for item in index["chunks"])
    assert index["exclusions"].get("edebi_alinti_yapisi", 0) >= 1


@pytest.mark.skipif(not BOOK_12.is_file(), reason="Local MEB 12th-grade source not installed")
def test_current_12th_grade_toc_recovers_wrapped_and_split_rows():
    """Current MEB 12 PDF has both split page-number blocks and wrapped titles."""
    index = build_index(BOOK_12)
    sections = {item["id"]: item for item in index["sections"]}
    assert len(sections) == 32
    assert sections["2.6"]["start"] == 94
    assert sections["8.2"]["start"] == 262
    assert sections["8.2"]["end"] == 270


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

def test_pre_review_uses_generic_poetry_layout_not_a_specific_title():
    from app.history_rag import block_layout, source_review_recommendation
    poetry = ["Başlık", "(...) ", "Kısa bir dize ve ritim", "Başka kısa bir dize", "Son kısa dize."]
    result = source_review_recommendation(" ".join(poetry), block_layout(poetry))
    assert result["decision"] == "do_not_use"
    assert result["reasons"] == ["edebi_alinti_yapisi"]
    prose = ["Tarım üretimi yerleşik yaşamın gelişmesini sağladı ve toplumsal yapıyı değiştirdi.",
             "Bu değişim farklı mesleklerin ortaya çıkmasına da katkı sağladı."]
    assert source_review_recommendation(" ".join(prose), block_layout(prose))["decision"] == "review_for_approval"
    assert source_review_recommendation("III. Adım: Soruları cevaplayınız.")["decision"] == "do_not_use"


def test_source_quote_is_kept_for_manual_pdf_review_only():
    from app.history_rag import _candidate, source_review_recommendation

    quote = (
        "“Gök Türklerde siyasi iktidar kut tabiri ile ifade olunuyordu ve "
        "kağan töreyi uygulardı; meclis kağanın icraatını denetlerdi.”"
    )
    assert _candidate(quote, [30, 60, 400, 200], 800)
    result = source_review_recommendation(quote)
    assert result["decision"] == "manual_review"
    assert result["reasons"] == ["kaynak_alintisi_baglam_kontrolu"]
    assert result["source_type"] == "quoted_source"
