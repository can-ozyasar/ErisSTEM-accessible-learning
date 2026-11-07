"""Source-bound analysis, bounded inference and private QLoRA data utilities.

The classes in this module are deliberately answer-key free at runtime.  They
can produce private research recommendations, but an agent decision is never
promoted to the student graph without an explicit human approval manifest.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ayt_knowledge_graph import (
    Edge,
    EvidenceChain,
    KnowledgeGraph,
    QuestionChoice,
    QuestionItem,
    RelationType,
    RetrievalResult,
    WeightedGraphSearch,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class QuestionMode(str, Enum):
    DIRECT = "direct"
    ELIMINATION = "elimination"
    CHRONOLOGY = "chronology"
    INFERENCE = "inference"
    MIXED = "mixed"


class QuestionAnalysis(StrictModel):
    question_id: str
    is_negative_root: bool = False
    is_chronology_trap: bool = False
    is_inference_required: bool = False
    mode: QuestionMode
    extracted_terms: list[str] = Field(default_factory=list, max_length=80)
    choice_terms: dict[str, list[str]] = Field(default_factory=dict, max_length=5)


class EliminationRecord(StrictModel):
    choice_label: str = Field(pattern=r"^[A-E]$")
    status: Literal["supported", "eliminated", "uncertain"]
    reason: str = Field(min_length=3, max_length=320)
    node_ids: list[str] = Field(default_factory=list, max_length=8)
    edge_ids: list[str] = Field(default_factory=list, max_length=8)
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class EliminationResult(StrictModel):
    question_id: str
    analysis: QuestionAnalysis
    retrieval: RetrievalResult
    records: list[EliminationRecord] = Field(default_factory=list, max_length=5)
    strategy: QuestionMode
    candidate_choices: list[str] = Field(default_factory=list, max_length=5)
    abstain: bool = False
    abstain_reason: str | None = None


class TeacherValidation(StrictModel):
    question_id: str
    decision: Literal["direct", "bounded_inference", "insufficient", "wrong"]
    evidence_node_ids: list[str] = Field(default_factory=list, max_length=3)
    evidence_edge_ids: list[str] = Field(default_factory=list, max_length=3)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=3, max_length=800)
    reviewer_kind: str = "rule_based_teacher_candidate_v1"
    model_judgment_used: bool = False
    retrieval_attempts: int = Field(default=1, ge=1, le=3)
    retry_queries: list[str] = Field(default_factory=list, max_length=2)
    is_human_teacher_approval: bool = False
    runtime_enabled: bool = False
    qlora_enabled: bool = False


class GeneratedQuestionDraft(StrictModel):
    """Private, source-guaranteed draft; answer_label never enters QuestionItem."""

    id: str
    runtime_question: QuestionItem
    answer_label: str = Field(pattern=r"^[A-E]$")
    supporting_edge_id: str
    relation_type: str = Field(min_length=3, max_length=64)
    concept_keys: list[str] = Field(min_length=1, max_length=12)
    source_ids: list[str] = Field(min_length=1, max_length=8)
    source_quote: str = Field(min_length=12, max_length=520)
    source_checksum: str | None = Field(default=None, min_length=16, max_length=128)
    page: int | None = Field(default=None, ge=1)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    generation_method: str = "approved_edge_relation_v1"
    human_review_required: bool = True


class SplitRecord(StrictModel):
    id: str = Field(min_length=1, max_length=160)
    concept_keys: list[str] = Field(min_length=1, max_length=32)
    payload: dict[str, Any]


class ConceptSplit(StrictModel):
    train: list[SplitRecord] = Field(default_factory=list)
    dev: list[SplitRecord] = Field(default_factory=list)
    test: list[SplitRecord] = Field(default_factory=list)
    concept_sets: dict[str, list[str]]
    leakage_free: bool
    seed: int

    @model_validator(mode="after")
    def verify_no_concept_leakage(self):
        names = ("train", "dev", "test")
        sets = [set(self.concept_sets.get(name, [])) for name in names]
        if any(left & right for index, left in enumerate(sets) for right in sets[index + 1:]):
            raise ValueError("Concept tabanlı split kümeleri çakışamaz")
        for name, rows in zip(names, (self.train, self.dev, self.test)):
            row_ids = [row.id for row in rows]
            if len(row_ids) != len(set(row_ids)):
                raise ValueError("Kayıt kimlikleri split içinde benzersiz olmalı")
            actual = {concept for row in rows for concept in row.concept_keys}
            if actual != set(self.concept_sets.get(name, [])):
                raise ValueError("Concept manifesti kayıtlarla uyuşmuyor")
        all_ids = [row.id for rows in (self.train, self.dev, self.test) for row in rows]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Bir kayıt birden fazla split'te bulunamaz")
        return self


_TOKEN_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+")
_NEGATIVE_RE = re.compile(r"\b(değildir|değil|olamaz|söylenemez|ulaşılamaz|yanlıştır|hangisi.*?dışında)\b", re.I)
_CHRONOLOGY_RE = re.compile(r"\b(önce|sonra|kronolojik|sıralama|ilk|son|ardından|öncelik)\b", re.I)
_INFERENCE_RE = re.compile(r"\b(çıkarılabilir|ulaşılabilir|gösterir|neden|sonuç|amaç|beklenir|yorum)\b", re.I)


def _terms(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in _TOKEN_RE.findall(text):
        normalized = token.casefold()
        if len(normalized) > 2 and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result[:80]


class QuestionAnalyzerAndEliminator:
    """Analyze question anatomy and safely eliminate only explicit contradictions."""

    def __init__(self, search: WeightedGraphSearch, *, direct_threshold: float = 0.42):
        if not 0.0 <= direct_threshold <= 1.0:
            raise ValueError("direct_threshold 0 ile 1 arasında olmalı")
        self.search = search
        self.direct_threshold = direct_threshold
        self._edges = {edge.id: edge for edge in search.edges}

    @staticmethod
    def analyze(question: QuestionItem) -> QuestionAnalysis:
        stem_terms = _terms(question.stem)
        choice_terms = {choice.label: _terms(choice.text) for choice in question.choices}
        negative = bool(_NEGATIVE_RE.search(question.stem))
        chronology = bool(_CHRONOLOGY_RE.search(question.stem))
        inference = bool(_INFERENCE_RE.search(question.stem))
        active = sum((negative, chronology, inference))
        mode = (QuestionMode.MIXED if active > 1 else
                QuestionMode.ELIMINATION if negative else
                QuestionMode.CHRONOLOGY if chronology else
                QuestionMode.INFERENCE if inference else QuestionMode.DIRECT)
        return QuestionAnalysis(question_id=question.id, is_negative_root=negative,
                                 is_chronology_trap=chronology, is_inference_required=inference,
                                 mode=mode, extracted_terms=stem_terms, choice_terms=choice_terms)

    def _record_for_chain(self, chain: EvidenceChain, analysis: QuestionAnalysis,
                          question: QuestionItem) -> EliminationRecord:
        best = chain.hits[0] if chain.hits else None
        nodes = [hit.node_id for hit in chain.hits[:3]]
        edges = list(dict.fromkeys(edge for hit in chain.hits[:3] for edge in hit.supporting_edge_ids))[:8]
        if best is None:
            return EliminationRecord(choice_label=chain.choice_label, status="uncertain",
                                     reason="Onaylı kanıt bulunamadı; yokluk yanlışlık kanıtı değildir.")
        choice = next(item for item in question.choices if item.label == chain.choice_label)
        query_terms = set(_terms(question.stem + " " + question.topic))
        choice_terms = set(_terms(choice.text))
        explicit_contradiction = any(self._edge_is_relevant_contradiction(
            edge_id, query_terms, choice_terms
        ) for edge_id in edges)
        if explicit_contradiction:
            return EliminationRecord(choice_label=chain.choice_label, status="eliminated",
                                     reason="Onaylı grafikte şıkla çelişen açık karşılaştırma kenarı bulundu.",
                                     node_ids=nodes, edge_ids=edges, score=best.score)
        explicit_support = best.score >= self.direct_threshold and self._edge_supports_choice(
            edges, query_terms, choice_terms
        )
        if explicit_support:
            status = "eliminated" if analysis.is_negative_root else "supported"
            reason = ("Şık, sorunun olumsuz kökünde aranan ifadeyi onaylı kanıtla destekliyor; bu nedenle elenir."
                      if analysis.is_negative_root else
                      "Şık için onaylı kaynak ve ilişki sinyali bulundu; kesin cevap olduğu varsayılmaz.")
            return EliminationRecord(choice_label=chain.choice_label, status=status, reason=reason,
                                     node_ids=nodes, edge_ids=edges, score=best.score)
        return EliminationRecord(choice_label=chain.choice_label, status="uncertain",
                                 reason="Benzer aday bulundu ancak soru-şık ilişkisini açıkça destekleyen kenar yok.",
                                 node_ids=nodes, edge_ids=edges, score=best.score)

    def _edge_terms(self, edge_id: str) -> set[str]:
        edge = self._edges.get(edge_id)
        if edge is None:
            return set()
        endpoints = [self.search.nodes[node_id] for node_id in (edge.from_node, edge.to_node)
                     if node_id in self.search.nodes]
        text = " ".join([edge.quote, *(node.label + " " + node.description for node in endpoints)])
        return set(_terms(text))

    def _edge_supports_choice(self, edge_ids: list[str], query_terms: set[str], choice_terms: set[str]) -> bool:
        for edge_id in edge_ids:
            edge = self._edges.get(edge_id)
            terms = self._edge_terms(edge_id)
            if (edge and edge.relation != RelationType.CELISIR_TAVIZDIR
                    and len(terms & query_terms) >= 1 and len(terms & choice_terms) >= 1):
                return True
        return False

    def _edge_is_relevant_contradiction(self, edge_id: str, query_terms: set[str],
                                        choice_terms: set[str]) -> bool:
        edge = self._edges.get(edge_id)
        terms = self._edge_terms(edge_id)
        return bool(edge and edge.relation == RelationType.CELISIR_TAVIZDIR
                    and len(terms & query_terms) >= 1 and len(terms & choice_terms) >= 1)

    def analyze_and_eliminate(self, question: QuestionItem, *, top_k: int = 3) -> EliminationResult:
        analysis = self.analyze(question)
        retrieval = self.search.search(question, top_k=top_k)
        records = [self._record_for_chain(chain, analysis, question) for chain in retrieval.chains]
        if analysis.is_negative_root:
            candidates = [record.choice_label for record in records if record.status == "uncertain"]
            strategy = QuestionMode.ELIMINATION
        else:
            candidates = [record.choice_label for record in records if record.status == "supported"]
            strategy = analysis.mode
            if not candidates:
                # Bir doğru ilişki bulunamadığında sistem doğrudan şık seçmeye
                # çalışmaz. Yalnız açıkça elenmiş seçenekleri dışarıda bırakıp
                # öğrenciyi kalan seçenekleri karşılaştırmaya yönlendirir.
                strategy = QuestionMode.ELIMINATION
                candidates = [record.choice_label for record in records if record.status == "uncertain"]
        abstain = not bool(candidates)
        return EliminationResult(
            question_id=question.id, analysis=analysis, retrieval=retrieval, records=records,
            strategy=strategy, candidate_choices=candidates, abstain=abstain,
            abstain_reason="Onaylı kanıtla güvenli aday üretilemedi." if abstain else None,
        )


class HistoryTeacherValidatorAgent:
    """Conservative rule-based teacher proposal; never grants approval."""

    def __init__(self, graph: KnowledgeGraph, *, max_atoms: int = 3, min_edge_confidence: float = 0.6):
        if not 1 <= max_atoms <= 3:
            raise ValueError("max_atoms 1 ile 3 arasında olmalı")
        self.graph = graph
        self.max_atoms = max_atoms
        self.min_edge_confidence = min_edge_confidence
        self.nodes = {node.id: node for node in graph.approved_nodes()}
        self.edges = {edge.id: edge for edge in graph.approved_edges()}

    def validate(self, question: QuestionItem, result: EliminationResult | RetrievalResult) -> TeacherValidation:
        retrieval = result.retrieval if isinstance(result, EliminationResult) else result
        all_hits = [hit for chain in retrieval.chains for hit in chain.hits]
        if not all_hits:
            return TeacherValidation(question_id=question.id, decision="insufficient",
                                     rationale="Onaylı grafikte soru için aday kanıt bulunamadı.")
        edge_ids = set(self.edges)
        direct = next((hit for hit in all_hits
                       if hit.score >= 0.55
                       and any(edge_id in edge_ids for edge_id in hit.supporting_edge_ids)
                       and self._direct_overlap(question, hit.node_id)), None)
        if direct is not None:
            source_ids = list(dict.fromkeys(direct.source_ids))[:8]
            return TeacherValidation(question_id=question.id, decision="direct",
                                     evidence_node_ids=[direct.node_id],
                                     evidence_edge_ids=direct.supporting_edge_ids[:3], source_ids=source_ids,
                                     rationale="Tek bir onaylı atomın alıntısı soru terimleriyle örtüşüyor. Bu otomatik aday kararıdır; öğretmen onayı değildir.")
        # A bounded inference needs distinct approved nodes connected by strong
        # edges.  It never treats lexical proximity or missing evidence as a
        # contradiction.
        selected, selected_edges = self._connected_bundle(question, retrieval)
        if len(selected) >= 2 and selected_edges:
            source_ids = list(dict.fromkeys(source for node_id in selected
                                           for source in self.nodes[node_id].metadata.source_ids))[:8]
            return TeacherValidation(
                question_id=question.id, decision="bounded_inference",
                evidence_node_ids=selected[:self.max_atoms], evidence_edge_ids=selected_edges[:self.max_atoms],
                source_ids=source_ids,
                rationale="En fazla üç onaylı atom, aynı kaynaklı graf yolunda bağlı ve soru terimleriyle örtüşüyor. Bu sınırlı çıkarım önerisidir; insan onayı değildir.",
            )
        return TeacherValidation(question_id=question.id, decision="insufficient",
                                 evidence_node_ids=selected[:self.max_atoms], evidence_edge_ids=selected_edges[:self.max_atoms],
                                 rationale="Aday metinler var ancak güvenilir bir doğrudan veya sınırlı çoklu-hop ilişki kurulamadı.")

    def validate_generated_draft(self, draft: GeneratedQuestionDraft) -> TeacherValidation:
        """Accept a reverse-generated item only when its exact edge proves it.

        This is separate from retrieval validation: generated questions already
        know an edge privately, but the teacher agent must still ensure that
        the edge, its two approved endpoints and the verbatim quote form one
        direct, traceable claim.
        """
        edge = self.edges.get(draft.supporting_edge_id)
        source = self.nodes.get(edge.from_node) if edge else None
        target = self.nodes.get(edge.to_node) if edge else None
        if (edge is None or source is None or target is None
                or edge.relation.value != draft.relation_type
                or edge.source_ids != draft.source_ids
                or edge.quote != draft.source_quote
                or edge.source_checksum != draft.source_checksum
                or edge.page != draft.page or edge.bbox != draft.bbox):
            return TeacherValidation(
                question_id=draft.id, decision="insufficient",
                rationale="Taslak, kaynak alıntılı onaylı ilişki kenarıyla birebir eşleşmiyor.",
            )
        quote_terms = set(_terms(edge.quote))
        endpoint_terms = set(_terms(source.label)) | set(_terms(target.label))
        if not endpoint_terms or not (quote_terms & endpoint_terms):
            return TeacherValidation(
                question_id=draft.id, decision="insufficient",
                rationale="İlişki kenarının alıntısı iki düğümden en az birini açıkça taşımıyor.",
            )
        return TeacherValidation(
            question_id=draft.id, decision="direct", evidence_node_ids=[source.id, target.id],
            evidence_edge_ids=[edge.id], source_ids=edge.source_ids,
            rationale="Tersine üretilen soru, iki onaylı düğüm ve kaynak alıntılı tek ilişki kenarıyla doğrudan destekleniyor.",
            reviewer_kind="rule_based_teacher_candidate_v1",
        )

    def validate_with_retry(self, question: QuestionItem, analyzer: QuestionAnalyzerAndEliminator,
                            *, max_attempts: int = 3) -> TeacherValidation:
        """Use transparent ReAct-style query reformulation before abstaining.

        Retries add only terms already present in the question, topic and
        choices. They cannot inject an answer, a source quote or model-world
        knowledge into retrieval.
        """
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts 1 ile 3 arasında olmalı")
        first = analyzer.analyze_and_eliminate(question)
        verdict = self.validate(question, first)
        attempted: list[str] = []
        if verdict.decision != "insufficient" or max_attempts == 1:
            return verdict
        base_terms = list(dict.fromkeys([*question.question_terms, *_terms(question.topic), *_terms(question.stem)]))
        choice_terms = [term for choice in question.choices for term in _terms(choice.text)]
        variants = [
            " ".join(base_terms[:12]),
            " ".join([*base_terms[:7], *choice_terms[:8]]),
        ]
        for attempt, query in enumerate(variants[:max_attempts - 1], start=2):
            if not query.strip():
                continue
            attempted.append(query)
            retry_question = question.model_copy(update={"topic": query[:180]})
            retry = analyzer.analyze_and_eliminate(retry_question)
            candidate = self.validate(question, retry)
            if candidate.decision in {"direct", "bounded_inference"}:
                return candidate.model_copy(update={"retrieval_attempts": attempt, "retry_queries": attempted})
        return verdict.model_copy(update={"retrieval_attempts": 1 + len(attempted), "retry_queries": attempted})

    def _direct_overlap(self, question: QuestionItem, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None:
            return False
        query = set(_terms(" ".join([question.stem, question.topic, *question.question_terms,
                                      *(choice.text for choice in question.choices)])))
        evidence = set(_terms(" ".join([node.label, node.description, node.metadata.quote,
                                         *node.metadata.aliases])))
        return len(query & evidence) >= 2

    def _connected_bundle(self, question: QuestionItem, retrieval: RetrievalResult) -> tuple[list[str], list[str]]:
        query = set(_terms(" ".join([question.stem, question.topic, *question.question_terms,
                                      *(choice.text for choice in question.choices)])))
        candidates: list[str] = []
        for chain in retrieval.chains:
            chain_candidates: list[str] = []
            for hit in chain.hits:
                node = self.nodes.get(hit.node_id)
                if node is None or hit.node_id in chain_candidates:
                    continue
                evidence = set(_terms(" ".join([node.label, node.description, node.metadata.quote,
                                                 *node.metadata.aliases])))
                if len(query & evidence) >= 2:
                    chain_candidates.append(hit.node_id)
            if len(chain_candidates) < 2:
                continue
            # Search only source-approved edges with confidence, and grow a
            # single path within one choice's chain. Independent chunks and
            # evidence from different alternatives cannot be synthesized.
            for start in chain_candidates:
                selected = [start]
                remaining = set(chain_candidates) - {start}
                selected_edges: list[str] = []
                while remaining and len(selected) < self.max_atoms:
                    current = selected[-1]
                    link = next((edge for edge in self.edges.values()
                                 if edge.confidence >= self.min_edge_confidence
                                 and ((edge.from_node == current and edge.to_node in remaining)
                                      or (edge.to_node == current and edge.from_node in remaining))), None)
                    if link is None:
                        break
                    neighbor = link.to_node if link.from_node == current else link.from_node
                    selected.append(neighbor)
                    selected_edges.append(link.id)
                    remaining.remove(neighbor)
                if len(selected) >= 2 and selected_edges:
                    return selected, selected_edges
        return [], []


class GraphToQuestionGenerator:
    """Generate private drafts only from approved relation edges."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.nodes = {node.id: node for node in graph.approved_nodes()}
        self.edges = [edge for edge in graph.approved_edges() if edge.from_node in self.nodes and edge.to_node in self.nodes]

    def generate(self, *, limit: int = 40) -> list[GeneratedQuestionDraft]:
        if limit < 1:
            raise ValueError("limit pozitif olmalı")
        drafts: list[GeneratedQuestionDraft] = []
        used: set[tuple[str, str, str]] = set()
        relation_labels = {
            RelationType.ALT_KONUSUDUR: "alt konusudur",
            RelationType.SEBEBIDIR: "sebebidir",
            RelationType.SONUCUDUR: "sonucudur",
            RelationType.AMACIDIR: "amacıdır",
            RelationType.DONEMINDE_OLMUSTUR: "döneminde gerçekleşmiştir",
            RelationType.KRONOLOJIK_SONRASIDIR: "kronolojik olarak sonrasıdır",
            RelationType.AKTORUDUR: "aktörüdür",
            RelationType.COGRAFYASIDIR: "coğrafyasıdır",
            RelationType.KAPSAMINDADIR: "kapsamındadır",
            RelationType.ILKESIYLE_ILISKILIDIR: "ilkesiyle ilişkilidir",
            RelationType.CELISIR_TAVIZDIR: "çelişir veya taviz niteliğindedir",
            RelationType.BENZERIDIR_PARALELDIR: "benzer veya paraleldir",
        }
        relation_choices = [relation for relation in RelationType if relation in relation_labels]
        def importance(edge: Edge) -> tuple[float, float, str]:
            left = self.nodes[edge.from_node].metadata.node_weight
            right = self.nodes[edge.to_node].metadata.node_weight
            return (-(left + right) / 2, -edge.confidence, edge.id)

        for edge in sorted(self.edges, key=importance):
            # A generated item must point to a source quote with traceable PDF
            # provenance. A structural edge without a checked quote is skipped.
            if (len(edge.quote.strip()) < 12 or not edge.source_ids
                    or not edge.source_checksum or edge.page is None or edge.bbox is None):
                continue
            key = (edge.from_node, edge.to_node, edge.relation.value)
            if key in used:
                continue
            used.add(key)
            source = self.nodes[edge.from_node]
            target = self.nodes[edge.to_node]
            correct_relation = relation_labels[edge.relation]
            distractors = [relation_labels[relation] for relation in relation_choices if relation != edge.relation][:4]
            # Deterministic option order varies by edge, reducing answer-position
            # leakage while leaving the private key only on the draft wrapper.
            labels = ("A", "B", "C", "D", "E")
            rotation = int(hashlib.sha256(edge.id.encode()).hexdigest()[:4], 16) % len(labels)
            answer_index = rotation
            option_texts = distractors[:answer_index] + [correct_relation] + distractors[answer_index:]
            choices = [QuestionChoice(label=label, text=value)
                       for label, value in zip(labels, option_texts)]
            question = QuestionItem(
                id=f"generated:{edge.id}",
                stem=f"Kaynağa göre {source.label} ile {target.label} arasındaki ilişki hangisidir?",
                choices=choices,
                topic=source.metadata.unit_title or "",
                question_terms=[source.label, target.label, correct_relation],
            )
            drafts.append(GeneratedQuestionDraft(
                id=question.id, runtime_question=question, answer_label=labels[answer_index],
                supporting_edge_id=edge.id, relation_type=edge.relation.value,
                # Relation *type* is an annotation shared by unrelated
                # questions. Treating it as a concept would merge the entire
                # dataset into one split. The concrete edge remains a key.
                concept_keys=[source.id, target.id, f"edge:{edge.id}"],
                source_ids=edge.source_ids, source_quote=edge.quote,
                source_checksum=edge.source_checksum, page=edge.page, bbox=edge.bbox,
            ))
            if len(drafts) >= limit:
                break
        return drafts


