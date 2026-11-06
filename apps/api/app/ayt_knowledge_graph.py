"""Deterministic, source-bound AYT History knowledge graph and tutor runtime.

The module is intentionally self contained.  It does not download a model or
call a hosted API: the application supplies an embedding function, a local
LLM adapter and the project's fine-tuned TTS synthesizer.  Unapproved nodes or
edges can be stored for review, but they never enter retrieval or prompts.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class NodeType(str, Enum):
    UNIT = "UNIT"
    TOPIC = "TOPIC"
    SUBTOPIC = "SUBTOPIC"
    OLAY_SAVAS = "OLAY_SAVAS"
    ANTLASMA_BELGE = "ANTLASMA_BELGE"
    KISI_AKTOR = "KISI_AKTOR"
    KURUM_DEVLET = "KURUM_DEVLET"
    KAVRAM_ILKE = "KAVRAM_ILKE"
    DONEM_KRONOLOJI = "DONEM_KRONOLOJI"
    YER_COGRAFYA = "YER_COGRAFYA"
    CEPHE = "CEPHE"


class RelationType(str, Enum):
    ALT_KONUSUDUR = "ALT_KONUSUDUR"
    SEBEBIDIR = "SEBEBIDIR"
    SONUCUDUR = "SONUCUDUR"
    AMACIDIR = "AMACIDIR"
    DONEMINDE_OLMUSTUR = "DONEMINDE_OLMUSTUR"
    KRONOLOJIK_SONRASIDIR = "KRONOLOJIK_SONRASIDIR"
    AKTORUDUR = "AKTORUDUR"
    COGRAFYASIDIR = "COGRAFYASIDIR"
    KAPSAMINDADIR = "KAPSAMINDADIR"
    ILKESIYLE_ILISKILIDIR = "ILKESIYLE_ILISKILIDIR"
    CELISIR_TAVIZDIR = "CELISIR_TAVIZDIR"
    BENZERIDIR_PARALELDIR = "BENZERIDIR_PARALELDIR"
    IMZALAYANIDIR = "IMZALAYANIDIR"
    UYGULANDIGI_YERDIR = "UYGULANDIGI_YERDIR"


class QuestionRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXT = "CONTEXT"


class DialogueStage(str, Enum):
    SORU_ANALIZI = "soru_analizi"
    HATIRLAMAYI_ORTAYA_CIKARMA = "hatirlamayi_ortaya_cikarma"
    KANITLA_BAG_KURMA = "kanitla_bag_kurma"
    SIK_ELEMESI = "sik_elemesi"
    OGRENCI_YANITI = "ogrenci_yaniti"
    GEREKCELI_ACIKLAMA = "gerekceli_aciklama"


class NodeMetadata(StrictModel):
    aliases: list[str] = Field(default_factory=list, max_length=32)
    years: list[int] = Field(default_factory=list, max_length=12)
    century: int | None = Field(default=None, ge=-50, le=30)
    period: str | None = Field(default=None, max_length=120)
    persons: list[str] = Field(default_factory=list, max_length=24)
    places: list[str] = Field(default_factory=list, max_length=24)
    concepts: list[str] = Field(default_factory=list, max_length=32)
    section_id: str | None = Field(default=None, max_length=80)
    unit_title: str | None = Field(default=None, max_length=160)
    node_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    source_ids: list[str] = Field(default_factory=list, max_length=12)
    source_checksum: str | None = Field(default=None, min_length=16, max_length=128)
    page: int | None = Field(default=None, ge=1)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    quote: str = Field(default="", max_length=520)
    extraction_method: str | None = Field(default=None, max_length=80)
    review_status: str | None = Field(default=None, max_length=48)
    quality_flags: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_bbox(self):
        if self.bbox is not None and any(value < 0 for value in self.bbox):
            raise ValueError("Kaynak koordinatları negatif olamaz")
        return self


class HistoricalNode(StrictModel):
    id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    node_type: NodeType
    label: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=1200)
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)
    embedding: list[float] | None = Field(default=None, max_length=8192)
    approved: bool = False

    @model_validator(mode="after")
    def source_required_when_approved(self):
        if self.approved and not self.metadata.source_ids:
            raise ValueError("Onaylı düğüm en az bir kaynak kimliği taşımalı")
        return self


class Edge(StrictModel):
    id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    from_node: str
    to_node: str
    relation: RelationType
    quote: str = Field(min_length=12, max_length=520)
    source_ids: list[str] = Field(min_length=1, max_length=4)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    approved: bool = False
    source_checksum: str | None = Field(default=None, min_length=16, max_length=128)
    page: int | None = Field(default=None, ge=1)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    extraction_method: str | None = Field(default=None, max_length=80)
    review_status: str | None = Field(default=None, max_length=48)

    @model_validator(mode="after")
    def validate_bbox(self):
        if self.bbox is not None and any(value < 0 for value in self.bbox):
            raise ValueError("Kenar kaynak koordinatları negatif olamaz")
        return self

    @model_validator(mode="after")
    def no_self_edge(self):
        if self.from_node == self.to_node:
            raise ValueError("Kenarın iki ucu aynı düğüm olamaz")
        return self


class KnowledgeGraph(StrictModel):
    schema_version: str = Field(default="ayt-history-knowledge-graph-v1", alias="schema")
    corpus_checksum: str = Field(min_length=16, max_length=128)
    nodes: list[HistoricalNode] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Düğüm kimlikleri benzersiz olmalı")
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Kenar kimlikleri benzersiz olmalı")
        known = set(node_ids)
        for edge in self.edges:
            if edge.from_node not in known or edge.to_node not in known:
                raise ValueError("Kenarın düğümleri grafikte bulunmalı")
            if edge.approved:
                source_nodes = {n.id for n in self.nodes if n.approved}
                if edge.from_node not in source_nodes or edge.to_node not in source_nodes:
                    raise ValueError("Onaylı kenar yalnız onaylı düğümlere bağlanabilir")
        return self

    def approved_nodes(self) -> list[HistoricalNode]:
        return [node for node in self.nodes if node.approved]

    def approved_edges(self) -> list[Edge]:
        approved = {node.id for node in self.approved_nodes()}
        return [edge for edge in self.edges if edge.approved and edge.from_node in approved and edge.to_node in approved]


class KnowledgeGraphBuilder:
    """Convert a versioned multi-book corpus into a review-safe graph.

    This builder creates structural book/section/chunk nodes only.  Entity
    extraction (person, event, treaty, place) can add candidate nodes later,
    but no such inference is silently promoted to an approved edge.
    """

    def __init__(self, corpus_checksum: str):
        if len(corpus_checksum) < 16:
            raise ValueError("Corpus checksum gerekli")
        self.corpus_checksum = corpus_checksum
        self.nodes: list[HistoricalNode] = []
        self.edges: list[Edge] = []

    @staticmethod
    def _years(text: str) -> list[int]:
        years: list[int] = []
        for raw in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", text):
            value = int(raw)
            if value not in years:
                years.append(value)
        return years[:12]

    @staticmethod
    def _approved(chunk: dict) -> bool:
        review = chunk.get("pre_review") or {}
        return (review.get("decision") in {"approved", "approved_for_runtime"}
                and bool(chunk.get("quality", {}).get("quality_checked", False)))

    def add_corpus(self, corpus: dict) -> KnowledgeGraphBuilder:
        if corpus.get("schema") != "multi-history-rag-v1" or corpus.get("corpus_checksum") != self.corpus_checksum:
            raise ValueError("Corpus şeması veya checksum eşleşmiyor")
        for book in corpus.get("books", []):
            book_id = f"book:{book['source_checksum'][:24]}"
            book_source = [book["source_checksum"]]
            self.nodes.append(HistoricalNode(id=book_id, node_type=NodeType.UNIT,
                                              label=str(book.get("source_name", "MEB kitabı"))[:180],
                                              metadata=NodeMetadata(source_ids=book_source), approved=False))
            sections = book.get("index", {}).get("sections", [])
            section_nodes: dict[str, str] = {}
            for section in sections:
                section_id = str(section.get("id", "unknown"))
                node_id = f"section:{book['source_checksum'][:24]}:{section_id}"
                section_nodes[section_id] = node_id
                self.nodes.append(HistoricalNode(
                    id=node_id, node_type=NodeType.TOPIC, label=str(section.get("title", section_id))[:180],
                    metadata=NodeMetadata(section_id=section_id, unit_title=str(book.get("source_name", ""))[:160],
                                          source_ids=book_source), approved=False))
                self.edges.append(Edge(id=f"edge:{book['source_checksum'][:16]}:{section_id}:book",
                                       from_node=node_id, to_node=book_id, relation=RelationType.ALT_KONUSUDUR,
                                       quote=f"{section.get('title', section_id)} bölümü {book.get('source_name', 'MEB kitabı')} içindedir.",
                                       source_ids=book_source, approved=False))
            for chunk in book.get("index", {}).get("chunks", []):
                chunk_id = str(chunk.get("id", ""))
                if not chunk_id:
                    continue
                source_id = f"{book['source_checksum']}:{chunk_id}"
                node_id = f"chunk:{source_id}"
                text = str(chunk.get("text", ""))
                section_id = str(chunk.get("section_id", "unknown"))
                approved = self._approved(chunk)
                warnings = chunk.get("quality", {}).get("warnings") or []
                weight = max(0.0, min(1.0, 0.75 - 0.08 * len(warnings)))
                self.nodes.append(HistoricalNode(
                    id=node_id, node_type=NodeType.SUBTOPIC, label=str(chunk.get("section_title", section_id))[:180],
                    description=text[:1200], metadata=NodeMetadata(section_id=section_id,
                    unit_title=str(book.get("source_name", ""))[:160], years=self._years(text),
                    node_weight=weight, source_ids=[source_id],
                    source_checksum=book["source_checksum"], page=chunk.get("page"),
                    bbox=chunk.get("bbox"), quote=text[:520],
                    extraction_method="pdf_index", review_status=chunk.get("review_status"),
                    quality_flags=list(warnings)[:16]), approved=approved))
                parent = section_nodes.get(section_id)
                if parent:
                    self.edges.append(Edge(id=f"edge:{book['source_checksum'][:16]}:{chunk_id}:section",
                                           from_node=node_id, to_node=parent, relation=RelationType.ALT_KONUSUDUR,
                                           quote=text[:520] or "Kaynak parçası bu bölüm içinde yer alır.",
                                           source_ids=[source_id], approved=approved,
                                           source_checksum=book["source_checksum"], page=chunk.get("page"),
                                           bbox=chunk.get("bbox"), extraction_method="pdf_index",
                                           review_status=chunk.get("review_status")))
            # A reviewed atom makes its containing section and book safe as
            # structural graph parents.  Without this propagation an approved
            # atom would have an approved edge to an unapproved parent and the
            # graph validator would (correctly) reject the whole snapshot.
            approved_chunks = {node.id for node in self.nodes
                               if node.id.startswith(f"chunk:{book['source_checksum']}:" ) and node.approved}
            approved_sections = {
                edge.to_node for edge in self.edges
                if edge.relation == RelationType.ALT_KONUSUDUR
                and edge.from_node in approved_chunks
                and edge.to_node in section_nodes.values()
            }
            for node in self.nodes:
                if node.id in approved_sections or node.id == book_id and approved_sections:
                    node.approved = True
            approved_structural = approved_sections | ({book_id} if approved_sections else set())
            for edge in self.edges:
                if edge.from_node in approved_structural and edge.to_node in approved_structural:
                    edge.approved = True
        return self

    def build(self) -> KnowledgeGraph:
        return KnowledgeGraph(corpus_checksum=self.corpus_checksum, nodes=self.nodes, edges=self.edges)


class QuestionChoice(StrictModel):
    label: str = Field(pattern=r"^[A-E]$")
    text: str = Field(min_length=1, max_length=800)


class ChoiceEvidenceLink(StrictModel):
    choice_label: str = Field(pattern=r"^[A-E]$")
    node_ids: list[str] = Field(default_factory=list, max_length=8)
    edge_ids: list[str] = Field(default_factory=list, max_length=8)
    relation: QuestionRelation = QuestionRelation.CONTEXT
    note: str = Field(default="", max_length=320)


class QuestionItem(StrictModel):
    id: str = Field(min_length=3, max_length=120)
    stem: str = Field(min_length=8, max_length=3000)
    choices: list[QuestionChoice] = Field(min_length=2, max_length=5)
    unit_id: str | None = None
    topic: str = Field(default="", max_length=180)
    question_terms: list[str] = Field(default_factory=list, max_length=40)
    choice_evidence: list[ChoiceEvidenceLink] = Field(default_factory=list, max_length=5)
    # Gold answer is deliberately absent from the runtime object.  Private
    # evaluation can store it outside this model.
    answer_key_ref: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def unique_choices_and_links(self):
        labels = [choice.label for choice in self.choices]
        if len(labels) != len(set(labels)):
            raise ValueError("Şık etiketleri benzersiz olmalı")
        links = [link.choice_label for link in self.choice_evidence]
        if len(links) != len(set(links)):
            raise ValueError("Bir şık için tek kanıt bağlantısı kaydı kullanılmalı")
        return self


class TutorDialogueState(StrictModel):
    session_id: str = Field(min_length=8, max_length=120)
    question_id: str
    stage: DialogueStage = DialogueStage.SORU_ANALIZI
    selected_choice: str | None = Field(default=None, pattern=r"^[A-E]$")
    eliminated_choices: list[str] = Field(default_factory=list, max_length=5)
    asked_hints: list[str] = Field(default_factory=list, max_length=12)
    learner_turns: int = Field(default=0, ge=0, le=20)
    repeat_attempts: int = Field(default=0, ge=0, le=5)
    retrieved_node_ids: list[str] = Field(default_factory=list, max_length=12)
    retrieved_edge_ids: list[str] = Field(default_factory=list, max_length=12)
    source_ids: list[str] = Field(default_factory=list, max_length=12)
    can_reveal_explanation: bool = False

    @model_validator(mode="after")
    def reveal_only_at_final_stage(self):
        if self.can_reveal_explanation and self.stage != DialogueStage.GEREKCELI_ACIKLAMA:
            raise ValueError("Açıklama yalnız son aşamada açılabilir")
        if any(label not in {"A", "B", "C", "D", "E"} for label in self.eliminated_choices):
            raise ValueError("Geçersiz elenen şık etiketi")
        return self


class EvidenceHit(StrictModel):
    choice_label: str = Field(pattern=r"^[A-E]$")
    node_id: str
    score: float
    cosine_score: float = Field(ge=0.0, le=1.0)
    metadata_score: float = Field(ge=0.0, le=1.0)
    node_weight_score: float = Field(ge=0.0, le=1.0)
    graph_score: float = Field(ge=0.0, le=1.0)
    hop: int = Field(ge=0, le=2)
    supporting_edge_ids: list[str] = Field(default_factory=list, max_length=8)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class EvidenceChain(StrictModel):
    choice_label: str = Field(pattern=r"^[A-E]$")
    hits: list[EvidenceHit] = Field(default_factory=list, max_length=8)
    abstain: bool = False
    abstain_reason: str | None = None


class RetrievalResult(StrictModel):
    chains: list[EvidenceChain]
    query_terms: list[str]
    metadata_filters: dict[str, list[str]] = Field(default_factory=dict)


class RetrievalGold(StrictModel):
    """Private evaluation label; never sent to the student or local LLM."""

    choice_label: str = Field(pattern=r"^[A-E]$")
    relevant_node_ids: list[str] = Field(default_factory=list, max_length=20)
    should_abstain: bool = False


class RetrievalMetrics(StrictModel):
    query_count: int = Field(ge=0)
    recall_at_1: float = Field(ge=0.0, le=1.0)
    recall_at_3: float = Field(ge=0.0, le=1.0)
    mrr_at_3: float = Field(ge=0.0, le=1.0)
    ndcg_at_3: float = Field(ge=0.0, le=1.0)
    wrong_evidence_rate: float = Field(ge=0.0, le=1.0)
    abstain_accuracy: float = Field(ge=0.0, le=1.0)


DEFAULT_SCORE_WEIGHTS = {
    "cosine": 0.45,
    "metadata": 0.25,
    "node_weight": 0.10,
    "graph": 0.20,
}


DATE_RE = re.compile(r"(?:MÖ|MS)?\s*\d{1,4}(?:\s*[-–]\s*\d{1,4})?", re.IGNORECASE)
TOKEN_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+")
STOP = {"ve", "veya", "ile", "bir", "bu", "şu", "olan", "hangi", "hangisi", "aşağıdaki", "göre", "için", "de", "da"}


def _tokens(text: str) -> set[str]:
    return {item.casefold() for item in TOKEN_RE.findall(text) if len(item) > 2 and item.casefold() not in STOP}


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denom = math.sqrt(sum(x * x for x in left) * sum(y * y for y in right))
    return max(0.0, min(1.0, sum(x * y for x, y in zip(left, right)) / denom)) if denom else 0.0


def evaluate_retrieval(cases: list[tuple[RetrievalResult, list[RetrievalGold]]]) -> RetrievalMetrics:
    """Evaluate choice-level retrieval against a private gold set.

    ``cases`` is intentionally passed by the evaluation runner instead of
    stored in the runtime graph.  A result can be scored against multiple
    choices, while answer keys and gold labels remain outside student prompts.
    """
    totals = {"r1": 0.0, "r3": 0.0, "mrr": 0.0, "ndcg": 0.0,
              "wrong": 0.0, "evidence": 0.0, "abstain": 0.0}
    count = 0
    for result, gold_rows in cases:
        by_choice = {chain.choice_label: chain for chain in result.chains}
        for gold in gold_rows:
            chain = by_choice.get(gold.choice_label)
            ranked = [hit.node_id for hit in chain.hits] if chain else []
            relevant = set(gold.relevant_node_ids)
            count += 1
            totals["r1"] += float(bool(set(ranked[:1]) & relevant)) if relevant else 0.0
            totals["r3"] += float(bool(set(ranked[:3]) & relevant)) if relevant else 0.0
            first = next((index for index, node_id in enumerate(ranked[:3], start=1)
                          if node_id in relevant), None)
            totals["mrr"] += 1.0 / first if first else 0.0
            dcg = sum((1.0 / math.log2(index + 2)) for index, node_id in enumerate(ranked[:3])
                      if node_id in relevant)
            ideal = 1.0 / math.log2(2) if relevant else 0.0
            totals["ndcg"] += dcg / ideal if ideal else 0.0
            if ranked:
                totals["wrong"] += sum(node_id not in relevant for node_id in ranked)
                totals["evidence"] += len(ranked)
            predicted_abstain = not ranked if chain is None else chain.abstain
            totals["abstain"] += float(predicted_abstain == gold.should_abstain)
    if count == 0:
        return RetrievalMetrics(query_count=0, recall_at_1=0, recall_at_3=0, mrr_at_3=0,
                                ndcg_at_3=0, wrong_evidence_rate=0, abstain_accuracy=0)
    return RetrievalMetrics(
        query_count=count,
        recall_at_1=round(totals["r1"] / count, 6),
        recall_at_3=round(totals["r3"] / count, 6),
        mrr_at_3=round(totals["mrr"] / count, 6),
        ndcg_at_3=round(totals["ndcg"] / count, 6),
        wrong_evidence_rate=round(totals["wrong"] / totals["evidence"], 6) if totals["evidence"] else 0.0,
        abstain_accuracy=round(totals["abstain"] / count, 6),
    )


class EmbeddingFn(Protocol):
    def __call__(self, text: str) -> list[float]: ...


class WeightedGraphSearch:
    """Question+choice search with explicit, inspectable score components."""

    def __init__(self, graph: KnowledgeGraph, embed: EmbeddingFn | None = None,
                 weights: dict[str, float] | None = None):
        self.graph = graph
        self.embed = embed
        self.weights = dict(DEFAULT_SCORE_WEIGHTS if weights is None else weights)
        if set(self.weights) != set(DEFAULT_SCORE_WEIGHTS) or any(value < 0 for value in self.weights.values()):
            raise ValueError("Arama ağırlıkları cosine, metadata, node_weight ve graph alanlarını içermeli")
        if not math.isclose(sum(self.weights.values()), 1.0, abs_tol=1e-6):
            raise ValueError("Arama ağırlıklarının toplamı 1 olmalı")
        self.nodes = {node.id: node for node in graph.approved_nodes()}
        self.edges = graph.approved_edges()
        self.adj: dict[str, list[tuple[str, Edge]]] = defaultdict(list)
        for edge in self.edges:
            self.adj[edge.from_node].append((edge.to_node, edge))
            self.adj[edge.to_node].append((edge.from_node, edge))

    @staticmethod
    def _metadata_score(node: HistoricalNode, text: str) -> float:
        query = text.casefold()
        values = [node.label, *node.metadata.aliases, *node.metadata.persons,
                  *node.metadata.places, *node.metadata.concepts, node.metadata.period or ""]
        exact = sum(1 for value in values if value and value.casefold() in query)
        dates = [str(year) for year in node.metadata.years]
        exact += sum(1 for year in dates if year in query)
        return min(1.0, exact / max(1, min(4, len([v for v in values if v]))))

    @staticmethod
    def _lexical_score(node: HistoricalNode, text: str) -> float:
        query = _tokens(text)
        target = _tokens(" ".join([node.label, node.description, *node.metadata.aliases,
                                    *node.metadata.persons, *node.metadata.places, *node.metadata.concepts]))
        return len(query & target) / max(1, len(query | target))

    def _graph_scores(self, seed: str) -> dict[str, tuple[float, int, list[str]]]:
        result: dict[str, tuple[float, int, list[str]]] = {seed: (1.0, 0, [])}
        queue = deque([(seed, 0, [])])
        while queue:
            current, hop, edge_ids = queue.popleft()
            if hop >= 2:
                continue
            for target, edge in self.adj.get(current, []):
                next_hop = hop + 1
                score = 1.0 if next_hop == 1 else 0.5
                previous = result.get(target)
                if previous is None or score > previous[0]:
                    chain = [*edge_ids, edge.id]
                    result[target] = (score, next_hop, chain)
                    queue.append((target, next_hop, chain))
        return result

    def _query_graph_scores(self, seeds: set[str]) -> dict[str, tuple[float, int, list[str]]]:
        """Return the strongest approved one/two-hop path from query seeds."""
        combined: dict[str, tuple[float, int, list[str]]] = {}
        for seed in sorted(seeds):
            for node_id, value in self._graph_scores(seed).items():
                previous = combined.get(node_id)
                if previous is None or value[0] > previous[0] or (value[0] == previous[0] and value[1] < previous[1]):
                    combined[node_id] = value
        return combined

    def search(self, question: QuestionItem, *, top_k: int = 3, min_score: float = 0.18) -> RetrievalResult:
        if top_k < 1:
            raise ValueError("top_k pozitif olmalı")
        query_terms = sorted(_tokens(question.stem + " " + " ".join(choice.text for choice in question.choices)))
        metadata_filters = {"dates": sorted(set(DATE_RE.findall(question.stem))), "terms": query_terms[:40]}
        chains = []
        for choice in question.choices:
            text = f"{question.stem} {choice.text} {question.topic}"
            query_embedding = self.embed(text) if self.embed else None
            hits = []
            metrics: dict[str, tuple[HistoricalNode, float, float]] = {}
            for node in self.nodes.values():
                lexical = self._lexical_score(node, text)
                cosine = cosine_similarity(query_embedding, node.embedding)
                # During corpus migration embeddings may be absent for a
                # reviewed atom.  Keep the deterministic lexical signal as a
                # bounded fallback instead of silently dropping that evidence.
                if self.embed is None or node.embedding is None:
                    cosine = lexical
                metadata = self._metadata_score(node, text)
                metrics[node.id] = (node, cosine, metadata)
            seeds = {node_id for node_id, (_node, cosine, metadata) in metrics.items()
                     if metadata > 0.0 or cosine > 0.08}
            graph_scores = self._query_graph_scores(seeds)
            for node_id, (node, cosine, metadata) in metrics.items():
                graph_score, hop, edge_ids = graph_scores.get(node_id, (0.0, 2, []))
                score = (self.weights["cosine"] * cosine + self.weights["metadata"] * metadata
                         + self.weights["node_weight"] * node.metadata.node_weight
                         + self.weights["graph"] * graph_score)
                if score >= min_score:
                    hits.append((score, node, cosine, metadata, graph_score, hop, edge_ids))
            hits.sort(key=lambda item: (-item[0], item[1].id))
            unique: dict[str, tuple] = {}
            for hit in hits:
                unique.setdefault(hit[1].id, hit)
            selected = list(unique.values())[:top_k]
            chains.append(EvidenceChain(
                choice_label=choice.label,
                hits=[EvidenceHit(choice_label=choice.label, node_id=node.id, score=round(score, 6),
                                  cosine_score=round(cosine, 6), metadata_score=round(metadata, 6),
                                  node_weight_score=node.metadata.node_weight,
                                  graph_score=round(graph_score, 6), hop=hop,
                                  supporting_edge_ids=edge_ids,
                                  source_ids=node.metadata.source_ids)
                       for score, node, cosine, metadata, graph_score, hop, edge_ids in selected],
                abstain=not bool(selected),
                abstain_reason=None if selected else "onaylı kaynak düğümü bulunamadı",
            ))
        return RetrievalResult(chains=chains, query_terms=query_terms, metadata_filters=metadata_filters)


class LocalLLM(Protocol):
    def generate(self, system_prompt: str, user_prompt: str, *, max_tokens: int) -> str: ...


class TTSSynthesizer(Protocol):
    def synthesize(self, text: str, *, output_path: Path) -> None: ...


class AudioCache:
    """Content-addressed WAV cache; dynamic sentences share the same path."""

    def __init__(self, root: Path, voice_version: str):
        self.root = root
        self.voice_version = voice_version
        self._locks = tuple(threading.Lock() for _ in range(64))

    def key(self, text: str) -> str:
        normalized = " ".join(text.split())
        return hashlib.sha256(f"{self.voice_version}\n{normalized}".encode()).hexdigest()

    def path_for(self, text: str) -> Path:
        return self.root / f"{self.key(text)}.wav"

    def get_or_create(self, text: str, synthesizer: TTSSynthesizer) -> Path:
        target = self.path_for(text)
        lock = self._locks[int(self.key(text)[:8], 16) % len(self._locks)]
        with lock:
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                # A crashed TTS process must never leave a half-written WAV
                # that later requests mistake for a valid cache hit.
                temporary = target.with_suffix(target.suffix + ".tmp")
                synthesizer.synthesize(text, output_path=temporary)
                temporary.replace(target)
        return target

    def prewarm(self, texts: list[str], synthesizer: TTSSynthesizer) -> dict[str, Path]:
        """Batch-generate stable prompts/questions once (Kaggle or local GPU)."""
        result: dict[str, Path] = {}
        for text in dict.fromkeys(" ".join(item.split()) for item in texts if item.strip()):
            result[text] = self.get_or_create(text, synthesizer)
        return result


def sentence_chunks(text: str, max_chars: int = 180) -> list[str]:
    if max_chars < 40:
        raise ValueError("max_chars çok küçük")
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    chunks: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        words, current = sentence.split(), ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


class SocraticTutorOrchestrator:
    """Coordinates graph evidence, safe LLM prompts, dialogue state and TTS."""

    def __init__(self, search: WeightedGraphSearch, llm: LocalLLM,
                 audio_cache: AudioCache, tts: TTSSynthesizer):
        self.search = search
        self.llm = llm
        self.audio_cache = audio_cache
        self.tts = tts
        self.last_timings: dict[str, int] = {}

    @staticmethod
    def _system_prompt() -> str:
        return ("Sen görme engelli AYT öğrencisine kısa özel ders veren tarih koçusun. "
                "Yalnız verilen onaylı kanıtlara dayan. İlk dört aşamada cevabı, doğru şıkkı "
                "ve cevap anahtarını söyleme. Tek seferde tek soru sor; en fazla iki kısa cümle kullan. "
                "Kaynak yetersizse tahmin etme ve bunu açıkça belirt.")

    def _context(self, result: RetrievalResult) -> str:
        """Render only approved node text and approved edge quotes for the LLM."""
        edge_by_id = {edge.id: edge for edge in self.search.edges}
        lines: list[str] = []
        for chain in result.chains:
            for hit in chain.hits[:2]:
                node = self.search.nodes.get(hit.node_id)
                if node is None:
                    continue
                description = " ".join(node.description.split())[:420]
                evidence = f"Şık {hit.choice_label}: {node.label}. {description}".strip()
                quotes = [edge_by_id[edge_id].quote[:260] for edge_id in hit.supporting_edge_ids
                          if edge_id in edge_by_id]
                if quotes:
                    evidence += " Bağlantı kanıtı: " + " ".join(quotes)
                evidence += f" Kaynak kimliği: {','.join(hit.source_ids)}. Skor: {hit.score}."
                lines.append(evidence)
                if len(lines) >= 8:
                    return "\n".join(lines)
        return "\n".join(lines) or "Onaylı kanıt yok."

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        compact = " ".join(value.split())
        return compact if len(compact) <= limit else compact[:limit].rsplit(" ", 1)[0] + "…"

    @staticmethod
    def _next_stage(stage: DialogueStage, learner_message: str) -> DialogueStage:
        """Advance one bounded turn; a learner message unlocks the final check."""
        if stage == DialogueStage.GEREKCELI_ACIKLAMA:
            return stage
        if stage == DialogueStage.OGRENCI_YANITI:
            # The explanation gate is intentionally closed until the learner
            # has supplied an actual answer.  A client may resend the state
            # without a message, but that must not skip the recall turn.
            return (DialogueStage.GEREKCELI_ACIKLAMA
                    if learner_message.strip() else DialogueStage.OGRENCI_YANITI)
        order = list(DialogueStage)
        return order[min(order.index(stage) + 1, len(order) - 1)]

    @staticmethod
    def _safe_fallback(stage: DialogueStage) -> str:
        prompts = {
            DialogueStage.SORU_ANALIZI: "Soru kökünün senden istediği bilgiyi kendi sözlerinle anlatır mısın?",
            DialogueStage.HATIRLAMAYI_ORTAYA_CIKARMA: "Bu konuyla ilgili aklına gelen ilk kişi, olay veya tarihi söyleyebilir misin?",
            DialogueStage.KANITLA_BAG_KURMA: "Kaynakta geçen hangi ayrıntı sorudaki ifadeyle bağlantılı görünüyor?",
            DialogueStage.SIK_ELEMESI: "Şıklardan birini kaynakta geçen bilgiyle karşılaştırıp elemek ister misin?",
            DialogueStage.OGRENCI_YANITI: "Bir şık seçip gerekçeni kendi cümlenle söyler misin?",
            DialogueStage.GEREKCELI_ACIKLAMA: "Yanıtını kaynakta geçen kanıtla karşılaştırıp aradaki bağı kendi cümlenle açıklar mısın?",
        }
        return prompts[stage]

    def start(self, question: QuestionItem, state: TutorDialogueState | None = None,
              learner_message: str = "", verified_explanation: str | None = None) -> tuple[TutorDialogueState, str, list[Path]]:
        started = time.monotonic()
        current = state or TutorDialogueState(session_id=hashlib.sha256(question.id.encode()).hexdigest()[:16], question_id=question.id)
        if current.question_id != question.id:
            raise ValueError("Diyalog başka soruya taşınamaz")
        response_stage = current.stage
        retrieval_started = time.monotonic()
        result = self.search.search(question, top_k=3)
        retrieval_ms = int((time.monotonic() - retrieval_started) * 1000)
        llm_ms = 0
        all_hits = [hit for chain in result.chains for hit in chain.hits]
        if not all_hits:
            text = "Bu soru için öğretmen onaylı kaynak düğümü bulunamadı. " + self._safe_fallback(response_stage)
            next_state = current.model_copy(update={"learner_turns": current.learner_turns + 1,
                                                     "stage": self._next_stage(response_stage, learner_message),
                                                     "source_ids": [], "retrieved_node_ids": [], "retrieved_edge_ids": []})
        else:
            stem = self._clip(question.stem, 900)
            choices = " | ".join(f"{c.label}: {self._clip(c.text, 240)}" for c in question.choices)
            user_prompt = (f"Aşama: {response_stage.value}\nSoru: {stem}\n"
                           f"Şıklar: {choices}\n"
                           f"Öğrenci mesajı: {self._clip(learner_message or 'Henüz yanıt vermedi.', 300)}\n"
                           + "Kanıt bağlamı:\n" + self._clip(self._context(result), 3200))
            # The final explanation is a server-side verified value.  It never
            # goes through the model, which has no answer key or private key.
            if response_stage == DialogueStage.GEREKCELI_ACIKLAMA:
                text = (verified_explanation or self._safe_fallback(response_stage)).strip()
            else:
                llm_started = time.monotonic()
                try:
                    text = self.llm.generate(self._system_prompt(), user_prompt, max_tokens=72).strip()
                except (OSError, RuntimeError, ValueError):  # local failure must not break tutoring
                    text = ""
                llm_ms = int((time.monotonic() - llm_started) * 1000)
                if not text or not _safe_early_response(text):
                    text = self._safe_fallback(response_stage)
            next_state = current.model_copy(update={
                "stage": self._next_stage(response_stage, learner_message),
                "learner_turns": current.learner_turns + 1,
                "retrieved_node_ids": list(dict.fromkeys(hit.node_id for hit in all_hits))[:12],
                "retrieved_edge_ids": list(dict.fromkeys(edge for hit in all_hits for edge in hit.supporting_edge_ids))[:12],
                "source_ids": list(dict.fromkeys(source for hit in all_hits for source in hit.source_ids))[:12],
            })
        tts_started = time.monotonic()
        text = self._clip(text, 600)
        audio_paths = [self.audio_cache.get_or_create(chunk, self.tts) for chunk in sentence_chunks(text)]
        tts_ms = int((time.monotonic() - tts_started) * 1000)
        if response_stage == DialogueStage.GEREKCELI_ACIKLAMA:
            # Only a server-side verified explanation can unlock the final
            # response.  A caller-supplied final-stage state without that
            # value is returned to the learner-answer gate.
            if verified_explanation and verified_explanation.strip():
                next_state = next_state.model_copy(update={"can_reveal_explanation": True})
            else:
                next_state = next_state.model_copy(update={
                    "stage": DialogueStage.OGRENCI_YANITI,
                    "can_reveal_explanation": False,
                })
        self.last_timings = {
            "retrieval": retrieval_ms,
            "first_token": int(getattr(self.llm, "last_first_token_ms", 0) or 0),
            "llm": llm_ms,
            "tts": tts_ms,
            "total": int((time.monotonic() - started) * 1000),
        }
        return next_state, text, audio_paths


def _answer_leak(text: str) -> bool:
    return bool(re.search(r"(?:doğru cevap|doğru şık|cevap\s*[:：]|şık\s*[A-E]\b|[A-E]\s*şıkkı)", text, re.IGNORECASE))


def _safe_early_response(text: str) -> bool:
    compact = " ".join(text.split())
    return bool(compact) and compact.endswith("?") and compact.count("?") == 1 and not _answer_leak(compact)


def example_graph_payload() -> dict[str, Any]:
    """Small answer-free JSON example used in docs and schema tests."""
    graph = KnowledgeGraph(
        corpus_checksum="0123456789abcdef0123456789abcdef",
        nodes=[
            HistoricalNode(id="topic-milli-mucadele", node_type=NodeType.TOPIC,
                           label="Millî Mücadele", approved=True,
                           metadata=NodeMetadata(section_id="2.1", node_weight=0.9, source_ids=["src-topic-001"])),
            HistoricalNode(id="event-tbmm", node_type=NodeType.KURUM_DEVLET,
                           label="TBMM'nin açılması", description="Millî egemenliğin kurumsallaşması.", approved=True,
                           metadata=NodeMetadata(years=[1920], concepts=["ulusal egemenlik"], source_ids=["src-meb-001"])),
        ],
        edges=[Edge(id="edge-topic-tbmm", from_node="event-tbmm", to_node="topic-milli-mucadele",
                    relation=RelationType.ALT_KONUSUDUR, quote="TBMM'nin açılması Millî Mücadele döneminin önemli gelişmelerindendir.",
                    source_ids=["src-meb-001"], confidence=0.96, approved=True)],
    )
    question = QuestionItem(id="demo-q1", stem="Millî egemenlikle ilgili gelişmeyi bul.",
                            choices=[QuestionChoice(label="A", text="TBMM'nin açılması"),
                                     QuestionChoice(label="B", text="Başka bir seçenek")], topic="Millî Mücadele")
    state = TutorDialogueState(session_id="demo-session", question_id="demo-q1")
    return {"graph": graph.model_dump(mode="json", by_alias=True), "question": question.model_dump(mode="json"), "dialogue_state": state.model_dump(mode="json")}
