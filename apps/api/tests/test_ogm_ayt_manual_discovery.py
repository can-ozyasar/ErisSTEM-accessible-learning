from app.pipeline.ogm_ayt_manual_discovery import build


def test_manual_review_passages_are_discoverable_only_in_private_queue():
    transcript = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
                  "rows": [{"candidate_id": "question-1", "topic": "Millî Mücadele",
                            "transcription_status": "private_teacher_review_required",
                            "question": {"stem": "Teşkilat-ı Esasiye Kanunu hangi sistemle ilgilidir?",
                                         "choices": [{"label": "A", "text": "Meclis hükümeti"}]}}]}
    old = {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "q",
           "corpus_checksum": "c", "proposals": [{"candidate_id": "question-1",
           "suggestions": [{"source_checksum": "s", "chunk_id": "old"}]}]}
    def chunk(chunk_id, decision, text):
        return {"id": chunk_id, "page": 2, "bbox": [10, 10, 100, 40],
                "section_title": "MİLLÎ MÜCADELE", "text": text,
                "pre_review": {"decision": decision, "reasons": ["baglam_kontrolu_gerekli"]},
                "quality": {"warnings": []}}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{
        "grade": 12, "source_checksum": "s", "source_name": "book.pdf", "index": {"chunks": [
            chunk("old", "review_for_approval", "Teşkilat-ı Esasiye Kanunu"),
            chunk("manual", "manual_review", "Teşkilat-ı Esasiye Kanunu meclis hükümeti sistemini kabul etti."),
        ]}}]}
    result = build(transcript, old, corpus)
    assert result["proposals"][0]["suggestions"][0]["chunk_id"] == "manual"
    assert result["proposals"][0]["suggestions"][0]["pre_review_decision"] == "manual_review"
    assert result["proposals"][0]["suggestions"][0]["review_status"] == "private_pdf_discovery_only"
    assert not result["runtime_enabled"]
    assert not result["qlora_enabled"]
