import json
from pathlib import Path

import pytest

from app.ayt_knowledge_graph import (
    AudioCache,
    DialogueStage,
    Edge,
    HistoricalNode,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    NodeMetadata,
    NodeType,
    QuestionChoice,
    QuestionItem,
    RelationType,
    RetrievalGold,
    SocraticTutorOrchestrator,
    TutorDialogueState,
    WeightedGraphSearch,
    evaluate_retrieval,
    example_graph_payload,
)
from app.ayt_local_runtime import LocalHTTPLLM, load_approved_graph


def graph() -> KnowledgeGraph:
    return KnowledgeGraph(
        corpus_checksum="0123456789abcdef0123456789abcdef",
        nodes=[
            HistoricalNode(id="topic", node_type=NodeType.TOPIC, label="Millî Mücadele", approved=True,
                           metadata=NodeMetadata(source_ids=["src-topic"], node_weight=.8)),
            HistoricalNode(id="tbmm", node_type=NodeType.KURUM_DEVLET, label="TBMM'nin açılması",
                           description="Ulusal egemenlik", approved=True,
                           metadata=NodeMetadata(years=[1920], concepts=["ulusal egemenlik"], source_ids=["src-tbmm"])),
            HistoricalNode(id="unapproved", node_type=NodeType.OLAY_SAVAS, label="Taslak", approved=False),
        ],
        edges=[Edge(id="e01", from_node="tbmm", to_node="topic", relation=RelationType.ALT_KONUSUDUR,
                    quote="TBMM'nin açılması Millî Mücadele ile ilişkilidir.", source_ids=["src-tbmm"], approved=True)],
    )


def question() -> QuestionItem:
    return QuestionItem(id="q-1", stem="Ulusal egemenlikle ilgili gelişmeyi bul.", topic="Millî Mücadele",
                        choices=[QuestionChoice(label="A", text="TBMM'nin açılması"),
                                 QuestionChoice(label="B", text="Başka bir seçenek")])


def test_graph_validates_and_serializes_example():
    payload = example_graph_payload()
    parsed = KnowledgeGraph.model_validate(payload["graph"])
    assert parsed.approved_edges()[0].relation == RelationType.ALT_KONUSUDUR
    assert payload["dialogue_state"]["can_reveal_explanation"] is False


def test_versioned_json_schema_artifact_covers_runtime_models():
    schema_path = Path(__file__).parents[3] / "docs" / "ayt-runtime-schemas.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ayt-history-runtime-schemas-v1"
    assert payload["knowledge_graph"]["$defs"]
    assert "properties" in payload["question_item"]
    assert "properties" in payload["tutor_dialogue_state"]


def test_search_returns_components_and_ignores_unapproved_nodes():
    result = WeightedGraphSearch(graph()).search(question(), top_k=3)
    assert {hit.node_id for chain in result.chains for hit in chain.hits}.issubset({"topic", "tbmm"})
    hit = next(hit for chain in result.chains for hit in chain.hits if hit.node_id == "tbmm")
    assert 0 <= hit.cosine_score <= 1 and 0 <= hit.metadata_score <= 1
    assert hit.supporting_edge_ids == ["e01"] or hit.hop == 0


def test_embedding_search_keeps_lexical_fallback_for_unembedded_atoms():
    result = WeightedGraphSearch(graph(), embed=lambda _text: [1.0, 0.0]).search(question(), top_k=3)
    assert any(hit.node_id == "tbmm" for chain in result.chains for hit in chain.hits)


def test_search_weights_are_explicit_and_normalized():
    with pytest.raises(ValueError):
        WeightedGraphSearch(graph(), weights={"cosine": 1.0})
    search = WeightedGraphSearch(graph(), weights={"cosine": .5, "metadata": .2,
                                                   "node_weight": .1, "graph": .2})
    assert search.weights["cosine"] == .5


def test_retrieval_metrics_score_relevant_rank_and_abstention():
    result = WeightedGraphSearch(graph()).search(question(), top_k=3)
    metrics = evaluate_retrieval([(result, [RetrievalGold(choice_label="A", relevant_node_ids=["tbmm"]),
                                            RetrievalGold(choice_label="B", should_abstain=True)])])
    assert metrics.query_count == 2
    assert metrics.recall_at_1 >= 0
    assert 0 <= metrics.mrr_at_3 <= 1
    assert 0 <= metrics.ndcg_at_3 <= 1
    assert 0 <= metrics.wrong_evidence_rate <= 1


def test_graph_rejects_approved_edge_to_unapproved_node():
    with pytest.raises(ValueError):
        KnowledgeGraph(
            corpus_checksum="0123456789abcdef0123456789abcdef",
            nodes=[HistoricalNode(id="a", node_type=NodeType.TOPIC, label="A", approved=True,
                                  metadata=NodeMetadata(source_ids=["src-a"])),
                   HistoricalNode(id="b", node_type=NodeType.TOPIC, label="B")],
            edges=[Edge(id="e", from_node="a", to_node="b", relation=RelationType.ALT_KONUSUDUR,
                        quote="A, B'nin alt konusudur.", source_ids=["src-a"], approved=True)],
        )


