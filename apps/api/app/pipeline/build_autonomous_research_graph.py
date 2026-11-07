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


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _eligible(chunk: dict) -> bool:
    quality = chunk.get("quality", {})
    review = chunk.get("pre_review", {})
    text = str(chunk.get("text", "")).strip()
    return (
        review.get("decision") == "review_for_approval"
        and len(text) >= 40
        and not EXCLUDE_RE.search(text)
        and not quality.get("visual_or_caption_risk")
        and not quality.get("instruction_risk")
        and not quality.get("ocr_fragment_risk")
        and bool(YEAR_RE.search(text))
        and chunk.get("page") is not None
        and chunk.get("bbox") is not None
    )


def _node_type(text: str) -> NodeType:
    if re.search(r"\bantlaşma(sı)?\b", text, re.I):
        return NodeType.ANTLASMA_BELGE
    if EVENT_RE.search(text):
        return NodeType.OLAY_SAVAS
    return NodeType.KAVRAM_ILKE


def build(corpus: dict, *, limit: int = 240) -> KnowledgeGraph:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("multi-history-rag-v1 corpus gerekli")
    nodes: list[HistoricalNode] = []
    edges: list[Edge] = []
    section_nodes: dict[tuple[str, str], str] = {}
    year_nodes: dict[tuple[str, str], str] = {}
    seen_atoms: set[str] = set()
    selected = 0
    for book in corpus.get("books", []):
        checksum = str(book.get("source_checksum", ""))
        if len(checksum) < 16:
            continue
        for chunk in book.get("index", {}).get("chunks", []):
            if selected >= limit or not _eligible(chunk):
                continue
            text = " ".join(str(chunk["text"]).split())[:520]
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
                                          extraction_method="agent_research_section", review_status="agent_source_traceable"),
                    approved=True,
                ))
            nodes.append(HistoricalNode(
                id=atom_id, node_type=_node_type(text), label=text[:180], description=text,
                metadata=NodeMetadata(node_weight=0.9, years=[int(value) for value in YEAR_RE.findall(text)][:8],
                                      section_id=section_key[1], unit_title=str(book.get("source_name", ""))[:160],
                                      source_ids=[source_id], source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                                      quote=text, extraction_method="agent_traceable_atom", review_status="agent_source_traceable"),
                approved=True,
            ))
            edges.append(Edge(
                id=_id("edge", atom_id, section_id, "scope"), from_node=atom_id, to_node=section_id,
                relation=RelationType.KAPSAMINDADIR, quote=text, source_ids=[source_id], confidence=0.8,
                approved=True, source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                extraction_method="same_chunk_section", review_status="agent_source_traceable",
            ))
            for year in dict.fromkeys(YEAR_RE.findall(text)):
                year_key = (checksum, year)
                year_id = year_nodes.get(year_key)
                if year_id is None:
                    year_id = _id("period", checksum, year)
                    year_nodes[year_key] = year_id
                    nodes.append(HistoricalNode(
                        id=year_id, node_type=NodeType.DONEM_KRONOLOJI, label=year,
                        metadata=NodeMetadata(node_weight=0.8, years=[int(year)], source_ids=[source_id],
                                              source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"], quote=text,
                                              extraction_method="explicit_year", review_status="agent_source_traceable"),
                        approved=True,
                    ))
                edges.append(Edge(
                    id=_id("edge", atom_id, year_id, "year"), from_node=atom_id, to_node=year_id,
                    relation=RelationType.DONEMINDE_OLMUSTUR, quote=text, source_ids=[source_id], confidence=0.95,
                    approved=True, source_checksum=checksum, page=chunk["page"], bbox=chunk["bbox"],
                    extraction_method="explicit_year_in_source", review_status="agent_source_traceable",
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
    return sum(node.metadata.extraction_method == "agent_traceable_atom" for node in graph.nodes)


if __name__ == "__main__":
    main()
