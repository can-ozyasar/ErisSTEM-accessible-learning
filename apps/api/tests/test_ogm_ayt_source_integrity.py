import hashlib

import pymupdf
import pytest

from app.pipeline.ogm_ayt_source_integrity import inspect


def test_pdf_crop_and_corpus_revision_are_checked(tmp_path):
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Lozan Antlasmasi ile ilgili kaynak metni.")
    source = tmp_path / "source.pdf"
    pdf.save(source)
    pdf.close()
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    box = [70, 60, 400, 85]
    chunk = {"id": "chunk-one", "text": "Lozan Antlasmasi ile ilgili kaynak metni.",
             "page": 1, "bbox": box, "section_title": "Lozan"}
    corpus = {"corpus_checksum": "corpus-v1", "books": [
        {"source_checksum": checksum, "source_name": source.name,
         "index": {"chunks": [chunk]}}]}
    queue = {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "questions-v1",
             "corpus_checksum": "corpus-v1", "proposals": [{"candidate_id": "q1",
             "suggestions": [{**chunk, "chunk_id": chunk["id"],
                              "source_checksum": checksum, "source_name": source.name}]}]}
    result = inspect(queue, corpus, tmp_path)
    assert result["card_count"] == 1
    assert result["low_similarity_count"] == 0
    assert not result["runtime_enabled"]
    discovery = inspect({**queue, "schema": "ogm-ayt-manual-source-discovery-v1"},
                        corpus, tmp_path)
    assert discovery["source_queue_schema"] == "ogm-ayt-manual-source-discovery-v1"
    changed_card = {**queue["proposals"][0]["suggestions"][0], "text": "Uydurma tarihsel iddia"}
    with pytest.raises(ValueError, match="kaynak parçası"):
        inspect({**queue, "proposals": [{"candidate_id": "q1", "suggestions": [changed_card]}]},
                corpus, tmp_path)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        inspect(queue, corpus, tmp_path)
