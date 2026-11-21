from app.pipeline.assemble_qlora_external_screen import build


def test_assembles_external_screen_without_inventing_first_token_latency():
    pack = {"schema": "eristem-qlora-synthetic-behavior-review-pack-v1", "candidate": "adapter",
            "source_report_sha256": "a" * 64, "records": [{"id": "synthetic-01", "case": "soruyu_anlama",
            "response": "Kanıttaki ipucu ne?", "evidence_available": True}]}
    review = {"schema": "deepseek-qlora-synthetic-output-review-v1", "candidate": "adapter", "source_report_sha256": "a" * 64,
              "reviews": [{"id": "synthetic-01", "source_external_claim": False, "wrong_source_attribution": False}]}
    paired = {"status": "completed", "paired": {"adapter": {"results": [{"case": "soruyu_anlama", "reply_preview": "Kanıttaki ipucu ne?", "seconds": 0.42}]}}}
    result = build(pack, review, paired)
    assert result["semantic_label_provenance"] == "external_ai_screen"
    assert result["records"][0]["first_token_ms"] is None
    assert result["records"][0]["full_response_ms"] == 420.0
