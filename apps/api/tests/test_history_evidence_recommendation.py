from app.history_rag import recommend_evidence


def index():
    return {
        "sections": [{"id": "2.1", "title": "Tarım Devrimi’nin Etkileri"}],
        "chunks": [
            {"id": "exact", "section_id": "2.1", "section_title": "Tarım Devrimi’nin Etkileri", "page": 10,
             "text": "Çayönü yerleşiminde tarımsal üretim ve köy yaşamı görülür."},
            {"id": "topic", "section_id": "2.1", "section_title": "Tarım Devrimi’nin Etkileri", "page": 11,
             "text": "Tarım devrimi insanların yaşamını değiştirmiştir ve toplumlar büyümüştür."},
            {"id": "caption", "section_id": "2.1", "section_title": "Tarım Devrimi’nin Etkileri", "page": 12,
             "text": "Görsel 2: Çayönü Museum eserinin fotoğrafı."},
        ],
    }


def test_multisignal_engine_prefers_direct_evidence_and_explains_it():
    result = recommend_evidence(index(), "Çayönü'nde hangi yaşam biçimi görülür?", ["Tarım ve köy yaşamı"],
                                "Tarım Devrimi’nin Etkileri")
    assert result[0]["id"] == "exact"
    assert result[0]["review_recommendation"] == "review"
    assert "ayırt edici soru/şık terimi" in result[0]["reasons"]
    caption = next(item for item in result if item["id"] == "caption")
    assert caption["review_recommendation"] == "do_not_use_yet"
    assert "görsel açıklaması riski" in caption["reasons"]
