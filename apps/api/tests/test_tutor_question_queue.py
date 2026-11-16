from app.pipeline.tutor_question_queue import build


def _question(identifier: str, page: int, topic: str, issues=None, visuals=None):
    return {"question": {"id": identifier, "number": 1, "question_type": "multiple_choice", "source": {"page": page}, "visuals": visuals or [], "parts": []}, "issues": issues or []}


def test_queue_is_topic_balanced_and_content_free():
    book = {"source_checksum": "a" * 64, "page_contexts": {1: {"topic": "A", "test_number": 1}, 2: {"topic": "A", "test_number": 2}, 3: {"topic": "B", "test_number": 1}}, "questions": [_question("a1", 1, "A"), _question("a2", 2, "A"), _question("b1", 3, "B")]}
    queue = build(book, target=3)
    assert [row["question_id"] for row in queue["selected"]] == ["a1", "b1", "a2"]
    assert queue["question_text_exported"] is False
    assert "choices" not in str(queue)


def test_queue_excludes_unstable_layout_and_visual_questions():
    book = {"source_checksum": "a" * 64, "page_contexts": {1: {"topic": "A"}, 2: {"topic": "A"}}, "questions": [_question("bad", 1, "A", issues=["choices_incomplete_or_out_of_order"]), _question("visual", 2, "A", visuals=[{"id": "image"}])]}
    queue = build(book, target=2)
    assert queue["selected_count"] == 0
    assert queue["summary"]["needs_more_source_questions"] is True
    assert queue["summary"]["blocked_reasons"]["görsel_betimleme_gerekli"] == 1


def test_queue_keeps_text_blank_questions_and_rejects_visual_choice_references():
    blank = _question("blank", 1, "A")
    blank["question"]["question_type"] = "fill_in_the_blank"
    blank["question"]["parts"] = [{"text": "Boş bırakılan yere aşağıdakilerden hangisi gelir?"}]
    visual_choice = _question("choice-visual", 2, "A")
    visual_choice["question"]["choices"] = [{"label": "A", "text": "Haritada gösterilen bölge"}]
    book = {"source_checksum": "a" * 64, "page_contexts": {1: {"topic": "A"}, 2: {"topic": "A"}},
            "questions": [blank, visual_choice]}
    queue = build(book, target=2)
    assert queue["selected_count"] == 1
    assert queue["selected"][0]["question_id"] == "blank"
    assert queue["summary"]["blocked_reasons"]["görsel_betimleme_gerekli"] == 1


def test_queue_normalizes_topic_spelling_and_rejects_test_name_as_topic():
    book = {"source_checksum": "a" * 64, "page_contexts": {1: {"topic": "Eski Çağ’da Hukuk"}, 2: {"topic": "Eski Çağ'da Hukuk"}, 3: {"topic": "Ünite Tarama Testi"}}, "questions": [_question("one", 1, ""), _question("two", 2, ""), _question("generic", 3, "")]}
    queue = build(book, target=3)
    assert queue["selected_count"] == 2
    assert list(queue["summary"]["selected_by_topic"].values()) == [2]
    assert queue["summary"]["blocked_reasons"]["konu_başlığı_yetersiz"] == 1
