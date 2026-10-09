from app.pipeline.tts_quality import TtsCandidateManifest, TtsGoldManifest, evaluate_tts_candidate


def gold(count: int = 1) -> TtsGoldManifest:
    return TtsGoldManifest.model_validate({
        "schema_version": "tts-gold-v1",
        "items": [{"id": f"u-{number}", "kind": "formula", "expected_spoken_text": "x karesi eşittir dört", "critical_tokens": ["karesi", "eşittir"]} for number in range(count)],
    })


def test_tts_report_never_exposes_private_reference_or_candidate_text():
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": "u-0", "observed_spoken_text": "x karesi eşittir dört"}],
    })

    report = evaluate_tts_candidate(gold(), candidate)

    assert report["contains_document_content"] is False
    assert report["evaluation_scope"] == "calibration"
    assert report["pronunciation_accuracy"] == report["critical_token_accuracy"] == 1
    assert "expected_spoken_text" not in str(report)
    assert report["decision"] == "tts-candidate-blocked"


def test_tts_gate_blocks_a_wrong_critical_math_token_even_with_adequate_sample_count():
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": f"u-{number}", "observed_spoken_text": "x küpü eşittir dört"} for number in range(50)],
    })

    report = evaluate_tts_candidate(gold(50), candidate)

    assert report["critical_token_accuracy"] < 1
    assert report["decision"] == "tts-candidate-blocked"


def test_tts_gate_can_qualify_only_a_safe_content_kind_for_listener_review():
    items = []
    results = []
    for kind in ("text", "formula"):
        for number in range(25):
            item_id = f"{kind}-{number}"
            items.append({
                "id": item_id,
                "kind": kind,
                "expected_spoken_text": "x karesi eşittir dört",
                "critical_tokens": ["karesi", "eşittir"],
            })
            results.append({
                "id": item_id,
                "observed_spoken_text": (
                    "x karesi eşittir dört" if kind == "text" else "x küpü eşittir dört"
                ),
            })
    report = evaluate_tts_candidate(
        TtsGoldManifest.model_validate({"schema_version": "tts-gold-v1", "items": items}),
        TtsCandidateManifest.model_validate({
            "schema_version": "tts-candidate-v1", "candidate": "voice-a", "results": results,
        }),
    )

    assert report["quality_policy_version"] == "tts-quality-policy-v3"
    assert report["eligible_kinds"] == ["text"]
    assert report["kind_results"]["formula"]["automatic_screen"] == "blocked"
    assert report["decision"] == "tts-candidate-kind-limited-listener-study-required"


def test_tts_metric_ignores_unspoken_punctuation_but_keeps_critical_words():
    reference = TtsGoldManifest.model_validate({
        "schema_version": "tts-gold-v1",
        "items": [{"id": "u-1", "kind": "table", "expected_spoken_text": "İkinci sütun: birleşim.", "critical_tokens": ["İkinci", "birleşim"]}],
    })
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": "u-1", "observed_spoken_text": "İkinci sütun birleşim"}],
    })
    report = evaluate_tts_candidate(reference, candidate)
    assert report["pronunciation_accuracy"] == 1
    assert report["critical_token_accuracy"] == 1


def test_tts_gold_rejects_a_critical_word_missing_from_reference():
    import pytest

    with pytest.raises(ValueError, match="critical tokens must occur"):
        TtsGoldManifest.model_validate({
            "schema_version": "tts-gold-v1",
            "items": [{"id": "u-1", "kind": "formula", "expected_spoken_text": "x artı y", "critical_tokens": ["eksi"]}],
        })


def test_source_bound_release_scope_is_explicit_not_inferred():
    reference = gold()
    assert reference.evaluation_scope == "calibration"
    release = TtsGoldManifest.model_validate(reference.model_dump() | {"evaluation_scope": "source-bound-release"})
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": "u-0", "observed_spoken_text": "x karesi eşittir dört"}],
    })
    assert evaluate_tts_candidate(release, candidate)["evaluation_scope"] == "source-bound-release"
