from types import SimpleNamespace

from app.pipeline.prepare_ayt_history_v5_audio_manifest import (
    INTERFACE_TEXTS,
    build,
    kaggle_synthesis_view,
)


def test_static_v5_manifest_binds_question_units_and_keeps_runtime_closed():
    question = SimpleNamespace(
        id="authoring-001",
        spoken_question="Milattan önce 546 yılında gerçekleşen olay hangisidir?",
        choices=["Birinci seçenek", "İkinci seçenek", "Üçüncü seçenek", "Dördüncü seçenek", "Beşinci seçenek"],
    )
    payload = build(SimpleNamespace(pack_id="ayt-history-v1", questions=[question]), "a" * 64)
    assert payload["runtime_enabled"] is False
    assert payload["requires_listener_review"] is True
    assert payload["summary"]["static_units"] == 6 + len(INTERFACE_TEXTS)
    stem = next(item for item in payload["items"] if item["id"] == "authoring-001:stem")
    assert stem["spoken_text"].startswith("birinci soru.")
    assert stem["contains_digits"] is False
    assert {item["id"] for item in payload["items"] if item["kind"] == "question"} == {
        "authoring-001:stem", "authoring-001:choice-a", "authoring-001:choice-b",
        "authoring-001:choice-c", "authoring-001:choice-d", "authoring-001:choice-e",
    }


def test_kaggle_view_withholds_digit_text_but_preserves_package_binding_and_ids():
    question = SimpleNamespace(
        id="authoring-002",
        spoken_question="Tarihî gelişme hangi dönemde yaşanmıştır?",
        choices=["Seçenek 1", "İkinci seçenek", "Üçüncü seçenek", "Dördüncü seçenek", "Beşinci seçenek"],
    )
    source = build(SimpleNamespace(pack_id="ayt-history-v1", questions=[question]), "b" * 64)

    minimized = kaggle_synthesis_view(source)

    assert minimized["pack_checksum"] == "b" * 64
    assert minimized["summary"]["source_static_units"] == 6 + len(INTERFACE_TEXTS)
    assert minimized["summary"]["units_with_digits_withheld"] == 1
    assert minimized["summary"]["static_units"] == 5 + len(INTERFACE_TEXTS)
    assert len(minimized["items"]) == 5 + len(INTERFACE_TEXTS)
    assert all(not item["contains_digits"] for item in minimized["items"])
    assert {item["id"] for item in minimized["items"] if item["kind"] == "question"} == {
        "authoring-002:stem", "authoring-002:choice-b", "authoring-002:choice-c",
        "authoring-002:choice-d", "authoring-002:choice-e",
    }
    assert minimized["runtime_enabled"] is False
    assert minimized["requires_listener_review"] is True
