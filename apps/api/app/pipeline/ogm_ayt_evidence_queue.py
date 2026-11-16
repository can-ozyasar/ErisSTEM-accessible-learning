"""Build a private MEB-evidence review queue for transcribed OGM AYT items."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from ..history_rag import PreparedBM25, terms

SCHEMA = "ogm-ayt-evidence-review-queue-v3"
TRANSCRIPTION_SCHEMAS = {"ogm-ayt-private-transcription-v1", "ayt-target-discovery-pool-v1"}
# These words occur in a question form far more often than they identify a
# historical claim.  They are excluded only from the *literal claim coverage*
# check below.  BM25 continues to see the complete question and choices.
QUESTION_FORM_TERMS = {
    "aşağıdakilerden",
    "aşağıdaki",
    "hangisi",
    "hangilerinden",
    "hangileri",
    "hangisidir",
    "verilen",
    "verilmiştir",
    "göre",
    "olarak",
    "ilgili",
    "değildir",
    "olamaz",
    "ulaşılabilir",
    "söylenebilir",
    "çıkarılabilir",
    "doğru",
    "yanlış",
    "bilgi",
    "ifadeler",
    "ifade",
    "yargı",
    "yargılardan",
    "özellik",
    "özelliklerden",
    "olduğu",
    "olması",
    "amaçlanmıştır",
}
GENERIC_CLAIM_TERMS = {
    "türkiye",
    "dünya",
    "dönem",
    "devlet",
    "savaş",
    "milli",
    "mücadele",
    "tarih",
    "tarihi",
    "gelişme",
    "olay",
    "bilgi",
    "toplum",
    "ülke",
}
CAPITALISED_TOKEN = re.compile(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+|MÖ|MS|\d{3,4}")
TOPIC_SECTION_HINTS = {
    "I. Dünya Savaşı Sürecinde Osmanlı Devleti": (
        "I. DÜNYA SAVAŞI SÜRECİNDE OSMANLI DEVLETİ",
        # The same AYT-relevant material appears under this heading in the
        # grade-11 edition. Keep this source-specific alias explicit instead
        # of widening the topic to every generic Ottoman chapter.
        "1908-1918 YILLARI ARASINDA OSMANLI DEVLETİ’NDE MEYDANA GELEN SİYASİ VE ASKERÎ GELİŞMELER",
        "1908-1918 YILLARI ARASINDA OSMANLI DEVLETİNDE MEYDANA GELEN SİYASİ VE ASKERÎ GELİŞMELER",
    ),
    "Millî Mücadele’ye Hazırlık Dönemi": (
        "MİLLÎ MÜCADELE’YE HAZIRLIK DÖNEMİ",
        "MİLLİ MÜCADELE’YE HAZIRLIK DÖNEMİ",
        "MİLLÎ MÜCADELE’YE HAZIRLIK DÖNEMİ-I",
        "MİLLÎ MÜCADELE’YE HAZIRLIK DÖNEMİ-II",
    ),
    "Batı Cephesi ve Bu Cephede Öne Çıkan Şahsiyetler": (
        "BATI CEPHESİ VE BU CEPHEDE ÖNE ÇIKAN ŞAHSİYETLER",
        "DOĞU, GÜNEY VE BATI CEPHELERİ",
    ),
    "Doğu ve Güney Cepheleri ile Bu Cephelerde Öne Çıkan Şahsiyetler": (
        "DOĞU VE GÜNEY CEPHELERİ İLE BU CEPHELERDE ÖNE ÇIKAN ŞAHSİYETLER",
        "DOĞU, GÜNEY VE BATI CEPHELERİ",
    ),
    "Atatürk İlkeleri": (
        "ATATÜRK İLKELERİ",
        "ATATÜRK İLKELERİ-SİYASİ VE HUKUK ALANINDAKİ GELİŞMELER",
    ),
    "Siyasi Alandaki Gelişmeler": (
        "SİYASİ ALANDAKİ GELİŞMELER",
        "ATATÜRK İLKELERİ-SİYASİ VE HUKUK ALANINDAKİ GELİŞMELER",
        "ATATÜRK DÖNEMİ TÜRK DIŞ POLİTİKASI",
    ),
    "Millî Mücadele": ("MİLLÎ MÜCADELE", "BÜYÜK MİLLET MECLİSİ", "SEVR", "CEPHELER", "LOZAN"),
    "Atatürkçülük ve Türk İnkılabı": (
        "ATATÜRK İLKELERİ",
        "İNKILAP",
        "ATATÜRK DÖNEMİ",
        "ATATÜRKÇÜ DÜŞÜNCE",
    ),
    "İki Savaş Arasındaki Dönemde Türkiye ve Dünya": ("İKİ DÜNYA SAVAŞI ARASINDAKİ",),
    "II. Dünya Savaşı Sürecinde Türkiye ve Dünya": ("II. DÜNYA SAVAŞI",),
    "II. Dünya Savaşı Sonrasında Türkiye ve Dünya": (
        "II. DÜNYA SAVAŞI SONRASI",
        "1950’LERDE TÜRKİYE",
    ),
    "21. Yüzyılın Eşiğinde Türkiye ve Dünya": ("1960 SONRASI", "1990 SONRASI"),
}
SEARCH_TERM_ALIASES = {
    # Historical place names and treaty names often vary across the PDF and
    # exam printings. These aliases only widen discovery; they never verify a
    # relation or promote a source to approved evidence.
    "montrö": ("montreux",),
    "montreux": ("montrö",),
    "öncülük": ("teklif", "başvuru", "girişim"),
    "antlaşma": ("sözleşme", "pakt"),
}


def _normalise(value: str) -> str:
    return " ".join(value.replace("İ", "I").replace("ı", "i").upper().split())


def _topic_pool(pool: list[tuple[dict, dict]], topic: str) -> list[tuple[dict, dict]]:
    hints = TOPIC_SECTION_HINTS.get(topic)
    if not hints:
        return []
    normalized_hints = tuple(_normalise(hint) for hint in hints)
    return [
        (book, chunk)
        for book, chunk in pool
        if any(hint in _normalise(chunk.get("section_title", "")) for hint in normalized_hints)
    ]


def _eligible(corpus: dict, *, include_atoms: bool = False) -> list[tuple[dict, dict]]:
    """Return clean text evidence candidates, including low-confidence review rows.

    This function builds a *private review queue*, not an approved/runtime
    index. Restricting discovery to ``review_for_approval`` silently hid short
    but clean textbook fragments whose pre-review classifier had asked for
    context review. Such fragments may be retrieved for a teacher to inspect;
    their pre-review status is preserved in each card and they never become
    approved evidence automatically.
    """
    rows = []
    for book in corpus.get("books", []):
        if book.get("grade") not in {10, 11, 12}:
            continue
        records = [(chunk, "context_chunk") for chunk in book["index"].get("chunks", [])]
        if include_atoms:
            records.extend((atom, "evidence_atom")
                           for atom in book["index"].get("evidence_atoms", []))
        for chunk, index_layer in records:
            decision = chunk.get("pre_review", {}).get("decision")
            quality = chunk.get("quality", {})
            if decision not in {"review_for_approval", "manual_review"}:
                continue
            if quality.get("text_quality") != "clean" or quality.get("warnings"):
                continue
            if any(quality.get(flag) for flag in (
                "visual_or_caption_risk", "instruction_risk", "ocr_fragment_risk"
            )):
                continue
            if not str(chunk.get("text", "")).strip():
                continue
            rows.append((book, {**chunk, "_index_layer": index_layer}))
    return rows


def _query(row: dict) -> str:
    return " ".join(
        [row["question"]["stem"], *(choice["text"] for choice in row["question"]["choices"])]
    )


def _claim_queries(row: dict) -> list[tuple[str, str]]:
    """Search the stem and every option as separate evidence needs.

    Option-wise retrieval supports elimination questions without guessing
    which option is correct: every choice receives an equal query channel.
    """
    stem = row["question"]["stem"]
    queries = [("whole_question", _query(row)), ("stem", stem)]
    for index, choice in enumerate(row["question"].get("choices", [])):
        label = str(choice.get("label") or chr(ord("A") + index))
        text = str(choice.get("text", "")).strip()
        if text:
            queries.append((f"choice:{label}", text))
            # Preserve the relation asked by the stem while searching each
            # option. Searching an option name alone loses predicates such as
            # who proposed, signed, caused, or abolished the event.
            queries.append((f"claim:{label}", f"{stem} {text}"))
    seen: set[str] = set()
    unique = []
    for label, query in queries:
        expanded_terms = set(terms(query))
        aliases = sorted({
            alias
            for term in expanded_terms
            for root, variants in SEARCH_TERM_ALIASES.items()
            if term == root or term.startswith(root)
            for alias in variants
        })
        if aliases:
            query = f"{query} {' '.join(aliases)}"
        key = " ".join(terms(query))
        if key and key not in seen:
            unique.append((label, query))
            seen.add(key)
    return unique


def _claim_terms(row: dict) -> set[str]:
    """Return inspectable question-root terms without using an answer key.

    Choices are useful for lexical candidate discovery, but requiring a choice
    to match would turn an unknown correct option into a hidden ranking label.
    The hard gate therefore uses only the stem.  It deliberately stays lexical:
    it is a fail-closed review filter, never a claim verifier.
    """
    return {term for term in terms(row["question"]["stem"]) if term not in QUESTION_FORM_TERMS}


def _anchor_terms(row: dict) -> set[str]:
    """Extract non-generic named/date anchors from the question root only."""
    raw = CAPITALISED_TOKEN.findall(row["question"]["stem"])
    return {
        term
        for token in raw
        for term in terms(token)
        if term not in QUESTION_FORM_TERMS | GENERIC_CLAIM_TERMS
    }


def _term_matches(claim: str, observed: str) -> bool:
    """Allow a conservative Turkish suffix/root match for long tokens."""
    return claim == observed or (
        len(claim) >= 5 and len(observed) >= 5 and claim[:5] == observed[:5]
    )


def _claim_coverage(row: dict, text: str) -> dict:
    claim_terms = _claim_terms(row)
    observed_terms = set(terms(text))
    covered = sorted(
        claim
        for claim in claim_terms
        if any(_term_matches(claim, observed) for observed in observed_terms)
    )
    distinctive = {
        term for term in claim_terms if len(term) >= 6 or any(char.isdigit() for char in term)
    }
    covered_distinctive = sorted(term for term in distinctive if term in covered)
    anchors = _anchor_terms(row)
    covered_anchors = sorted(term for term in anchors if term in covered)
    required = 1 if len(claim_terms) <= 3 else 2
    # A lexical overlap is a review signal. It does not prove a historical
    # relation or authorize a passage, especially with Turkish OCR noise.
    direct_gate = (
        len(covered) >= required
        and len(covered) / max(1, len(claim_terms)) >= 0.4
        and (not distinctive or bool(covered_distinctive))
        and (not anchors or bool(covered_anchors))
    )
    return {
        "claim_term_count": len(claim_terms),
        "covered_claim_term_count": len(covered),
        "claim_coverage": round(len(covered) / max(1, len(claim_terms)), 3),
        "distinctive_claim_term_count": len(distinctive),
        "covered_distinctive_term_count": len(covered_distinctive),
        "anchor_term_count": len(anchors),
        "covered_anchor_term_count": len(covered_anchors),
        "lexical_overlap_hint": direct_gate,
    }


def _global_index(pool: list[tuple[dict, dict]]) -> PreparedBM25:
    """One indexed corpus for all eligible books, preserving source IDs."""
    items = [
        {
            **chunk,
            "id": f"{book['source_checksum']}:{chunk['id']}",
            "_chunk_id": chunk["id"],
            "_book": book,
            "_index_layer": chunk.get("_index_layer", "context_chunk"),
        }
        for book, chunk in pool
    ]
    return PreparedBM25(items)


def _rank_claimwise(index: PreparedBM25, queries: list[tuple[str, str]], limit: int,
                    scoped_ids: set[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Fuse stem/option rankings with RRF, preserving why each card surfaced."""
    by_id: dict[str, dict] = {}
    ranks: dict[str, list[dict]] = {}
    fused: dict[str, float] = {}
    for label, query in queries:
        for rank, item in enumerate(index.rank(query, limit=len(index.chunks)), start=1):
            key = item["id"]
            by_id[key] = item
            ranks.setdefault(key, []).append({"channel": label, "rank": rank})
            fused[key] = fused.get(key, 0.0) + 1.0 / (60 + rank)

    def ordered(is_scoped: bool) -> list[dict]:
        selected = []
        for key, item in by_id.items():
            scope_key = (item["_book"]["source_checksum"], item["_chunk_id"])
            if (scope_key in scoped_ids) != is_scoped:
                continue
            selected.append({**item, "_rrf_score": fused[key], "_channel_ranks": ranks[key]})
        selected.sort(key=lambda item: (-item["_rrf_score"], item["page"], item["id"]))
        # Keep the full candidate pool here. A later selector may reserve a
        # strong hit from a single option channel that additive RRF would
        # otherwise push below ``limit``. The ordinary RRF path still applies
        # its original top-k policy in _reserve_cross_section_candidates.
        return selected

    local = ordered(True)
    expanded = ordered(False)
    return local, expanded


