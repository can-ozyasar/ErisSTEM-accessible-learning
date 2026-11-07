"""Build a traceable research graph from high-signal MEB evidence atoms.

The output is explicitly an agent-reviewed research graph.  It is useful for
building a private QLoRA pilot, but it must not be configured as student
runtime data until the normal approval manifest promotes the same sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ..ayt_knowledge_graph import Edge, HistoricalNode, KnowledgeGraph, NodeMetadata, NodeType, RelationType


YEAR_RE = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")
EXCLUDE_RE = re.compile(r"\b(soru|hangisi|belirtiniz|etkinlik|görsel|tablo|cevaplayınız|tartışınız)\b", re.I)
EVENT_RE = re.compile(r"\b(savaş|muharebe|antlaşma|antlaşması|kongre|genelge|meclis|hareketi|inkılap)\b", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
CAUSE_RE = re.compile(r"(?P<cause>.{12,220}?)\s+(?:nedeniyle|sebebiyle|yüzünden|dolayı)\s+(?P<effect>.{12,220}?)(?:[.!?]|$)", re.I)
RESULT_RE = re.compile(r"(?P<cause>.{12,220}?)\s+sonucunda\s+(?P<effect>.{12,220}?)(?:[.!?]|$)", re.I)
PURPOSE_RE = re.compile(r"(?P<purpose>.{12,180}?)\s+amacıyla\s+(?P<action>.{12,220}?)(?:[.!?]|$)", re.I)
ACTOR_RE = re.compile(r"(?P<actor>.{3,140}?)\s+tarafından\s+(?P<action>.{12,220}?)(?:[.!?]|$)", re.I)
AFTER_RE = re.compile(r"(?P<first>.{12,220}?)\s+(?:ardından|akabinde|sonra)\s+(?P<second>.{12,220}?)(?:[.!?]|$)", re.I)
EVENT_TITLE_RE = re.compile(
    r"\b(?P<event>(?:[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû’'\-]+"
    r"(?:\s+(?:[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû’'\-]+|[a-zçğıöşüâîû]+)){0,5})"
    r"\s+(?:Antlaşması|Antlaşması|Sözleşmesi|Kongresi|Genelgesi|Savaşı|Harekâtı|Harekatı|"
    r"Meclisi|Hareketi|Konferansı|Darbesi|Reformu|Seferi|Mücadelesi|Teşkilatı|Örgütü))\b"
)
LINE_END_HYPHEN_RE = re.compile(r"(?<=[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû])-\s+(?=[a-zçğıöşüâîû])")
TEMPORAL_ACTION_RE = re.compile(r"\b(?P<action>imzalandı|kuruldu|toplandı|başladı|sona erdi|gerçekleşti)\b", re.I)
TEMPORAL_CONTEXT_RISK_RE = re.compile(r"\b(?:devam ederken|sonrasında|sırasında|öncesinde|esnasında)\b", re.I)


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _eligible(chunk: dict) -> bool:
    quality = chunk.get("quality", {})
    review = chunk.get("pre_review", {})
    text = str(chunk.get("text", "")).strip()
    return (
        # ``manual_review`` is a source-quality queue state, not a statement
        # that the text is false.  For this private research graph we admit a
        # clean manual-review candidate only as a source-coordinate-bound
        # draft; it still cannot enter student runtime or QLoRA without the
        # later teacher and spoken-question quality gates.
        review.get("decision") in {"review_for_approval", "manual_review"}
        and len(text) >= 40
        and not EXCLUDE_RE.search(text)
        and not quality.get("visual_or_caption_risk")
        and not quality.get("instruction_risk")
        and not quality.get("ocr_fragment_risk")
        and chunk.get("page") is not None
        and chunk.get("bbox") is not None
    )


def _node_type(text: str) -> NodeType:
    if re.search(r"\bantlaşma(sı)?\b", text, re.I):
        return NodeType.ANTLASMA_BELGE
    if EVENT_RE.search(text):
        return NodeType.OLAY_SAVAS
    return NodeType.KAVRAM_ILKE


def _phrase(value: str) -> str:
    """Return a short source-verbatim claim label, never a generated summary."""
    compact = " ".join(value.strip(" ,;:-").split())
    if len(compact) > 180:
        compact = compact[:180].rsplit(" ", 1)[0]
    return compact


def _normalize_layout_ocr(text: str) -> str:
    """Repair only deterministic PDF line-end hyphenation for spoken text.

    The corpus retains the original PDF extraction and crop. This display
    normalization changes only ``ilişki- lerinde``-style line breaks, while
    preserving in-word hyphens, numbers and source coordinates.
    """
    return " ".join(LINE_END_HYPHEN_RE.sub("", text).split())


def _explicit_relations(text: str) -> list[tuple[str, str, RelationType, str]]:
    """Extract only cue-marked relations from one source sentence.

    A relation is emitted only when both endpoints are literal substrings of
    that sentence.  These are review candidates, not student-runtime facts.
    """
    found: list[tuple[str, str, RelationType, str]] = []
    patterns = (
        (CAUSE_RE, "effect", "cause", RelationType.SEBEBIDIR),
        (RESULT_RE, "cause", "effect", RelationType.SONUCUDUR),
        (PURPOSE_RE, "action", "purpose", RelationType.AMACIDIR),
        (ACTOR_RE, "action", "actor", RelationType.AKTORUDUR),
        (AFTER_RE, "second", "first", RelationType.KRONOLOJIK_SONRASIDIR),
    )
    for sentence in SENTENCE_RE.split(text):
        sentence = " ".join(sentence.split())
        for pattern, left_name, right_name, relation in patterns:
            for match in pattern.finditer(sentence):
                left, right = _phrase(match.group(left_name)), _phrase(match.group(right_name))
                if len(left) >= 12 and len(right) >= 12 and left != right:
                    found.append((left, right, relation, sentence[:520]))
    return found


def _event_titles(sentence: str) -> list[str]:
    """Extract only compact, source-verbatim historical event titles.

    This deliberately favours precision over coverage.  A full source
    sentence is a useful evidence atom, but it is not a usable event node for
    a spoken question.  The title remains a literal substring of the quoted
    sentence, so no historical fact is invented during normalization.
    """
    result: list[str] = []
    for match in EVENT_TITLE_RE.finditer(sentence):
        title = " ".join(match.group("event").split())
        if (12 <= len(title) <= 96 and len(title.split()) <= 8
                and "[" not in title and "]" not in title and title not in result):
            result.append(title)
    return result


def _event_year_action(sentence: str, title: str, year: str, *, title_count: int) -> str | None:
    """Return a direct event--year action, otherwise reject the association.

    A sentence may mention a war as background and give the date of a second
    event.  Proximity alone would create a false graph edge.  The extractor
    therefore requires a direct action verb or an immediate parenthesized
    year, and refuses ambiguous multi-title sentences without that evidence.
    """
    title_match = re.search(re.escape(title), sentence)
    year_match = re.search(rf"(?<!\d){re.escape(year)}(?!\d)", sentence)
    if title_match is None or year_match is None:
        return None
    left, right = sorted((title_match.end(), year_match.end()))
    gap_start, gap_end = sorted((title_match.end(), year_match.start()))
    gap = sentence[gap_start:gap_end]
    distance = abs(title_match.start() - year_match.start())
    action_matches = list(TEMPORAL_ACTION_RE.finditer(sentence))
    nearby = [match for match in action_matches
              if min(abs(match.start() - title_match.end()), abs(match.start() - year_match.end())) <= 70]
    if TEMPORAL_CONTEXT_RISK_RE.search(gap):
        return None
    if re.search(rf"\(\s*{re.escape(year)}\s*\)", sentence[title_match.end():title_match.end() + 45]):
        return "dated"
    if distance > 85 or not nearby:
        return None
    # If another named event competes in the same sentence, an unambiguous
    # verb must appear after this title/year pair rather than merely nearby.
    if title_count > 1 and not any(match.start() >= max(title_match.end(), year_match.end()) for match in nearby):
        return None
    action = nearby[0].group("action").casefold()
    return {
        "imzalandı": "signed", "kuruldu": "founded", "toplandı": "convened",
        "başladı": "started", "sona erdi": "ended", "gerçekleşti": "occurred",
    }.get(action)


def build(corpus: dict, *, limit: int = 240) -> KnowledgeGraph:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("multi-history-rag-v1 corpus gerekli")
    nodes: list[HistoricalNode] = []
    edges: list[Edge] = []
    section_nodes: dict[tuple[str, str], str] = {}
    year_nodes: dict[tuple[str, str], str] = {}
    claim_nodes: dict[tuple[str, str, str], str] = {}
    seen_atoms: set[str] = set()
    selected = 0

    def claim_node(*, checksum: str, chunk: dict, source_id: str, section_id: str,
                   label: str, quote: str, relation: RelationType) -> str:
        key = (checksum, str(chunk["id"]), label)
        existing = claim_nodes.get(key)
        if existing is not None:
            return existing
        node_id = _id("claim", checksum, str(chunk["id"]), label)
        claim_nodes[key] = node_id
        nodes.append(HistoricalNode(
            id=node_id, node_type=_node_type(label), label=label, description=quote,
            metadata=NodeMetadata(node_weight=0.92, years=[int(value) for value in YEAR_RE.findall(quote)][:8],
                                  section_id=section_id, unit_title=str(chunk.get("section_title", ""))[:160],
                                  source_ids=[source_id], source_checksum=checksum, page=chunk["page"],
                                  bbox=chunk["bbox"], quote=quote,
                                  extraction_method=f"explicit_{relation.value.casefold()}_cue",
                                  review_status="agent_source_traceable"),
            approved=True,
        ))
        return node_id

    def year_node(*, checksum: str, year: str, source_id: str, chunk: dict, quote: str) -> str:
        year_key = (checksum, year)
        existing = year_nodes.get(year_key)
        if existing is not None:
            return existing
        node_id = _id("period", checksum, year)
        year_nodes[year_key] = node_id
        nodes.append(HistoricalNode(
            id=node_id, node_type=NodeType.DONEM_KRONOLOJI, label=year,
            metadata=NodeMetadata(node_weight=0.8, years=[int(year)], source_ids=[source_id],
                                  source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"], quote=quote,
                                  extraction_method="explicit_year", review_status="agent_source_traceable"),
            approved=True,
        ))
        return node_id

    for book in corpus.get("books", []):
        checksum = str(book.get("source_checksum", ""))
        if len(checksum) < 16:
            continue
        for chunk in book.get("index", {}).get("chunks", []):
            if selected >= limit or not _eligible(chunk):
                continue
            text = _normalize_layout_ocr(str(chunk["text"]))[:520]
            atom_id = _id("atom", checksum, str(chunk["id"]))
            if atom_id in seen_atoms:
                continue
            seen_atoms.add(atom_id)
            section_key = (checksum, str(chunk.get("section_id", "unknown")))
            section_id = section_nodes.get(section_key)
            source_id = f"{checksum}:{chunk['id']}"
            if section_id is None:
                section_id = _id("section", checksum, section_key[1])
                section_nodes[section_key] = section_id
                nodes.append(HistoricalNode(
                    id=section_id, node_type=NodeType.TOPIC,
                    label=str(chunk.get("section_title", section_key[1]))[:180],
                    metadata=NodeMetadata(node_weight=0.65, section_id=section_key[1],
                                          unit_title=str(book.get("source_name", ""))[:160],
                                          source_ids=[source_id], source_checksum=checksum,
                                          page=chunk["page"], bbox=chunk["bbox"], quote=text,
                                          extraction_method="agent_research_section_layout_normalized", review_status="agent_source_traceable"),
                    approved=True,
                ))
            nodes.append(HistoricalNode(
                id=atom_id, node_type=_node_type(text), label=text[:180], description=text,
                metadata=NodeMetadata(node_weight=0.9, years=[int(value) for value in YEAR_RE.findall(text)][:8],
                                      section_id=section_key[1], unit_title=str(book.get("source_name", ""))[:160],
                                      source_ids=[source_id], source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                                      quote=text, extraction_method="agent_traceable_atom_layout_normalized", review_status="agent_source_traceable"),
                approved=True,
            ))
            edges.append(Edge(
                id=_id("edge", atom_id, section_id, "scope"), from_node=atom_id, to_node=section_id,
                relation=RelationType.KAPSAMINDADIR, quote=text, source_ids=[source_id], confidence=0.8,
                approved=True, source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                extraction_method="same_chunk_section_layout_normalized", review_status="agent_source_traceable",
            ))
            for year in dict.fromkeys(YEAR_RE.findall(text)):
                year_id = year_node(checksum=checksum, year=year, source_id=source_id, chunk=chunk, quote=text)
                edges.append(Edge(
                    id=_id("edge", atom_id, year_id, "year"), from_node=atom_id, to_node=year_id,
                    relation=RelationType.DONEMINDE_OLMUSTUR, quote=text, source_ids=[source_id], confidence=0.95,
                    approved=True, source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                    extraction_method="explicit_year_in_source", review_status="agent_source_traceable",
                ))
            # Source sentences with a named event and a year create a compact
            # event--time edge in addition to the broader atom--time edge.
            # The former can form a natural spoken question; the latter stays
            # available for retrieval/context but is filtered by the draft
            # quality gate if it is sentence-shaped.
            for sentence in SENTENCE_RE.split(text):
                sentence = " ".join(sentence.split())
                if not sentence:
                    continue
                years = list(dict.fromkeys(YEAR_RE.findall(sentence)))
                if not years:
                    continue
                titles = _event_titles(sentence)
                for title in titles:
                    event_id = claim_node(checksum=checksum, chunk=chunk, source_id=source_id,
                                          section_id=section_key[1], label=title, quote=sentence,
                                          relation=RelationType.DONEMINDE_OLMUSTUR)
                    for year in years:
                        action = _event_year_action(sentence, title, year, title_count=len(titles))
                        if action is None:
                            continue
                        year_id = year_node(checksum=checksum, year=year, source_id=source_id,
                                            chunk=chunk, quote=sentence)
                        edges.append(Edge(
                            id=_id("edge", event_id, year_id, "named_event_year"),
                            from_node=event_id, to_node=year_id,
                            relation=RelationType.DONEMINDE_OLMUSTUR, quote=sentence,
                            source_ids=[source_id], confidence=0.97, approved=True,
                            source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                            extraction_method=f"source_verbatim_named_event_year_{action}",
                            review_status="agent_source_traceable",
                        ))
            for left, right, relation, quote in _explicit_relations(text):
                left_id = claim_node(checksum=checksum, chunk=chunk, source_id=source_id,
                                     section_id=section_key[1], label=left, quote=quote, relation=relation)
                right_id = claim_node(checksum=checksum, chunk=chunk, source_id=source_id,
                                      section_id=section_key[1], label=right, quote=quote, relation=relation)
                edges.append(Edge(
                    id=_id("edge", left_id, right_id, relation.value), from_node=left_id, to_node=right_id,
                    relation=relation, quote=quote, source_ids=[source_id], confidence=0.76,
                    approved=True, source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                    extraction_method=f"explicit_{relation.value.casefold()}_cue",
                    review_status="agent_source_traceable",
                ))
            selected += 1
    if selected == 0:
        raise ValueError("Araştırma grafiği için uygun, tarih içeren kaynak atomu bulunamadı")
    return KnowledgeGraph(corpus_checksum=str(corpus["corpus_checksum"]), nodes=nodes, edges=edges)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=240)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    graph = build(corpus, limit=args.limit)
    payload = graph.model_dump(mode="json", by_alias=True)
    payload["research_only"] = True
    payload["review_status"] = "agent_source_traceable"
    payload["runtime_enabled"] = False
    payload["notice"] = "Agent research graph: all relationships are source-traceable but require promotion before student runtime."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"atoms": selected_count(graph), "nodes": len(graph.nodes), "edges": len(graph.edges),
                      "research_only": True}, ensure_ascii=False))


def selected_count(graph: KnowledgeGraph) -> int:
    return sum((node.metadata.extraction_method or "").startswith("agent_traceable_atom") for node in graph.nodes)


if __name__ == "__main__":
    main()
