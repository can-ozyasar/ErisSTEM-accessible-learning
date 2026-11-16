"""Review-gated, source-bound examples for the history coach QLoRA run."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ayt_autonomy import ConceptBasedDataSplitter, SplitRecord
from .tutor_coach import ANSWER_LABEL

CASES = (
    "soruyu_anlama", "hatirlayani_ortaya_cikar", "kanitla_bag_kur", "siki_sina",
    "yanlis_cevabi_duzelt", "dogruyu_pekistir",
)
EARLY_ANSWER_CASES = set(CASES[:4])
ERROR_TYPES = ("kisi", "tarih", "yer", "kronoloji", "neden_sonuc", "kaynak_yorumu", "asiri_genelleme", "genel")
CONCEPT_KEYS_SOURCE = "approved_graph_edges_v1"
GROUNDING_MODES = ("source_evidence", "question_derived_recall")


class TutorReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question_id: str = Field(min_length=3, max_length=80)
    case: str
    error_type: str
    grounding_mode: str = "source_evidence"
    source_ids: list[str] = Field(default_factory=list, max_length=2)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=2)
    # Server-derived from the reviewed evidence graph and source chunks.
    # Client-supplied values are discarded by the route before persistence.
    concept_keys: list[str] = Field(default_factory=list, max_length=128)
    concept_keys_source: str = Field(default="", max_length=80)
    learner_state: str = Field(min_length=3, max_length=400)
    coaching_goal: str = Field(min_length=8, max_length=300)
    guide_response: str = Field(min_length=10, max_length=600)
    early_answer_disclosed: bool
    grounded_in_source: bool
    simple_turkish: bool
    age_appropriate: bool
    reviewed_by: str = Field(min_length=2, max_length=120)
    approved: bool
    expected_revision: int = Field(ge=0)

    @field_validator("case")
    @classmethod
    def known_case(cls, value: str):
        if value not in CASES:
            raise ValueError("Bilinmeyen koçluk durumu")
        return value

    @field_validator("error_type")
    @classmethod
    def known_error_type(cls, value: str):
        if value not in ERROR_TYPES:
            raise ValueError("Bilinmeyen hata türü")
        return value

    @field_validator("grounding_mode")
    @classmethod
    def known_grounding_mode(cls, value: str):
        if value not in GROUNDING_MODES:
            raise ValueError("Bilinmeyen kanıtlama kipi")
        return value

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[str]):
        if len(value) != len(set(value)):
            raise ValueError("Kaynak parça kimlikleri tekrarlanamaz")
        return value

    @field_validator("concept_keys")
    @classmethod
    def unique_concepts(cls, value: list[str]):
        normalized = [item.strip() for item in value]
        if any(not item or len(item) > 160 for item in normalized):
            raise ValueError("Kavram kimlikleri dolu ve kısa olmalı")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Kavram kimlikleri tekrarlanamaz")
        return normalized

    @field_validator("evidence_quotes")
    @classmethod
    def short_quotes(cls, value: list[str]):
        if any(len(item) > 520 for item in value):
            raise ValueError("Kaggle örneğindeki MEB kanıtı 520 karakteri aşamaz")
        return value

    @model_validator(mode="after")
    def stage_evidence_contract(self):
        if len(self.source_ids) != len(self.evidence_quotes):
            raise ValueError("Her kaynak kimliği için bir kısa MEB kanıtı gerekli")
        is_recall_probe = self.case in CASES[2:4] and self.grounding_mode == "question_derived_recall"
        if self.grounding_mode == "question_derived_recall" and (not is_recall_probe or self.source_ids):
            raise ValueError("Soru kökünden hatırlama kipi yalnız kanıtsız üçüncü ve dördüncü aşamada kullanılabilir")
        if is_recall_probe and self.grounded_in_source:
            raise ValueError("Kaynak alıntısız hatırlama turu kaynak bağlı olarak işaretlenemez")
        if self.case not in CASES[:2] and not self.source_ids and not is_recall_probe:
            raise ValueError("Kanıtla bağ kurma ve sonraki aşamalarda kaynak gerekli")
        return self

    def approved_quality(self) -> bool:
        grounded = self.grounded_in_source or self.grounding_mode == "question_derived_recall"
        return self.approved and grounded and self.simple_turkish and self.age_appropriate and not self.early_answer_disclosed


def review_id(question_id: str, case: str) -> str:
    return f"tutor-review-v2:{question_id}:{case}"


def derive_concept_keys(graph: dict) -> list[str]:
    """Derive leakage concepts from endpoints of approved graph relations only."""
    concepts: set[str] = set()
    if graph.get("approved"):
        for edge in graph.get("edges", []):
            if not edge.get("approved"):
                continue
            concepts.update(f"node:{edge[key]}" for key in ("from_node", "to_node") if edge.get(key))
    return sorted(concepts)


def split_question_ids(question_ids: Iterable[str],
                       concept_keys_by_question: dict[str, list[str]]) -> dict[str, str]:
    ids = sorted(set(question_ids))
    if len(ids) != 120:
        raise ValueError("Bölme işlemi tam 120 soru grubuyla yapılır")
    records = []
    for question_id in ids:
        concepts = sorted(set(concept_keys_by_question.get(question_id, [])))
        if not concepts:
            raise ValueError(f"Kavram tabanlı bölme için concept key eksik: {question_id}")
        records.append(SplitRecord(id=question_id, concept_keys=concepts, payload={}))
    split = ConceptBasedDataSplitter(seed=42).split(records)
    if not split.train or not split.dev or not split.test:
        raise ValueError("Kavram kümeleri üç bölüme ayrılmaya yetmedi; sızıntısız kapalı test üretilemedi")
    return {record.id: name for name, bucket in (
        ("train", split.train), ("dev", split.dev), ("sealed_test", split.test)
    ) for record in bucket}


def validate_review_payload(item: TutorReviewInput, allowed_sources: dict[str, str]) -> None:
    if not set(item.source_ids).issubset(allowed_sources):
        raise ValueError("Seçilen kaynak parçası bu sorunun onaylı getirme sonucunda yok")
    if len(item.source_ids) != len(item.evidence_quotes):
        raise ValueError("Her kaynak kimliği için bir kısa MEB kanıtı gerekli")
    if any(quote not in allowed_sources[source_id] for source_id, quote in zip(item.source_ids, item.evidence_quotes)):
        raise ValueError("MEB kanıtı seçilen kaynak parçasından birebir alınmalı")
    if item.approved and not item.approved_quality():
        raise ValueError("Onay için kaynak bağlılık, sade Türkçe, yaş düzeyi ve cevap ifşası kontrolleri olumlu olmalı")
    if item.case in EARLY_ANSWER_CASES and ANSWER_LABEL.search(item.guide_response):
        raise ValueError("Bu aşamada rehber yanıt cevap veya şık ifşa edemez")


def export_rows(records: Iterable[dict]) -> tuple[dict[str, list[dict]], dict]:
    approved = [item for item in records if item.get("approved")]
    by_question: dict[str, dict[str, dict]] = {}
    for item in approved:
        by_question.setdefault(item["question_id"], {})[item["case"]] = item
    complete = {key: value for key, value in by_question.items() if set(value) == set(CASES)}
    if len(complete) < 120:
        raise ValueError("Dışa aktarma için altı durumu da onaylı en az 120 soru gerekir")
    selected_ids = sorted(complete)[:120]
    if any(item.get("concept_keys_source") != CONCEPT_KEYS_SOURCE or not item.get("concept_keys")
           for question_id in selected_ids for item in complete[question_id].values()):
        raise ValueError("Concept split için onaylı graf kenarlarından sunucuda türetilmiş anahtar gerekli")
    concepts_by_question = {
        question_id: sorted({concept for item in complete[question_id].values()
                             for concept in item.get("concept_keys", [])})
        for question_id in selected_ids
    }
    rows = {"train": [], "dev": [], "sealed_test": []}
    for question_id, split in split_question_ids(selected_ids, concepts_by_question).items():
        for case in CASES:
            item = complete[question_id][case]
            prompt_lines = [
                "Sen AYT tarih soru koçusun. Öğrenciyi düşündür; 11-12. sınıf düzeyinde kısa ve doğal Türkçe kullan.",
                "Cevabı veya doğru şıkkı, öğrenci denemeden açıklama.",
                f"Koçluk durumu: {case}", f"Hata türü: {item['error_type']}",
                f"Soru: {item['question_text']}", f"Öğrenci: {item['learner_state']}",
            ]
            if item.get("grounding_mode") == "question_derived_recall":
                prompt_lines.append("Yalnız soru ve öğrencinin ifadesinden hareketle hatırlama sorusu sor; yeni tarih, kişi veya olay bilgisi ekleme.")
            if item["evidence_quotes"]:
                prompt_lines.append("MEB kanıtı: " + " ".join(item["evidence_quotes"]))
            prompt = "\n".join([*prompt_lines, "Koç:"])
            rows[split].append({"group_id": question_id, "case": case, "error_type": item["error_type"],
                                "prompt": prompt, "completion": item["guide_response"]})
    counts = Counter(row["group_id"] for bucket in rows.values() for row in bucket)
    if len(counts) != 120 or any(count != 6 for count in counts.values()):
        raise ValueError("Aynı sorunun altı turu tek veri bölümünde kalmalı")
    return rows, {"question_groups": 120, "examples": 720,
                  "splits": {key: len(value) for key, value in rows.items()},
                  "split_strategy": "transitive_concept_components_v1",
                  "contains_short_reviewed_evidence": True, "contains_answer_keys": False}