def test_builder_keeps_unreviewed_corpus_nodes_out_of_runtime():
    corpus = {
        "schema": "multi-history-rag-v1", "corpus_checksum": "0123456789abcdef0123456789abcdef",
        "books": [{"source_name": "meb.pdf", "source_checksum": "abcdef0123456789abcdef0123456789",
                   "index": {"sections": [{"id": "2.1", "title": "Millî Mücadele"}],
                              "chunks": [{"id": "c1", "section_id": "2.1", "section_title": "Millî Mücadele",
                                          "text": "1920 yılında TBMM açıldı.",
                                          "quality": {"quality_checked": True},
                                          "pre_review": {"decision": "review_for_approval"}}]}}],
    }
    built = KnowledgeGraphBuilder(corpus["corpus_checksum"]).add_corpus(corpus).build()
    assert built.approved_nodes() == []
    assert len(built.nodes) == 3 and len(built.edges) == 2


class FakeLLM:
    captured_prompt = ""

    def generate(self, system_prompt, user_prompt, *, max_tokens):
        assert "cevap anahtarını söyleme" in system_prompt
        assert "TBMM" in user_prompt
        FakeLLM.captured_prompt = user_prompt
        return "Kaynakta geçen hangi ayrıntı bu gelişmeyle ilişkilidir?"


class FakeTTS:
    def synthesize(self, text, *, output_path):
        output_path.write_bytes(text.encode("utf-8"))


def test_orchestrator_uses_content_addressed_audio_cache(tmp_path: Path):
    orchestrator = SocraticTutorOrchestrator(WeightedGraphSearch(graph()), FakeLLM(),
                                              AudioCache(tmp_path, "tts-v5"), FakeTTS())
    state = TutorDialogueState(session_id="session-1", question_id="q-1")
    next_state, text, audio = orchestrator.start(question(), state)
    assert next_state.retrieved_node_ids
    assert text.endswith("?")
    assert audio and all(path.is_file() for path in audio)
    _, _, audio_again = orchestrator.start(question(), state)
    assert [path.name for path in audio] == [path.name for path in audio_again]
    prewarmed = orchestrator.audio_cache.prewarm(["Soru hazır.", "Soru hazır."], FakeTTS())
    assert list(prewarmed) == ["Soru hazır."]
    assert next_state.stage == DialogueStage.HATIRLAMAYI_ORTAYA_CIKARMA
    assert set(orchestrator.last_timings) == {"retrieval", "first_token", "llm", "tts", "total"}
    assert orchestrator.last_timings["total"] >= 0
    assert "Ulusal egemenlik" in FakeLLM.captured_prompt
    assert "Kaynak kimliği" in FakeLLM.captured_prompt


def test_orchestrator_falls_back_when_local_llm_is_unavailable(tmp_path: Path):
    class BrokenLLM:
        def generate(self, *_args, **_kwargs):
            raise RuntimeError("service down")

    orchestrator = SocraticTutorOrchestrator(WeightedGraphSearch(graph()), BrokenLLM(),
                                              AudioCache(tmp_path, "tts-v5"), FakeTTS())
    _, text, _ = orchestrator.start(question())
    assert text.endswith("?")
    assert "cevap" not in text.casefold()


def test_final_stage_uses_only_verified_server_text(tmp_path: Path):
    class MustNotRun:
        def generate(self, *_args, **_kwargs):
            raise AssertionError("final aşamada LLM çağrılmamalı")

    orchestrator = SocraticTutorOrchestrator(WeightedGraphSearch(graph()), MustNotRun(),
                                              AudioCache(tmp_path, "tts-v5"), FakeTTS())
    state = TutorDialogueState(session_id="session-1", question_id="q-1",
                               stage=DialogueStage.GEREKCELI_ACIKLAMA)
    next_state, text, _ = orchestrator.start(question(), state,
                                              verified_explanation="Doğrulanmış açıklama.")
    assert text == "Doğrulanmış açıklama."
    assert next_state.can_reveal_explanation


def test_local_llm_adapter_sends_bounded_prompt_and_parses_text(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"text":"Kaynakta hangi ayrinti soruyu acikliyor?"}'

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["payload"] = request.data
        captured["url"] = request.full_url
        return Response()

    monkeypatch.setattr("app.ayt_local_runtime.urlopen", fake_urlopen)
    text = LocalHTTPLLM("http://tutor-llm:8001/generate").generate("Kural", "Soru", max_tokens=72)
    assert text.startswith("Kaynakta")
    assert captured["url"].endswith("/generate")
    assert "Kural" in captured["payload"].decode("utf-8")
    assert captured["timeout"] == 8


def test_local_llm_adapter_bounds_service_payload(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"text":"Kisa soru?"}'

    def fake_urlopen(request, timeout):
        captured["size"] = len(request.data)
        return Response()

    monkeypatch.setattr("app.ayt_local_runtime.urlopen", fake_urlopen)
    LocalHTTPLLM("http://tutor-llm:8001/generate").generate("kural " * 2000,
                                                               "kanıt " * 3000, max_tokens=72)
    assert captured["size"] < 9000


def test_local_llm_requires_http_endpoint():
    with pytest.raises(ValueError):
        LocalHTTPLLM("https://hosted.example/generate")


def test_graph_loader_fails_closed_without_approved_surface(tmp_path: Path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({
        "schema": "ayt-history-knowledge-graph-v1",
        "corpus_checksum": "0123456789abcdef0123456789abcdef",
        "nodes": [], "edges": []
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="onaylı_ayt_grafi_yok"):
        load_approved_graph(path)

