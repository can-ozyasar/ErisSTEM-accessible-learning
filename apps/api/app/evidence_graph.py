"""Source-bound evidence bundles and relation graph validation."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROLES = frozenset({"primary", "context", "relation", "contrast"})
RELATIONS = frozenset({"gerceklesti_tarih", "gerceklesti_yer", "once_geldi", "sonra_geldi", "neden_oldu", "sonuc_oldu", "gerceklestirdi", "tanımlar", "iliskilidir"})
NODE_KINDS = frozenset({"kisi", "olay", "tarih_donem", "yer", "kavram"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceCard(StrictModel):
    source_id: str = Field(min_length=8, max_length=80)
    role: Literal["primary", "context", "relation", "contrast"]
    quote: str = Field(min_length=12, max_length=520)


class EvidenceBundle(StrictModel):
    cards: list[EvidenceCard] = Field(min_length=1, max_length=4)
    reviewer: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=10, max_length=600)
    approved: bool

    @field_validator("cards")
    @classmethod
    def unique_roles_and_sources(cls, value: list[EvidenceCard]):
        if len({card.role for card in value}) != len(value) or len({card.source_id for card in value}) != len(value):
            raise ValueError("Her kanıt rolü ve kaynak parçası yalnız bir kez kullanılabilir")
        if not any(card.role == "primary" for card in value):
            raise ValueError("Kanıt demetinde primary rolü gerekli")
        return value


class GraphNode(StrictModel):
    id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=2, max_length=120)
    kind: Literal["kisi", "olay", "tarih_donem", "yer", "kavram"]
    aliases: list[str] = Field(default_factory=list, max_length=12)
    temporal: TemporalRange | None = None

    @model_validator(mode="after")
    def temporal_only_for_periods(self):
        if self.temporal is not None and self.kind != "tarih_donem":
            raise ValueError("Zaman aralığı yalnız tarih/dönem düğümünde tutulabilir")
        return self


class TemporalRange(StrictModel):
    """Normalised timeline coordinates; they are display aids, never proof."""
    start_year: int | None = Field(default=None, ge=-5000, le=2500)
    end_year: int | None = Field(default=None, ge=-5000, le=2500)
    precision: Literal["year", "range", "century", "period", "unknown"] = "unknown"
    era: Literal["mo", "ms", "mixed", "unknown"] = "unknown"

    @model_validator(mode="after")
    def chronological_range(self):
        if self.start_year is not None and self.end_year is not None and self.start_year > self.end_year:
            raise ValueError("Zaman aralığının başlangıcı bitişinden sonra olamaz")
        if self.precision == "year" and self.start_year != self.end_year:
            raise ValueError("Yıl hassasiyeti için başlangıç ve bitiş aynı olmalı")
        return self


class GraphEdge(StrictModel):
    id: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9_-]+$")
    from_node: str = Field(min_length=3, max_length=80)
    to_node: str = Field(min_length=3, max_length=80)
    relation: Literal["gerceklesti_tarih", "gerceklesti_yer", "once_geldi", "sonra_geldi", "neden_oldu", "sonuc_oldu", "gerceklestirdi", "tanımlar", "iliskilidir"]
    source_id: str = Field(min_length=8, max_length=80)
    quote: str = Field(min_length=12, max_length=520)
    approved: bool

    @model_validator(mode="after")
    def no_self_relation(self):
        if self.from_node == self.to_node:
            raise ValueError("İlişkinin iki ucu aynı düğüm olamaz")
        return self


def validate_bundle(bundle: EvidenceBundle, allowed_sources: dict[str, str]) -> None:
    for card in bundle.cards:
        if card.source_id not in allowed_sources or card.quote not in allowed_sources[card.source_id]:
            raise ValueError("Kanıt alıntısı onaylı kaynak parçasında birebir bulunmalı")
    if bundle.approved and not any(card.role == "primary" for card in bundle.cards):
        raise ValueError("Onaylı demette primary kanıt gerekli")


def validate_edge(edge: GraphEdge, nodes: dict[str, GraphNode], allowed_sources: dict[str, str]) -> None:
    if edge.from_node not in nodes or edge.to_node not in nodes:
        raise ValueError("İlişkinin düğümleri grafikte bulunmalı")
    if edge.source_id not in allowed_sources or edge.quote not in allowed_sources[edge.source_id]:
        raise ValueError("İlişki alıntısı onaylı kaynak parçasında birebir bulunmalı")
    if not edge.approved:
        raise ValueError("Öğrenci grafiğine yalnız onaylı ilişki yazılabilir")


def relation_proposals(sources: list[dict]) -> list[dict]:
    """Explainable, conservative proposals; never writes graph edges."""
    proposals = []
    date = re.compile(r"\b(?:M[ÖS]\.?\s*)?\d{1,4}\b", re.IGNORECASE)
    for source in sources:
        text = source["text"]
        for match in date.finditer(text):
            quote = text[max(0, match.start() - 80): min(len(text), match.end() + 120)].strip()
            if len(quote) >= 12:
                proposals.append({"source_id": source["id"], "relation": "gerceklesti_tarih", "quote": quote,
                                  "reason": "kaynakta tarih/dönem ifadesi"})
                break
    return proposals[:8]
