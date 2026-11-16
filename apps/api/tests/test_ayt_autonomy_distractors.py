"""A generated multiple-choice item must have only one graph-supported option."""

from app.ayt_autonomy import (
    GeneratedDraftQualityGate,
    GraphToQuestionGenerator,
    HistoryTeacherValidatorAgent,
    QuestionAnalyzerAndEliminator,
    QuestionAnalyzerAndValidator,
)
from app.ayt_knowledge_graph import (
    Edge,
    HistoricalNode,
    KnowledgeGraph,
    NodeMetadata,
    NodeType,
    QuestionChoice,
    QuestionItem,
    RelationType,
    WeightedGraphSearch,
)

CHECKSUM = "a" * 64


def _node(name: str, node_type: NodeType = NodeType.KAVRAM_ILKE) -> HistoricalNode:
    return HistoricalNode(id=name, node_type=node_type, label=name.replace("_", " ").title(),
                          metadata=NodeMetadata(source_ids=["source-1"]), approved=True)


def _edge(name: str, subject: str, target: str, relation: RelationType) -> Edge:
    return Edge(id=f"edge:{name}", from_node=subject, to_node=target, relation=relation,
                quote="Kaynağın açıkça kurduğu tarihsel ilişki bu cümlede yer alır.",
                source_ids=["source-1"], source_checksum=CHECKSUM,
                page=1, bbox=[1, 1, 100, 30], approved=True)


def test_second_supported_target_cannot_be_a_distractor():
    target_names = ["ilk_neden", "ikinci_neden", "ucuncu_neden", "dorduncu_neden",
                    "besinci_neden", "altinci_neden", "yedinci_neden"]
    nodes = [_node("ana_olay"), _node("diger_olay"),
             *(_node(name) for name in target_names)]
    edges = [_edge("e1", "ana_olay", "ilk_neden", RelationType.SEBEBIDIR),
             _edge("e2", "ana_olay", "ikinci_neden", RelationType.SEBEBIDIR),
             *(_edge(f"e{index}", "diger_olay", name, RelationType.SEBEBIDIR)
               for index, name in enumerate(target_names[2:], 3))]
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    drafts = GraphToQuestionGenerator(graph).generate(limit=10)
    for draft in drafts:
        if draft.supporting_edge_id == "edge:e1":
            choices = {choice.text for choice in draft.runtime_question.choices}
            assert "Ilk Neden" in choices
            assert "Ikinci Neden" not in choices
            break
    else:
        raise AssertionError("Beklenen kaynak bağlı soru üretilmedi")


def test_generator_honors_source_checksum_and_page_scope():
    nodes = [_node("ana_olay"), *(_node(f"neden_{i}") for i in range(6))]
    edges = [_edge(f"e{i}", "ana_olay", f"neden_{i}", RelationType.SEBEBIDIR)
             for i in range(6)]
    edges[0] = edges[0].model_copy(update={"source_checksum": "b" * 64, "page": 5})
    edges[1] = edges[1].model_copy(update={"page": 50})
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    generator = GraphToQuestionGenerator(graph, source_checksum=CHECKSUM,
                                         page_ranges=[(1, 10)])
    assert {edge.id for edge in generator.edges} == {f"edge:e{i}" for i in range(2, 6)}


def test_temporal_choices_only_use_source_backed_peer_years():
    years = ["1901", "1903", "1907", "1911", "1919"]
    nodes = [_node(f"olay_{i}") for i in range(5)]
    nodes += [_node(year, NodeType.DONEM_KRONOLOJI) for year in years]
    edges = [
        _edge(f"year-{i}", f"olay_{i}", year, RelationType.DONEMINDE_OLMUSTUR)
        .model_copy(update={"extraction_method": "source_verbatim_named_event_year_occurred"})
        for i, year in enumerate(years)
    ]
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    drafts = GraphToQuestionGenerator(graph).generate(limit=10)
    assert len(drafts) == 5
    assert all({choice.text for choice in draft.runtime_question.choices} == set(years)
               for draft in drafts)

    split_edges = [edge.model_copy(update={"page": 11 if index >= 3 else 1})
                   for index, edge in enumerate(edges)]
    split_graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=split_edges)
    assert GraphToQuestionGenerator(split_graph, page_ranges=[(1, 5), (10, 15)]).generate(limit=10) == []