class ConceptBasedDataSplitter:
    """Deterministically split whole concept groups without leakage."""

    def __init__(self, *, seed: int = 42):
        self.seed = seed

    def split(self, records: list[SplitRecord], *, train_ratio: float = 0.70,
              dev_ratio: float = 0.15) -> ConceptSplit:
        if not records or not 0 < train_ratio < 1 or not 0 < dev_ratio < 1 or train_ratio + dev_ratio >= 1:
            raise ValueError("Geçerli kayıt ve oranlar gerekli")
        # Union records transitively when they share any concept. Exact tuple
        # grouping is insufficient: {A,B} and {B,C} must stay in one split.
        parent = list(range(len(records)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        owner: dict[str, int] = {}
        for index, record in enumerate(records):
            if not record.concept_keys:
                raise ValueError(f"Kayıtta concept key eksik: {record.id}")
            for concept in set(record.concept_keys):
                if concept in owner:
                    union(index, owner[concept])
                else:
                    owner[concept] = index
        groups: dict[int, list[SplitRecord]] = defaultdict(list)
        for index, record in enumerate(records):
            groups[find(index)].append(record)
        components = []
        for items in groups.values():
            concepts = tuple(sorted({concept for item in items for concept in item.concept_keys}))
            digest = hashlib.sha256(f"{self.seed}|{'|'.join(concepts)}".encode()).hexdigest()
            components.append((digest, concepts, items))
        ordered = sorted(components)
        total = len(records)
        targets = {"train": total * train_ratio, "dev": total * dev_ratio, "test": total * (1 - train_ratio - dev_ratio)}
        buckets: dict[str, list[SplitRecord]] = {"train": [], "dev": [], "test": []}
        for _digest, _concepts, items in ordered:
            # A component is indivisible: concept leakage is more damaging
            # than a perfectly exact ratio. Prefer the bucket that incurs the
            # smallest overflow, then the closest target size.
            def assignment_cost(name: str) -> tuple[float, float, str]:
                projected = len(buckets[name]) + len(items)
                return (max(0.0, projected - targets[name]), abs(projected - targets[name]), name)

            destination = min(buckets, key=assignment_cost)
            buckets[destination].extend(items)
        concept_sets = {name: sorted({concept for item in items for concept in item.concept_keys})
                        for name, items in buckets.items()}
        return ConceptSplit(train=buckets["train"], dev=buckets["dev"], test=buckets["test"],
                            concept_sets=concept_sets, leakage_free=True, seed=self.seed)

