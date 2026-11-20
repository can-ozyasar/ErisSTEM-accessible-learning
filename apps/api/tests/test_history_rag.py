from pathlib import Path

import pytest

from app.history_rag import build_index, load_index, matching_sections, retrieve, sections, terms


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


def test_loader_accepts_current_schema_and_rejects_unknown_schema(tmp_path):
    import hashlib
    import json

    source = tmp_path / "source.pdf"
    source.write_bytes(b"private-source")
    index = tmp_path / "history-rag.json"
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    index.write_text(json.dumps({"schema": 2, "source_checksum": checksum, "chunks": []}), encoding="utf-8")
    assert load_index(source, index)["schema"] == 2
    index.write_text(json.dumps({"schema": 3, "source_checksum": checksum, "chunks": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="kaynak PDF sürümüyle eşleşmiyor"):
        load_index(source, index)


BOOK = Path(__file__).parents[3] / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
BOOK_12 = Path(__file__).parents[3] / "data/meb/inkilap-12-aday-eba.pdf"
AYT_SUMMARY = Path(__file__).parents[3] / "data/private/ogm-supplementary-v1/ayt-konu-ozetleri.pdf"


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
    assert sections["2.6"]["start"] == 95
    assert sections["8.2"]["start"] == 263
    assert sections["8.2"]["end"] == 271
    assert sections["3.2"]["start"] == 110
    assert sections["3.2"]["end"] == 113


@pytest.mark.skipif(not AYT_SUMMARY.is_file(), reason="Local AYT summary source not installed")
def test_summary_toc_keeps_date_leading_flat_heading():
    """A flat summary title may begin with a date such as ``20. Yüzyıl``."""
    import pymupdf

    source_sections = {item["id"]: item for item in sections(pymupdf.open(AYT_SUMMARY))}
    assert source_sections["summary.54"]["title"] == "20. Yüzyıl Başlarında Osmanlı Devleti"
    assert source_sections["summary.54"]["start"] < source_sections["summary.55"]["start"]


def test_review_flags_activity_fragments_and_captions_without_changing_approval():
    from app.history_rag import candidate_review_warnings, is_visual_caption
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings(
        'III. Adım: Oynayanlar grubundan her bir kişiye Çatalhöyük’teki sosyal yaşamdan bir rol seçtirilir')
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings(
        've bu rolün neler yaşamış olabileceğini kendi bakış açıları ile canlandırmaları sağlatılır.')
    assert 'etkinlik_yonergesi_olabilir' in candidate_review_warnings('Kaynakları inceleyerek soruları cevap layınız.')
    assert 'gorsel_aciklama_olabilir' in candidate_review_warnings('Şanlıurfa Arkeoloji ve Mozaik Müzesi, Şanlıurfa')
    assert 'gorsel_aciklama_olabilir' in candidate_review_warnings('Banyoles Bölge Arkeoloji Müzesi')
    assert is_visual_caption("Görsel 2.10: Sevr Antlaşması'nı imzalayan heyet")
    assert is_visual_caption("Görsel 4 Üniversite binası, Ankara")
    assert is_visual_caption("Tekerlekli at modeli (yaklaşık MÖ VI. yüzyıl)")
    assert not is_visual_caption(
        "Sevr Antlaşması sürecinde kararlar San Remo Konferansı'nda belirlendi. "
        "Osmanlı heyeti Paris'e gönderildi (Görsel 2.10)."
    )
    assert candidate_review_warnings(
        "Sevr Antlaşması sürecinde kararlar San Remo Konferansı'nda belirlendi. "
        "Osmanlı heyeti Paris'e gönderildi (Görsel 2.10)."
    ) == []
    assert candidate_review_warnings('Tarım toplumsal yaşamda iş bölümünün gelişmesine katkı sağladı.') == []


@pytest.mark.skipif(not BOOK_12.is_file(), reason="Local MEB 12th-grade source not installed")
def test_12th_grade_lesson_paragraph_with_figure_reference_is_not_caption():
    import pymupdf

    from app.history_rag import _clean, build_index, is_visual_caption, source_review_recommendation

    with pymupdf.open(BOOK_12) as pdf:
        blocks = pdf[77].get_text("dict")["blocks"]
    block_texts = [
        _clean(" ".join(span["text"] for line in block.get("lines", []) for span in line["spans"]))
        for block in blocks if block.get("type") == 0
    ]
    paragraph = next(
        text for text in block_texts
        if "Paris Barış Konferansı" in text and "San Remo Konferansı" in text
    )
    assert "(Görsel 2.10)" in paragraph
    assert not is_visual_caption(paragraph)
    assert source_review_recommendation(paragraph)["decision"] != "do_not_use"

    index = build_index(BOOK_12)
    candidate = next(chunk for chunk in index["chunks"] if "San Remo Konferansı" in chunk["text"])
    assert candidate["page"] == 78
    assert candidate["quality"]["text_quality"] == "clean"
    assert "(Görsel 2.10)" in candidate["text"]


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


def test_short_fact_atom_keeps_adjacent_heading_and_rejects_caption():
    from app.history_rag import evidence_atoms

    blocks = [
        {"text": "ÜNİVERSİTE REFORMU (1933)", "bbox": [36, 649, 186, 663],
         "layout": {"first_line_is_title": True}},
        {"text": "İsviçreli bilim insanı Albert Malche’nin raporu doğrultusunda yükseköğretimde reform yapılmıştır.",
         "bbox": [36, 667, 436, 681], "layout": {"first_line_is_title": False}},
        {"text": "Görsel 4: Üniversite binası, Ankara", "bbox": [36, 690, 330, 704],
         "layout": {"first_line_is_title": False}},
    ]

    atoms, _ = evidence_atoms(
        blocks, checksum="source", page_number=205, page_height=780,
        section={"id": "summary.63", "title": "Atatürk Dönemi’nde Yapılan İnkılaplar"},
    )

    assert len(atoms) == 1
    assert atoms[0]["heading"] == "ÜNİVERSİTE REFORMU (1933)"
    assert atoms[0]["extraction_method"] == "adjacent_heading_plus_fact"
    assert "Albert Malche" in atoms[0]["text"]


def test_atom_joins_only_same_column_unfinished_paragraph_continuation():
    from app.history_rag import evidence_atoms

    blocks = [
        {"text": "• TBMM’de tek bir siyasi partinin bulunması demokrasiye uygun değildi ve 1929 Dünya",
         "bbox": [36, 477.76, 519.28, 510.47], "layout": {"first_line_is_title": False}},
        {"text": "Ekonomik Buhranı nedeniyle yeni bir parti kurma düşüncesi doğdu.",
         "bbox": [36, 508.73, 519.28, 534.46], "layout": {"first_line_is_title": False}},
        {"text": "• Ayrı bir liste maddesi kendi tarihsel nedenini ve sonucunu ayrıca açıklar.",
         "bbox": [36, 540, 519.28, 555], "layout": {"first_line_is_title": False}},
    ]

    atoms, _ = evidence_atoms(
        blocks, checksum="source", page_number=211, page_height=780,
        section={"id": "summary.1", "title": "İç politika"},
    )

    assert len(atoms) == 2
    joined = atoms[0]
    assert "1929 Dünya Ekonomik Buhranı" in joined["text"]
    assert joined["extraction_method"] == "standalone_fact_continuation"
    assert len(joined["source_segments"]) == 2
    assert "Ayrı bir liste" not in joined["text"]


def test_atom_rejects_repeated_page_furniture():
    from app.history_rag import _atom_candidate

    assert not _atom_candidate("TYT-AYT TYT-AYT TYT-AYT", [36, 120, 220, 140], 780)


def test_atom_rejects_long_uppercase_section_heading():
    from app.history_rag import _atom_candidate

    heading = "TÜRKISTAN’DAN TÜRKIYE’YE UZANAN SÜREÇTE MEYDANA GELEN ÖNEMLI ASKERÎ MÜCADELELER 1.1."
    assert not _atom_candidate(heading, [40, 120, 480, 170], 780)