def test_generator_deduplicates_same_event_year_across_source_chunks():
    years = ["1901", "1903", "1907", "1911", "1919"]
    nodes = [_node(f"olay_{i}") for i in range(5)]
    nodes += [_node(year, NodeType.DONEM_KRONOLOJI) for year in years]
    edges = [
        _edge(f"year-{i}", f"olay_{i}", year, RelationType.DONEMINDE_OLMUSTUR)
        .model_copy(update={"extraction_method": "source_verbatim_named_event_year_occurred"})
        for i, year in enumerate(years)
    ]
    duplicate = edges[0].model_copy(update={"id": "edge:duplicate", "source_ids": ["other-source"]})
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=[*edges, duplicate])
    generator = GraphToQuestionGenerator(graph)
    drafts = generator.generate(limit=10)
    fingerprints = [(draft.runtime_question.question_terms[0],
                     next(choice.text for choice in draft.runtime_question.choices
                          if choice.label == draft.answer_label)) for draft in drafts]
    assert len(fingerprints) == len(set(fingerprints)) == 5
    assert generator.semantic_duplicates_collapsed == 1


def test_generic_relation_and_answer_leak_are_rejected():
    names = ["ilk_neden", "ikinci_neden", "ucuncu_neden", "dorduncu_neden",
             "besinci_neden", "altinci_neden"]
    nodes = [_node("ana_olay"), _node("diger_olay"), *(_node(name) for name in names)]
    edges = [_edge("e0", "ana_olay", names[0], RelationType.SEBEBIDIR)]
    edges += [_edge(f"e{i}", "diger_olay", name, RelationType.SEBEBIDIR)
              for i, name in enumerate(names[1:], 1)]
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    draft = GraphToQuestionGenerator(graph).generate(limit=1)[0]
    answer = next(choice.text for choice in draft.runtime_question.choices
                  if choice.label == draft.answer_label)
    assert answer not in draft.runtime_question.question_terms
    assert draft.runtime_question.question_terms == ["Ana Olay"]
    leaky = draft.model_copy(update={
        "runtime_question": draft.runtime_question.model_copy(update={
            "stem": f"Kaynağa göre {answer} ile Ana Olay arasındaki ilişki hangisidir?",
        }),
    })
    issues = GeneratedDraftQualityGate().review(leaky).issues
    assert "answer_leaked_in_stem" in issues
    assert "unsupported_question_template" in issues


def test_actor_stem_with_finite_verb_is_rejected():
    names = [f"aktor_{i}" for i in range(6)]
    nodes = [_node("olay_kuruldu"), _node("diger_olay"), *(_node(name) for name in names)]
    edges = [_edge("actor-0", "olay_kuruldu", names[0], RelationType.AKTORUDUR)]
    edges += [_edge(f"actor-{i}", "diger_olay", name, RelationType.AKTORUDUR)
              for i, name in enumerate(names[1:], 1)]
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    draft = GraphToQuestionGenerator(graph).generate(limit=1)[0]
    assert "actor_stem_has_finite_verb" in GeneratedDraftQualityGate().review(draft).issues


def test_source_actor_relation_gets_spoken_endpoints_from_sentence():
    edge = _edge("actor", "olay", "aktor", RelationType.AKTORUDUR).model_copy(update={
        "quote": "İtilaf donanması, Osmanlı kuvvetleri tarafından durduruldu ve çekildi.",
    })
    phrases = GraphToQuestionGenerator._source_relation_phrases(edge)
    assert phrases == {
        "subject": "İtilaf donanması",
        "answer": "Osmanlı kuvvetleri",
        "action": "durduruldu ve çekildi",
    }


