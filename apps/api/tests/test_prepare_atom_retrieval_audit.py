from app.pipeline.prepare_atom_retrieval_audit import need_plan


def test_need_plan_keeps_question_intent_without_choices():
    plan = need_plan(
        "Atatürkçülük ve Türk İnkılabı",
        "16 Ocak 1932'de Prof. Dr. Albert Malche hangi reform için rapor hazırlamıştır?",
    )

    assert plan["relation_intent"] == "fact"
    assert "Albert Malche" in plan["entity_hints"]
    assert "üniversite" not in plan["retrieval_query"].casefold()