def _reserve_cross_section_candidates(local: list[dict], expanded: list[dict], limit: int) -> list[dict]:
    """Keep cross-section evidence discoverable even when the topic pool is full.

    Topic labels guide discovery but can hide prerequisite or contrast evidence
    in another chapter. Reserve roughly one third of the review slate for those
    candidates, then backfill unused slots from either pool. This is a review
    queue policy; it does not approve evidence or alter runtime retrieval.
    """
    if limit < 1:
        return []
    if not expanded:
        return local[:limit]
    expanded_quota = min(len(expanded), max(1, limit // 3))
    local_quota = min(len(local), limit - expanded_quota)
    selected = [*local[:local_quota], *expanded[:expanded_quota]]
    if len(selected) < limit:
        selected.extend(local[local_quota:local_quota + limit - len(selected)])
    if len(selected) < limit:
        selected.extend(expanded[expanded_quota:expanded_quota + limit - len(selected)])
    return selected


def _reserve_option_channel_candidates(
    local: list[dict], expanded: list[dict], queries: list[tuple[str, str]],
    limit: int, *, channel_rank_limit: int = 5,
) -> list[dict]:
    """Protect strong option-specific hits from being diluted by additive RRF.

    This is a review-queue experiment, not an evidence decision. For each
    answer option, reserve its best in-topic and cross-section candidate when
    that candidate ranks within ``channel_rank_limit`` for the option-only
    query. Fill the remaining slate with the regular cross-section RRF policy.
    No option is treated as correct; all options receive the same treatment.
    """
    if limit < 1:
        return []
    option_labels = [label for label, _ in queries if label.startswith("choice:")]
    selected: list[dict] = []
    seen: set[str] = set()

    def best_channel_hit(pool: list[dict], label: str) -> dict | None:
        hits = []
        for item in pool:
            channel_ranks = {
                row.get("channel"): row.get("rank")
                for row in item.get("_channel_ranks", [])
            }
            rank = channel_ranks.get(label)
            if isinstance(rank, int) and rank <= channel_rank_limit:
                hits.append((rank, -item.get("_rrf_score", 0.0), item))
        return min(hits, default=(None, None, None), key=lambda hit: (hit[0], hit[1]))[2]

    # First reserve one best hit for every option, comparing topic-local and
    # expanded candidates together. This avoids fixed-pool ordering consuming
    # a small slate before later options are considered. Then reserve a second
    # hit from the other pool per option where the slate has room.
    option_hits: dict[str, dict[str, dict | None]] = {}
    for label in option_labels:
        option_hits[label] = {
            "local": best_channel_hit(local, label),
            "expanded": best_channel_hit(expanded, label),
        }

    def hit_order(label: str, item: dict, pool_name: str) -> tuple[int, int, float, str]:
        rank = min(
            row["rank"] for row in item.get("_channel_ranks", [])
            if row.get("channel") == label
        )
        return (rank, 0 if pool_name == "local" else 1, -item.get("_rrf_score", 0.0), item["id"])

    for label in option_labels:
        candidates = [
            (pool_name, item)
            for pool_name, item in option_hits[label].items()
            if item is not None
        ]
        if not candidates:
            continue
        pool_name, item = min(candidates, key=lambda pair: hit_order(label, pair[1], pair[0]))
        if item["id"] not in seen:
            selected.append({**item, "_selection_reason": f"reserved_{label}"})
            seen.add(item["id"])
        option_hits[label][pool_name] = None
        if len(selected) >= limit:
            return selected[:limit]

    for label in option_labels:
        candidates = [
            (pool_name, item)
            for pool_name, item in option_hits[label].items()
            if item is not None and item["id"] not in seen
        ]
        if not candidates:
            continue
        pool_name, item = min(candidates, key=lambda pair: hit_order(label, pair[1], pair[0]))
        selected.append({**item, "_selection_reason": f"reserved_{label}_{pool_name}"})
        seen.add(item["id"])
        if len(selected) >= limit:
            return selected[:limit]

    remaining = limit - len(selected)
    if remaining:
        local_tail = [item for item in local if item["id"] not in seen]
        expanded_tail = [item for item in expanded if item["id"] not in seen]
        selected.extend(_reserve_cross_section_candidates(local_tail, expanded_tail, remaining))
    return selected[:limit]


def build(transcriptions: dict, corpus: dict, limit: int = 6,
          strategy: str = "whole_question") -> dict:
    if transcriptions.get("schema") not in TRANSCRIPTION_SCHEMAS:
        raise ValueError("Private OGM transkripsiyon şeması gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("MEB corpus şeması geçersiz")
    if limit < 1:
        raise ValueError("Kanıt aday sınırı pozitif olmalı")
    if strategy not in {
        "whole_question", "claimwise_rrf", "claimwise_option_reserve",
        "claimwise_atom_context_option_reserve",
    }:
        raise ValueError("Bilinmeyen retrieval stratejisi")
    include_atoms = strategy == "claimwise_atom_context_option_reserve"
    pool = _eligible(corpus, include_atoms=include_atoms)
    index = _global_index(pool)
    proposals = []
    for row in transcriptions.get("rows", []):
        started = time.perf_counter()
        if row.get("transcription_status") != "private_teacher_review_required":
            proposals.append(
                {
                    "candidate_id": row["candidate_id"],
                    "status": "blocked_transcription_quality",
                    "suggestions": [],
                }
            )
            continue
        suggestions = []
        scoped_pool = _topic_pool(pool, row["topic"])
        scoped_ids = {(book["source_checksum"], chunk["id"]) for book, chunk in scoped_pool}
        if strategy in {
            "claimwise_rrf", "claimwise_option_reserve",
            "claimwise_atom_context_option_reserve",
        }:
            local_ranked, expanded_ranked = _rank_claimwise(
                index, _claim_queries(row), limit, scoped_ids
            )
            if strategy in {
                "claimwise_option_reserve", "claimwise_atom_context_option_reserve"
            }:
                selected_ranked = _reserve_option_channel_candidates(
                    local_ranked, expanded_ranked, _claim_queries(row), limit
                )
            else:
                selected_ranked = _reserve_cross_section_candidates(
                    local_ranked, expanded_ranked, limit
                )
        else:
            # Rank once across the corpus. Single-document BM25 has no useful
            # collection IDF and makes scores between books incomparable.
            ranked = index.rank(_query(row), limit=len(pool))
            local_ranked = [
                item
                for item in ranked
                if (item["_book"]["source_checksum"], item["_chunk_id"]) in scoped_ids
            ][:limit]
            expanded_ranked = [
                item
                for item in ranked
                if (item["_book"]["source_checksum"], item["_chunk_id"]) not in scoped_ids
            ]
            selected_ranked = _reserve_cross_section_candidates(local_ranked, expanded_ranked, limit)
        for item in selected_ranked:
            book = item["_book"]
            in_topic = (book["source_checksum"], item["_chunk_id"]) in scoped_ids
            coverage = _claim_coverage(row, item["text"])
            suggestions.append(
                {
                    "chunk_id": item["_chunk_id"],
                    "source_name": book["source_name"],
                    "source_checksum": book["source_checksum"],
                    "grade": book["grade"],
                    # Older private indexes may not carry a stable section id;
                    # keep the candidate usable for teacher review while
                    # preserving the human-readable section title.
                    "section_id": item.get("section_id") or item.get("section_title", "belirsiz"),
                    "page": item["page"],
                    "bbox": item["bbox"],
                    "section_title": item["section_title"],
                    "pre_review_decision": item.get("pre_review", {}).get("decision"),
                    "pre_review_confidence": item.get("pre_review", {}).get("confidence"),
                    "quality_warnings": item.get("quality", {}).get("warnings", []),
                    "score": round(item["_rrf_score"], 6) if "_rrf_score" in item else item["score"],
                    "retrieval_channels": item.get("_channel_ranks", []),
                    "selection_reason": item.get("_selection_reason", "rrf_rank"),
                    "claim_coverage": coverage,
                    "index_layer": item.get("_index_layer", "context_chunk"),
                    "heading": item.get("heading"),
                    "extraction_method": item.get("extraction_method"),
                    "in_topic_section": in_topic,
                    "text": item["text"],
                    "review_status": "candidate_unverified",
                }
            )
        # Calculate diagnostic coverage only for the selected review slate;
        # it cannot promote a passage over the corpus-wide BM25 ordering.
        proposals.append(
            {
                "candidate_id": row["candidate_id"],
                "topic": row["topic"],
                "status": "teacher_agent_source_review_required"
                if suggestions
                else "insufficient_evidence",
                "section_scope_applied": bool(scoped_pool),
                "expanded_to_other_sections": any(not item["in_topic_section"] for item in suggestions),
                "retrieval_ms": round((time.perf_counter() - started) * 1000, 2),
                "suggestions": suggestions,
            }
        )
    return {
        "schema": SCHEMA,
        "source_checksum": transcriptions["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "retrieval_strategy": strategy,
        "proposals": proposals,
        "notice": (
            "Private review queue. Lexical coverage is diagnostic only. Suggestions require "
            "PDF-crop and relation review; no answer or worked explanation was read."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--strategy", choices=(
        "whole_question", "claimwise_rrf", "claimwise_option_reserve",
        "claimwise_atom_context_option_reserve",
    ), default="whole_question")
    args = parser.parse_args()
    result = build(
        json.loads(args.transcriptions.read_text(encoding="utf-8")),
        json.loads(args.corpus.read_text(encoding="utf-8")),
        args.limit,
        strategy=args.strategy,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