def test_source_relation_rejects_fragment_without_explicit_sentence_boundary():
    edge = _edge("actor", "olay", "aktor", RelationType.AKTORUDUR).model_copy(update={
        "quote": "İtilaf donanması, Osmanlı kuvvetleri tarafından durduruldu",
    })
    assert GraphToQuestionGenerator._source_relation_phrases(edge) is None


def test_teacher_candidate_requires_both_endpoints_in_verbatim_quote():
    names = [f"neden_{i}" for i in range(5)]
    nodes = [_node("ana_olay"), _node("diger_olay"), *(_node(name) for name in names)]
    edges = [_edge("e0", "ana_olay", names[0], RelationType.SEBEBIDIR)]
    edges += [_edge(f"e{i}", "diger_olay", name, RelationType.SEBEBIDIR)
              for i, name in enumerate(names[1:], 1)]
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=edges)
    draft = GraphToQuestionGenerator(graph).generate(limit=1)[0]
    assert HistoryTeacherValidatorAgent(graph).validate_generated_draft(draft).decision == "insufficient"

    labels = {node.id: node.label for node in nodes}
    supported = [edge.model_copy(update={
        "quote": f"{labels[edge.from_node]} ile {labels[edge.to_node]} açık bir ilişki içindedir."})
        for edge in edges]
    verified_graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=supported)
    verified_draft = GraphToQuestionGenerator(verified_graph).generate(limit=1)[0]
    assert HistoryTeacherValidatorAgent(verified_graph).validate_generated_draft(verified_draft).decision == "direct"


def test_eliminator_requires_question_and_choice_on_opposite_edge_endpoints():
    nodes = [_node("ana_olay"), _node("ilk_neden")]
    misleading = _edge("misleading", "ana_olay", "ilk_neden", RelationType.SEBEBIDIR)
    misleading = misleading.model_copy(update={
        "quote": "Ana Olay ile Ilk Neden ilişkilidir. Sakarya Savaşı 1921 yılında gerçekleşmiştir."})
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=nodes, edges=[misleading])
    analyzer = QuestionAnalyzerAndEliminator(WeightedGraphSearch(graph))
    assert not analyzer._edge_supports_choice([misleading.id], {"sakarya", "savaşı"}, {"1921"})

    valid_nodes = [_node("sakarya_savasi"), _node("1921", NodeType.DONEM_KRONOLOJI)]
    valid = _edge("valid", "sakarya_savasi", "1921", RelationType.DONEMINDE_OLMUSTUR)
    valid = valid.model_copy(update={"quote": "Sakarya Savasi 1921 yılında gerçekleşmiştir."})
    valid_graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=valid_nodes, edges=[valid])
    valid_analyzer = QuestionAnalyzerAndEliminator(WeightedGraphSearch(valid_graph))
    assert valid_analyzer._edge_supports_choice([valid.id], {"sakarya", "savasi"}, {"1921"})


def test_combined_analyzer_blocks_visual_choice_but_keeps_roman_premises():
    graph = KnowledgeGraph(corpus_checksum=CHECKSUM, nodes=[], edges=[])
    search = WeightedGraphSearch(graph)
    runner = QuestionAnalyzerAndValidator(search, graph)
    choices = [QuestionChoice(label=label, text=text) for label, text in zip(
        "ABCDE", ["I. öncül doğrudur", "II. öncül doğrudur", "I ve II", "Yalnız I", "Yalnız II"],
    )]
    question = QuestionItem(id="roman-premise", stem="I ve II öncüllerinden hangileri doğrudur?",
                            choices=choices)
    decision = runner.evaluate(question)
    assert decision.eligible
    assert "roman_numeral_premises" in decision.format_tags
    visual_choices = [QuestionChoice(label="A", text="İlk seçenek"),
                      QuestionChoice(label="B", text="Haritada gösterilen bölge")]
    visual = QuestionItem(id="visual-choice", stem="Which option follows from the question?",
                          choices=visual_choices)
    blocked = runner.evaluate(visual)
    assert not blocked.eligible
    assert blocked.scope_reasons == ["referenced_visual"]
    assert blocked.analysis is None
