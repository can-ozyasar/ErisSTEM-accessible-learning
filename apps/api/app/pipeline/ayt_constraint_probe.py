"""Retrieve review candidates against teacher-authored evidence constraints.

This is a private repair tool for cases where whole-question BM25 retrieval
returns broad context.  A constraint names a fact that must be found in one
passage (for example a person--event relation).  The tool abstains from a
review proposal when any mandatory constraint has no candidate.  It never
reads an answer key and candidates remain unapproved until a teacher checks
the corresponding PDF crop.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..history_rag import terms


def _eligible_chunks(corpus: dict, include_manual_review: bool = False) -> list[tuple[dict, dict]]:
    candidates = []
    for book in corpus.get("books", []):
        for chunk in book["index"].get("chunks", []):
            decision = chunk.get("pre_review", {}).get("decision")
            if decision != "review_for_approval" and not (include_manual_review and decision == "manual_review"):
                continue
            if chunk.get("quality", {}).get("warnings"):
                continue
            candidates.append((book, chunk))
    return candidates


def _term_matches(required: str, observed: str) -> bool:
    """Allow transparent Turkish inflection matching without a hidden lemmatizer."""
    return required == observed or (len(required) >= 4 and observed.startswith(required))


def _covered(required: set[str], observed: set[str]) -> set[str]:
    return {term for term in required if any(_term_matches(term, token) for token in observed)}


def _matches(chunk: dict, clause: dict) -> bool:
    observed = set(terms(chunk["text"]))
    all_of = set(terms(" ".join(clause.get("all_of", []))))
    any_of = set(terms(" ".join(clause.get("any_of", []))))
    return _covered(all_of, observed) == all_of and (not any_of or bool(_covered(any_of, observed)))


def _rank_matches(matches: list[tuple[dict, dict]], clause: dict, query_terms: list[str],
                  limit: int) -> list[tuple[dict, dict]]:
    """Rank only passages that satisfy the full mandatory relation.

    The clause gate is intentionally applied before scoring: a passage that
    names only one side of a person--event relation must not outrank a direct
    relation just because it repeats more broad question words.
    """
    required = set(terms(" ".join([*clause.get("all_of", []), *clause.get("any_of", [])])))
    query = set(terms(" ".join(query_terms)))
    scored = []
    for book, chunk in matches:
        observed = set(terms(chunk["text"]))
        required_hits = len(_covered(required, observed))
        query_hits = len(_covered(query, observed))
        scored.append((required_hits * 10 + query_hits, book, chunk))
    scored.sort(key=lambda row: (-row[0], row[2]["page"], row[2]["id"]))
    selected = []
    seen_pages = set()
    for score, book, chunk in scored:
        # PDF exports often split a single paragraph into adjacent blocks.
        # One page per clause avoids spending the whole review budget on those
        # near duplicates and acts as a simple, inspectable MMR-style guard.
        page_key = (book["source_checksum"], chunk["page"])
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        selected.append((book, {**chunk, "score": round(score, 3)}))
        if len(selected) == limit:
            break
    return selected


def _suggestion(book: dict, chunk: dict, clause: dict) -> dict:
    return {
        "chunk_id": chunk["id"],
        "grade": book["grade"],
        "source_name": book["source_name"],
        "source_checksum": book["source_checksum"],
        "section_id": chunk["section_id"],
        "section_title": chunk["section_title"],
        "page": chunk["page"],
        "bbox": chunk["bbox"],
        "score": chunk["score"],
        "text": chunk["text"],
        "pre_review": chunk.get("pre_review", {}),
        "review_status": "candidate",
        "constraint_clause_id": clause["id"],
    }


def build(question_candidates: dict, corpus: dict, constraints: dict,
          per_clause: int = 2, include_manual_review: bool = False) -> dict:
    """Return a checksum-bound, incomplete-by-default review proposal manifest."""
    if question_candidates.get("schema") != "ayt-tarih2-candidates-v1":
        raise ValueError("Beklenen AYT soru aday şeması bulunamadı")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Beklenen çok kitaplı corpus şeması bulunamadı")
    if constraints.get("schema") != "ayt-evidence-constraints-v1":
        raise ValueError("Beklenen kanıt kısıt şeması bulunamadı")
    if constraints.get("question_source_checksum") != question_candidates.get("source_checksum"):
        raise ValueError("Kısıt ve soru checksum'ları eşleşmiyor")
    if constraints.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Kısıt ve corpus checksum'ları eşleşmiyor")
    if per_clause < 1:
        raise ValueError("Her kısıt için en az bir aday gerekli")

    question_by_id = {item["candidate_id"]: item for item in question_candidates.get("candidates", [])}
    pool = _eligible_chunks(corpus, include_manual_review)
    rows = []
    for case in constraints.get("cases", []):
        candidate_id = case.get("candidate_id")
        question = question_by_id.get(candidate_id)
        if question is None or question.get("year_status") != "bound":
            raise ValueError("Kısıt yalnız kapsam içi, yıl-bağlı soru için tanımlanabilir")
        clauses = case.get("required_clauses", [])
        if not clauses or any(not clause.get("id") for clause in clauses):
            raise ValueError("Her kısıt vakasında kimlikli zorunlu madde gerekli")
        suggestions, missing = [], []
        for clause in clauses:
            if not clause.get("all_of") and not clause.get("any_of"):
                raise ValueError("Zorunlu madde en az bir arama terimi içermeli")
            matches = [(book, chunk) for book, chunk in pool if _matches(chunk, clause)]
            ranked = _rank_matches(matches, clause, case.get("query_terms", []), per_clause)
            if not ranked:
                missing.append(clause["id"])
                continue
            suggestions.extend(_suggestion(book, chunk, clause) for book, chunk in ranked)

        # A single passage can establish more than one constraint.  Keep its
        # earliest clause position, then its highest score, deterministically.
        deduped = {}
        for rank, suggestion in enumerate(suggestions):
            key = (suggestion["source_checksum"], suggestion["chunk_id"])
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = (suggestion["score"], rank, suggestion)
                continue
            existing_suggestion = existing[2]
            clause_ids = existing_suggestion.setdefault(
                "constraint_clause_ids", [existing_suggestion["constraint_clause_id"]]
            )
            if suggestion["constraint_clause_id"] not in clause_ids:
                clause_ids.append(suggestion["constraint_clause_id"])
            if suggestion["score"] > existing[0]:
                suggestion["constraint_clause_ids"] = clause_ids
                deduped[key] = (suggestion["score"], rank, suggestion)
        ordered = [entry[2] for entry in sorted(
            deduped.values(), key=lambda entry: (-entry[0], entry[1], entry[2]["page"], entry[2]["chunk_id"])
        )]
        rows.append({
            "candidate_id": candidate_id,
            "exam_year": question["exam_year"],
            "status": "teacher_review_required" if not missing else "insufficient_evidence",
            "constraint_gate": {"required_clause_ids": [clause["id"] for clause in clauses],
                                "missing_clause_ids": missing, "complete": not missing},
            "suggestions": ordered,
        })

    return {
        "schema": "ayt-evidence-proposals-v1",
        "question_source_checksum": question_candidates["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "proposal_count": len(rows),
        "proposals": rows,
        "notice": (
            "Private constraint-based teacher-review output. It reads no answer key; complete "
            "lexical coverage is not an evidence approval. PDF-crop review and an explicit teacher "
            "source role are still mandatory before student RAG, evaluation or QLoRA use."
            + (" Manual-review source quotations were included for discovery only." if include_manual_review else "")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-clause", type=int, default=2)
    parser.add_argument("--include-manual-review", action="store_true",
                        help="Yalnız PDF kırpımı için belirsiz kaynak alıntısı adaylarını da keşfe ekler")
    args = parser.parse_args()
    result = build(
        json.loads(args.questions.read_text(encoding="utf-8")),
        json.loads(args.corpus.read_text(encoding="utf-8")),
        json.loads(args.constraints.read_text(encoding="utf-8")),
        args.per_clause, args.include_manual_review,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
