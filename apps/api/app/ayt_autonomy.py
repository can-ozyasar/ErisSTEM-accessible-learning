"""Source-bound analysis, bounded inference and private QLoRA data utilities.

The classes in this module are deliberately answer-key free at runtime.  They
can produce private research recommendations, but an agent decision is never
promoted to the student graph without an explicit human approval manifest.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from enum import Enum
from typing import Any, ClassVar, Literal

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
from .question_scope import AccessibilityAndScopeFilter


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


class DraftQualityReview(StrictModel):
    """A deterministic gate between source-traceability and QLoRA eligibility.

    A source-backed edge can still make a bad student question when an OCR
    fragment becomes an endpoint.  Traceability therefore proves neither
    Turkish readability nor pedagogical usability.  This review intentionally
    fails closed: a rejected draft remains a private repair candidate.
    """

    question_id: str
    accepted: bool
    issues: list[str] = Field(default_factory=list, max_length=16)
    reviewer_kind: str = "deterministic_draft_quality_gate_v1"


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
_NEGATIVE_RE = re.compile(r"\b(değildir|değil|olamaz|söylenemez|ulaşılamaz|yanlıştır|hangisi.*?dışında)\b", re.IGNORECASE)
_CHRONOLOGY_RE = re.compile(r"\b(önce|sonra|kronolojik|sıralama|ilk|son|ardından|öncelik)\b", re.IGNORECASE)
_INFERENCE_RE = re.compile(r"\b(çıkarılabilir|ulaşılabilir|gösterir|neden|sonuç|amaç|beklenir|yorum)\b", re.IGNORECASE)

_DRAFT_OCR_FRAGMENT_RE = re.compile(
    r"\b(?:istan|atlan|nort|tıriti|organizeyşın|dar|ön|pa)\s+"
    r"(?:bul|tik|lantik|besi|cülüğünde|rtisinin)\b",
    re.IGNORECASE,
)
_TRUNCATED_DATE_RELATION_RE = re.compile(r"\b\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+[12]\s+ile\s+\d{4}\b")
_LINEBREAK_WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]{2,}-\s+[a-zçğıöşüâîû]")
_GENERIC_ENDPOINT_START_RE = re.compile(r"^(?:bu|şu|o|ancak|ayrıca|ve|ile|da|de|bir|yüzyılda)\b", re.IGNORECASE)
_INCOMPLETE_ENDPOINT_END_RE = re.compile(r"\b(?:ile|ve|için|arasında|tarafından|amacıyla|nedeniyle|sonucunda)$", re.IGNORECASE)
_EVENT_LABEL_RE = re.compile(
    r"(?P<label>(?:[A-ZÇĞİÖŞÜI][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû0-9’'().\-]+\s+){1,6}"
    r"(?:Antlaşması|Savaşı|Savaşları|Cephesi|Kongresi|Harekâtı|Harekatı|Muharebesi|"
    r"Anayasası|Genelgesi|Meclisi|İnkılabı|İlanı|Kaldırılması))\b"
)


class GeneratedDraftQualityGate:
    """Reject malformed source-derived question drafts before any data split.

    The gate is deliberately narrow.  It does not judge historical truth;
    that belongs to ``HistoryTeacherValidatorAgent`` and source review.  It
    identifies mechanical failures which make a spoken question unusable:
    clipped dates, OCR-split words, sentence-sized relation endpoints and
    malformed five-choice items.
    """

    _temporal: ClassVar[set[str]] = {
        RelationType.DONEMINDE_OLMUSTUR.value,
        RelationType.KRONOLOJIK_SONRASIDIR.value,
    }

    @staticmethod
    def _endpoint_issues(value: str, *, temporal_source: bool = False) -> list[str]:
        compact = " ".join(value.split())
        words = _TOKEN_RE.findall(compact)
        problems: list[str] = []
        if not compact or len(compact) > 100 or len(words) > 14:
            problems.append("endpoint_too_long")
        if compact.endswith((".", ";", ":", ",")):
            problems.append("endpoint_is_sentence_fragment")
        if (_DRAFT_OCR_FRAGMENT_RE.search(compact) or _LINEBREAK_WORD_RE.search(compact)
                or "[" in compact or "]" in compact):
            problems.append("endpoint_has_ocr_artifact")
        if _GENERIC_ENDPOINT_START_RE.search(compact) or compact[:1].islower():
            problems.append("endpoint_is_generic_or_unfinished")
        if _INCOMPLETE_ENDPOINT_END_RE.search(compact):
            problems.append("endpoint_has_incomplete_grammar")
        if temporal_source and re.search(r"\b\d{4}\b", compact):
            problems.append("temporal_subject_contains_unparsed_date")
        return problems

    def review(self, draft: GeneratedQuestionDraft) -> DraftQualityReview:
        question = draft.runtime_question
        issues: list[str] = []
        stem = " ".join(question.stem.split())
        temporal_template = (draft.relation_type == RelationType.DONEMINDE_OLMUSTUR.value
                             and stem.startswith("Kaynağa göre ")
                             and stem.endswith((" hangi yılda imzalanmıştır?", " hangi yılda kurulmuştur?",
                                                " hangi yılda başlamıştır?", " hangi yılda sona ermiştir?",
                                                " hangi yılda gerçekleşmiştir?")))
        natural_relation_template = {
            RelationType.SEBEBIDIR.value: stem.endswith(" durumunun nedenlerinden hangisidir?"),
            RelationType.SONUCUDUR.value: stem.endswith(" durumunun sonuçlarından hangisidir?"),
            RelationType.AMACIDIR.value: stem.endswith(" uygulamasının amacı aşağıdakilerden hangisidir?"),
            RelationType.AKTORUDUR.value: stem.endswith(" eylemini gerçekleştiren taraf hangisidir?"),
        }.get(draft.relation_type, False)
        if not (temporal_template or natural_relation_template):
            issues.append("unsupported_question_template")
        if len(stem) > 235:
            issues.append("spoken_stem_too_long")
        if not AccessibilityAndScopeFilter().evaluate({
            "stem": stem,
            "choices": [choice.model_dump(mode="json") for choice in question.choices],
        }).eligible:
            issues.append("visual_question_out_of_scope")
        if _TRUNCATED_DATE_RELATION_RE.search(stem):
            issues.append("truncated_date_in_stem")
        if _DRAFT_OCR_FRAGMENT_RE.search(stem) or "[" in stem or "]" in stem:
            issues.append("ocr_artifact_in_stem")
        if (draft.relation_type == RelationType.AKTORUDUR.value
                and re.search(r"\b(?:kuruldu|atıldı|yapıldı|başlatıldı|imzalandı|"
                              r"gerçekleşti|sona erdi) eylemini gerçekleştiren taraf hangisidir\?$",
                              stem, re.IGNORECASE)):
            issues.append("actor_stem_has_finite_verb")
        if len(question.choices) != 5 or {choice.label for choice in question.choices} != {"A", "B", "C", "D", "E"}:
            issues.append("invalid_choice_set")
        if not any(choice.label == draft.answer_label for choice in question.choices):
            issues.append("missing_private_answer_position")
        answer = next((choice.text.strip() for choice in question.choices
                       if choice.label == draft.answer_label), "")
        if answer and answer.casefold() in stem.casefold():
            issues.append("answer_leaked_in_stem")
        if len({choice.text.strip().casefold() for choice in question.choices}) != len(question.choices):
            issues.append("duplicate_choice_text")
        for choice in question.choices:
            if not re.fullmatch(r"\d{4}", choice.text.strip()):
                issues.extend(self._endpoint_issues(choice.text))
        endpoints = [question.question_terms[0], answer] if question.question_terms and answer else []
        if len(endpoints) != 2:
            issues.append("missing_relation_endpoints")
        else:
            temporal = draft.relation_type in self._temporal
            issues.extend(self._endpoint_issues(endpoints[0], temporal_source=temporal))
            issues.extend(self._endpoint_issues(endpoints[1]))
            if temporal and not re.fullmatch(r"(?:MÖ\s*)?\d{4}", " ".join(endpoints[1].split())):
                issues.append("temporal_target_is_not_normalized_year")
            if temporal_template and any(not re.fullmatch(r"\d{4}", choice.text) for choice in question.choices):
                issues.append("temporal_choices_are_not_years")
        quote = " ".join(draft.source_quote.split())
        if len(quote) < 24 or _DRAFT_OCR_FRAGMENT_RE.search(quote) or _LINEBREAK_WORD_RE.search(quote):
            issues.append("source_quote_quality_risk")
        if quote.endswith((",", ";", ":")) or not quote.endswith((".", "!", "?", "”", "’")):
            issues.append("source_quote_incomplete")
        return DraftQualityReview(question_id=draft.id, accepted=not issues,
                                  issues=sorted(set(issues)))


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

    def _edge_endpoint_match(self, edge_id: str, query_terms: set[str],
                             choice_terms: set[str]) -> bool:
        edge = self._edges.get(edge_id)
        if edge is None:
            return False
        source = self.search.nodes.get(edge.from_node)
        target = self.search.nodes.get(edge.to_node)
        if (source is None or target is None or not edge.source_ids
                or not edge.source_checksum or edge.page is None or edge.bbox is None):
            return False
        quote = " ".join(edge.quote.split()).casefold()
        if not all(" ".join(node.label.split()).casefold() in quote for node in (source, target)):
            return False
        left, right = set(_terms(source.label)), set(_terms(target.label))
        specific_choice = choice_terms - query_terms
        return bool((left & query_terms and right & specific_choice)
                    or (right & query_terms and left & specific_choice))

    def _edge_supports_choice(self, edge_ids: list[str], query_terms: set[str], choice_terms: set[str]) -> bool:
        for edge_id in edge_ids:
            edge = self._edges.get(edge_id)
            if (edge and edge.relation != RelationType.CELISIR_TAVIZDIR
                    and self._edge_endpoint_match(edge_id, query_terms, choice_terms)):
                return True
        return False

    def _edge_is_relevant_contradiction(self, edge_id: str, query_terms: set[str],
                                        choice_terms: set[str]) -> bool:
        edge = self._edges.get(edge_id)
        return bool(edge and edge.relation == RelationType.CELISIR_TAVIZDIR
                    and self._edge_endpoint_match(edge_id, query_terms, choice_terms))

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
                       and any(edge_id in edge_ids and self._edge_has_verbatim_claim(self.edges[edge_id])
                               for edge_id in hit.supporting_edge_ids)
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
        if not self._edge_has_verbatim_claim(edge):
            return TeacherValidation(
                question_id=draft.id, decision="insufficient",
                rationale="İlişki alıntısı iki düğümü de birebir taşımıyor veya kaynak izi eksik.",
            )
        return TeacherValidation(
            question_id=draft.id, decision="direct", evidence_node_ids=[source.id, target.id],
            evidence_edge_ids=[edge.id], source_ids=edge.source_ids,
            rationale="Tersine üretilen soru, iki onaylı düğüm ve kaynak alıntılı tek ilişki kenarıyla doğrudan destekleniyor.",
            reviewer_kind="rule_based_teacher_candidate_v1",
        )

    def _edge_has_verbatim_claim(self, edge: Edge) -> bool:
        source = self.nodes.get(edge.from_node)
        target = self.nodes.get(edge.to_node)
        if (source is None or target is None or not edge.source_ids
                or not edge.source_checksum or edge.page is None or edge.bbox is None):
            return False
        quote = " ".join(edge.quote.split()).casefold()
        return all(" ".join(node.label.split()).casefold() in quote for node in (source, target))

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
                                 and self._edge_has_verbatim_claim(edge)
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


class QuestionAnalysisDecision(StrictModel):
    """Traceable result of scope, elimination, and evidence validation."""

    question_id: str
    eligible: bool
    scope_reasons: list[str] = Field(default_factory=list, max_length=8)
    format_tags: list[str] = Field(default_factory=list, max_length=3)
    analysis: QuestionAnalysis | None = None
    elimination: EliminationResult | None = None
    evidence_validation: TeacherValidation | None = None


class QuestionAnalyzerAndValidator:
    """One entry point that cannot analyze out-of-scope visual questions."""

    def __init__(self, search: WeightedGraphSearch, graph: KnowledgeGraph,
                 scope_filter: AccessibilityAndScopeFilter | None = None):
        self.search = search
        self.graph = graph
        self.scope_filter = scope_filter or AccessibilityAndScopeFilter()
        self.eliminator = QuestionAnalyzerAndEliminator(search)
        self.teacher_validator = HistoryTeacherValidatorAgent(graph)

    def evaluate(self, question: QuestionItem, *, section_id: str | None = None,
                 page: int | None = None, source_checksum: str | None = None,
                 top_k: int = 3) -> QuestionAnalysisDecision:
        scope = self.scope_filter.evaluate(
            question.model_dump(mode="json"), section_id=section_id, page=page,
            source_checksum=source_checksum,
        )
        if not scope.eligible:
            return QuestionAnalysisDecision(
                question_id=question.id, eligible=False,
                scope_reasons=list(scope.reasons), format_tags=list(scope.format_tags),
            )
        elimination = self.eliminator.analyze_and_eliminate(question, top_k=top_k)
        evidence = self.teacher_validator.validate(question, elimination)
        return QuestionAnalysisDecision(
            question_id=question.id, eligible=True,
            scope_reasons=list(scope.reasons), format_tags=list(scope.format_tags),
            analysis=elimination.analysis, elimination=elimination,
            evidence_validation=evidence,
        )


class GraphToQuestionGenerator:
    """Generate private drafts only from approved relation edges."""

    def __init__(self, graph: KnowledgeGraph, *, source_checksum: str | None = None,
                 page_ranges: list[tuple[int, int]] | None = None,
                 source_page_ranges: dict[str, list[tuple[int, int]]] | None = None):
        self.graph = graph
        self._page_ranges = page_ranges
        self._source_page_ranges = source_page_ranges or {}
        self.semantic_duplicates_collapsed = 0
        self.nodes = {node.id: node for node in graph.approved_nodes()}
        self.edges = [
            edge for edge in graph.approved_edges()
            if edge.from_node in self.nodes and edge.to_node in self.nodes
            and (self._edge_in_scope(edge) if self._source_page_ranges else
                 (source_checksum is None or edge.source_checksum == source_checksum)
                 and (page_ranges is None or edge.page is not None
                      and any(start <= edge.page <= end for start, end in page_ranges))
            )
        ]

    def _edge_in_scope(self, edge: Edge) -> bool:
        ranges = self._source_page_ranges.get(edge.source_checksum or "", [])
        return edge.page is not None and any(start <= edge.page <= end for start, end in ranges)

    def _ranges_for_edge(self, edge: Edge) -> list[tuple[int, int]]:
        if self._source_page_ranges:
            return self._source_page_ranges.get(edge.source_checksum or "", [])
        return self._page_ranges or []

    @staticmethod
    def _normalize_fingerprint(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(re.sub(r"[^\w\s]", " ", normalized).split())

    @staticmethod
    def _source_relation_phrases(edge: Edge) -> dict[str, str] | None:
        """Extract short spoken endpoints from one source-bound sentence.

        Graph extraction keeps broad spans for provenance.  This pass narrows
        only around an explicit relation cue; it never invents text outside
        the quoted PDF sentence.
        """
        quote = re.sub(
            r"(?<=[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû])-\s+(?=[a-zçğıöşüâîû])", "", edge.quote,
        )
        quote = " ".join(quote.split()).strip(" \"“”‘’")
        if not quote.endswith((".", "!", "?")):
            return None
        if edge.relation == RelationType.AKTORUDUR:
            match = re.search(
                r"(?P<subject>[^.;,]{3,120}),\s*(?P<actor>[^.;,]{3,100})\s+tarafından\s+"
                r"(?P<action>[^.;]{3,180})[.!?]$", quote, re.IGNORECASE,
            )
            if not match:
                return None
            subject = " ".join(match.group("subject").split()).strip(" :")
            actor = " ".join(match.group("actor").split()).strip(" :")
            action = " ".join(match.group("action").split()).strip(" :")
            if (not 2 <= len(subject.split()) <= 12 or not 1 <= len(actor.split()) <= 8
                    or not 1 <= len(action.split()) <= 16
                    or re.search(r"\b(?:amacıyla|nedeniyle|sonucunda)\b", action, re.IGNORECASE)):
                return None
            return {"subject": subject, "answer": actor, "action": action}
        if edge.relation == RelationType.SEBEBIDIR:
            match = re.search(
                r"(?P<cause>[^.;]{12,180})\s+(?:nedeniyle|sebebiyle|yüzünden|dolayı)\s+"
                r"(?P<effect>[^.;]{8,180})[.!?]$", quote, re.IGNORECASE,
            )
            if not match:
                return None
            return {"subject": " ".join(match.group("effect").split()).strip(" :"),
                    "answer": " ".join(match.group("cause").split()).strip(" :")}
        if edge.relation == RelationType.SONUCUDUR:
            match = re.search(
                r"(?P<cause>[^.;]{12,180})\s+sonucunda\s+(?P<effect>[^.;]{8,180})[.!?]$",
                quote, re.IGNORECASE,
            )
            if not match:
                return None
            return {"subject": " ".join(match.group("cause").split()).strip(" :"),
                    "answer": " ".join(match.group("effect").split()).strip(" :")}
        return None

    @staticmethod
    def _source_temporal_phrase(edge: Edge, target_label: str) -> str | None:
        """Find a compact named event near the edge's source year.

        ``explicit_year`` graph edges often preserve an entire paragraph as
        their source endpoint.  A date question is allowed only when a named
        event ending (Antlaşması, Cephesi, Harekâtı, ...) occurs close to the
        exact year in that same quote.  Ambiguous paragraphs stay review-only.
        """
        if edge.relation != RelationType.DONEMINDE_OLMUSTUR:
            return None
        year = target_label.strip()
        if not re.fullmatch(r"\d{4}", year):
            return None
        if year is None:
            return None
        quote = re.sub(
            r"(?<=[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû])-\s+(?=[a-zçğıöşüâîû])", "", edge.quote,
        )
        quote = " ".join(quote.split())
        year_positions = [match.start() for match in re.finditer(rf"(?<!\d){year}(?!\d)", quote)]
        if len(year_positions) != 1:
            return None
        candidates = []
        for match in _EVENT_LABEL_RE.finditer(quote):
            label = " ".join(match.group("label").split()).strip(" ,;:-")
            if re.search(r"\b(?:19|20)\d{2}\b", label) or len(label.split()) > 8:
                continue
            if abs(match.start() - year_positions[0]) <= 110:
                candidates.append(label)
        return candidates[0] if len(candidates) == 1 else None

    def generate(self, *, limit: int = 40) -> list[GeneratedQuestionDraft]:
        if limit < 1:
            raise ValueError("limit pozitif olmalı")
        self.semantic_duplicates_collapsed = 0
        drafts: list[GeneratedQuestionDraft] = []
        used: set[tuple[str, str, str]] = set()
        used_question_fingerprints: set[tuple[str, str, str]] = set()
        supported_templates = {
            RelationType.DONEMINDE_OLMUSTUR, RelationType.SEBEBIDIR,
            RelationType.SONUCUDUR, RelationType.AMACIDIR, RelationType.AKTORUDUR,
        }
        def section_key(edge: Edge) -> str:
            edge_ranges = self._ranges_for_edge(edge)
            if edge.page is not None and edge_ranges:
                for start, end in edge_ranges:
                    if start <= edge.page <= end:
                        return f"{edge.source_checksum}:pages:{start}-{end}"
            return self.nodes[edge.from_node].metadata.section_id or ""
        def importance(edge: Edge) -> tuple[float, float, str]:
            left = self.nodes[edge.from_node].metadata.node_weight
            right = self.nodes[edge.to_node].metadata.node_weight
            return (-(left + right) / 2, -edge.confidence, edge.id)

        # KAPSAMINDADIR is useful for graph navigation but produces shallow
        # "paragraph belongs to heading" questions.  Keep it out of the
        # coaching corpus.  Round-robin the remaining relation types so a
        # frequent date relation cannot crowd out explicit cause, purpose or
        # actor evidence.
        by_relation: dict[RelationType, list[Edge]] = defaultdict(list)
        for edge in sorted(self.edges, key=importance):
            if edge.relation in supported_templates:
                by_relation[edge.relation].append(edge)
        ordered_edges: list[Edge] = []
        while any(by_relation.values()):
            for relation in sorted(by_relation, key=lambda value: value.value):
                if by_relation[relation]:
                    ordered_edges.append(by_relation[relation].pop(0))
        # A natural content question needs content alternatives, not five
        # relation labels.  All option phrases are still source-verbatim graph
        # endpoints; only the one backed by the current edge is correct.
        target_pool: dict[tuple[RelationType, str, str, str], list[str]] = defaultdict(list)
        supported_targets: dict[tuple[str, RelationType], set[str]] = defaultdict(set)
        natural_by_edge = {edge.id: self._source_relation_phrases(edge) for edge in self.edges}
        temporal_by_edge = {
            edge.id: self._source_temporal_phrase(edge, self.nodes[edge.to_node].label)
            for edge in self.edges
        }
        temporal_action_by_edge = {
            edge.id: next((value for value in ("signed", "founded", "convened", "started", "ended", "occurred")
                           if value in (edge.extraction_method or "")), "dated")
            for edge in self.edges
        }
        for edge in self.edges:
            if (edge.relation == RelationType.DONEMINDE_OLMUSTUR
                    and not ((edge.extraction_method or "").startswith("source_verbatim_named_event_year_")
                             or temporal_by_edge.get(edge.id))):
                continue
            target_node = self.nodes[edge.to_node]
            natural = natural_by_edge.get(edge.id)
            target = temporal_by_edge.get(edge.id) or (natural or {}).get("answer", target_node.label)
            if edge.relation == RelationType.DONEMINDE_OLMUSTUR:
                target = target_node.label
            supported_targets[(edge.from_node, edge.relation)].add(target)
            action = ((edge.extraction_method or "").rsplit("_", 1)[-1]
                      if edge.relation == RelationType.DONEMINDE_OLMUSTUR else "")
            if edge.relation == RelationType.DONEMINDE_OLMUSTUR:
                action = "dated"
            edge_ranges = self._ranges_for_edge(edge)
            pool_section = ("temporal_scope" if edge.relation == RelationType.DONEMINDE_OLMUSTUR
                            and len(edge_ranges) >= 3 else section_key(edge))
            pool_key = (edge.relation, target_node.node_type.value, pool_section, action)
            if (edge.relation != RelationType.KAPSAMINDADIR
                    and not GeneratedDraftQualityGate._endpoint_issues(target)
                    and target not in target_pool[pool_key]):
                target_pool[pool_key].append(target)
        for edge in ordered_edges:
            # A generated item must point to a source quote with traceable PDF
            # provenance. A structural edge without a checked quote is skipped.
            if (len(edge.quote.strip()) < 12 or not edge.source_ids
                    or not edge.source_checksum or edge.page is None or edge.bbox is None):
                continue
            if (edge.relation == RelationType.DONEMINDE_OLMUSTUR
                    and not ((edge.extraction_method or "").startswith("source_verbatim_named_event_year_")
                             or temporal_by_edge.get(edge.id))):
                continue
            key = (edge.from_node, edge.to_node, edge.relation.value)
            if key in used:
                self.semantic_duplicates_collapsed += 1
                continue
            used.add(key)
            source = self.nodes[edge.from_node]
            target = self.nodes[edge.to_node]
            natural = natural_by_edge.get(edge.id)
            question_terms = [source.label]
            # Deterministic option order varies by edge, reducing answer-position
            # leakage while leaving the private key only on the draft wrapper.
            labels = ("A", "B", "C", "D", "E")
            rotation = int(hashlib.sha256(edge.id.encode()).hexdigest()[:4], 16) % len(labels)
            answer_index = rotation
            temporal_source = temporal_by_edge.get(edge.id)
            if edge.relation == RelationType.DONEMINDE_OLMUSTUR and re.fullmatch(r"\d{4}", target.label):
                # A subject linked to several years needs a more specific
                # action/event cue before it can yield a single-answer item.
                if len(supported_targets[(edge.from_node, edge.relation)]) != 1:
                    continue
                # Dates must be real alternatives supported by other graph
                # events in the same section, not invented numeric offsets.
                action = "dated"
                temporal_pool_section = ("temporal_scope" if len(self._ranges_for_edge(edge)) >= 3
                                         else section_key(edge))
                pool_key = (edge.relation, target.node_type.value, temporal_pool_section, action)
                distractors = [value for value in target_pool[pool_key]
                               if value not in supported_targets[(edge.from_node, edge.relation)]
                               and re.fullmatch(r"\d{4}", value)]
                if len(distractors) < 4:
                    continue
                distractors = distractors[:4]
                correct_value = target.label
                temporal_verb = {
                    "signed": "imzalanmıştır", "founded": "kurulmuştur",
                    "convened": "toplanmıştır", "started": "başlamıştır",
                    "ended": "sona ermiştir", "occurred": "gerçekleşmiştir",
                    "dated": "gerçekleşmiştir",
                }.get(temporal_action_by_edge.get(edge.id, "dated"), "gerçekleşmiştir")
                stem = f"Kaynağa göre {temporal_source or source.label} hangi yılda {temporal_verb}?"
                question_terms = [temporal_source or source.label]
            elif natural is not None and edge.relation in {
                    RelationType.AKTORUDUR, RelationType.SEBEBIDIR, RelationType.SONUCUDUR,
            }:
                natural_subject = natural["subject"]
                correct_value = natural["answer"]
                pool_key = (edge.relation, target.node_type.value, section_key(edge), "")
                candidates = [value for value in target_pool[pool_key] if value != correct_value]
                if len(candidates) < 4:
                    continue
                distractors = candidates[:4]
                template = {
                    RelationType.SEBEBIDIR: f"Kaynağa göre {natural_subject} durumunun nedenlerinden hangisidir?",
                    RelationType.SONUCUDUR: f"Kaynağa göre {natural_subject} durumunun sonuçlarından hangisidir?",
                    RelationType.AKTORUDUR: (
                        f"Kaynağa göre \"{natural_subject}\" cümlesinde {natural['action']} "
                        "eylemini gerçekleştiren taraf hangisidir?"
                    ),
                }
                stem = template[edge.relation]
                question_terms = [natural_subject]
            else:
                pool_key = (edge.relation, target.node_type.value, section_key(edge), "")
                known_answers = supported_targets[(edge.from_node, edge.relation)]
                candidates = [value for value in target_pool[pool_key] if value not in known_answers]
                if len(candidates) < 4:
                    continue
                distractors = candidates[:4]
                correct_value = target.label
                template = {
                    RelationType.SEBEBIDIR: f"Kaynağa göre {source.label} durumunun nedenlerinden hangisidir?",
                    RelationType.SONUCUDUR: f"Kaynağa göre {source.label} durumunun sonuçlarından hangisidir?",
                    RelationType.AMACIDIR: f"Kaynağa göre {source.label} uygulamasının amacı aşağıdakilerden hangisidir?",
                    RelationType.AKTORUDUR: f"Kaynağa göre {source.label} eylemini gerçekleştiren taraf hangisidir?",
                }
                stem = template[edge.relation]
                question_terms = [source.label]
            natural = natural_by_edge[edge.id]
            fingerprint_subject = (temporal_source if temporal_source else
                                   natural["subject"] if natural else source.label)
            fingerprint = (edge.relation.value, self._normalize_fingerprint(fingerprint_subject),
                           self._normalize_fingerprint(correct_value))
            if fingerprint in used_question_fingerprints:
                self.semantic_duplicates_collapsed += 1
                continue
            used_question_fingerprints.add(fingerprint)
            option_texts = distractors[:answer_index] + [correct_value] + distractors[answer_index:]
            choices = [QuestionChoice(label=label, text=value)
                       for label, value in zip(labels, option_texts)]
            question = QuestionItem(
                id=f"generated:{edge.id}",
                stem=stem,
                choices=choices,
                topic=source.metadata.unit_title or "",
                # Only terms already visible in the public stem may enter
                # retrieval. The private correct target must not bias search.
                question_terms=question_terms,
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
            def assignment_cost(name: str, group_size: int = len(items)) -> tuple[float, float, str]:
                projected = len(buckets[name]) + group_size
                return (max(0.0, projected - targets[name]), abs(projected - targets[name]), name)

            destination = min(buckets, key=assignment_cost)
            buckets[destination].extend(items)
        concept_sets = {name: sorted({concept for item in items for concept in item.concept_keys})
                        for name, items in buckets.items()}
        return ConceptSplit(train=buckets["train"], dev=buckets["dev"], test=buckets["test"],
                            concept_sets=concept_sets, leakage_free=True, seed=self.seed)

