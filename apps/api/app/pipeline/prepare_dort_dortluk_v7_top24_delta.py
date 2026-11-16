"""Prepare only previously unseen top-24 evidence crops for unresolved items."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pymupdf

DELTA_PACK_SCHEMA = "dort-dortluk-v7-top24-delta-review-pack-v1"
COMBINED_PACK_SCHEMA = "dort-dortluk-v7-top24-combined-review-pack-v1"


def crop_signature(card: dict[str, Any]) -> tuple[str, int, tuple[float, ...]]:
    bbox = tuple(round(float(value), 2) for value in card["bbox"])
    return card["source_checksum"], int(card["page"]), bbox


def select_unseen_cards(v6: dict[str, Any], v7: dict[str, Any],
                        adjudications: dict[str, Any], excluded_ids: set[str],
                        include_previous: bool = False) -> dict[str, list[dict[str, Any]]]:
    resolved_ids = {row["candidate_id"] for row in adjudications.get("adjudications", [])}
    old_by_question = {
        row["candidate_id"]: {crop_signature(card) for card in row.get("suggestions", [])}
        for row in v6.get("proposals", [])
    }
    selected: dict[str, list[dict[str, Any]]] = {}
    for row in v7.get("proposals", []):
        candidate_id = row["candidate_id"]
        if candidate_id in resolved_ids or candidate_id in excluded_ids:
            continue
        old_signatures = old_by_question.get(candidate_id, set())
        unseen = [
            {**card, "_expanded_rank": rank}
            for rank, card in enumerate(row.get("suggestions", []), start=1)
            if include_previous or crop_signature(card) not in old_signatures
        ]
        # Atom and context indexes can point to the same physical PDF crop.
        # Review that crop once and retain the first (highest-ranked) view.
        unique_unseen: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, int, tuple[float, ...]]] = set()
        for card in unseen:
            signature = crop_signature(card)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_unseen.append(card)
        unseen = unique_unseen
        if unseen:
            selected[candidate_id] = unseen
    return selected


def _source_paths(corpus: dict[str, Any], root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for book in corpus.get("books", []):
        name = book["source_name"]
        candidates = (root / "data" / "meb" / name,
                      root / "data" / "private" / "ogm-supplementary-v1" / name,
                      root / "data" / "private" / "yks-ayt-source-v1" / name)
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            raise FileNotFoundError(f"Private corpus PDF bulunamadı: {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != book["source_checksum"]:
            raise ValueError(f"PDF checksum corpus kaydıyla eşleşmiyor: {name}")
        paths[book["source_checksum"]] = path
    return paths


def _question_page_and_number(candidate_id: str) -> tuple[int, int]:
    match = re.search(r":p(\d+):q(\d+)$", candidate_id)
    if not match:
        raise ValueError(f"Soru kaynağı sayfa/soru kimliği çözümlenemedi: {candidate_id}")
    return int(match.group(1)), int(match.group(2))


def _balanced_partition(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda item: item["candidate_id"]):
        by_topic[row.get("topic", "belirsiz")].append(row)
    agent_a: list[dict[str, Any]] = []
    agent_b: list[dict[str, Any]] = []
    for topic_rows in by_topic.values():
        for index, row in enumerate(topic_rows):
            (agent_a if index % 2 == 0 else agent_b).append(row)
    return agent_a, agent_b


def build(v6: dict[str, Any], v7: dict[str, Any], transcriptions: dict[str, Any],
          corpus: dict[str, Any], adjudications: dict[str, Any], excluded_ids: set[str],
          output: Path, root: Path, include_previous: bool = False,
          queue_label: str = "v7-top24",
          question_pdf_path: Path | None = None) -> dict[str, Any]:
    if v6.get("schema") != v7.get("schema") or v6.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("V6/V7 kuyruğu ve corpus sürümü aynı olmalı")
    if v7.get("retrieval_strategy") not in {
        "claimwise_rrf", "claimwise_option_reserve",
        "claimwise_atom_context_option_reserve",
    }:
        raise ValueError("Desteklenen claimwise retrieval kuyruğu gerekli")
    if adjudications.get("answer_key_accessed") is not False:
        raise ValueError("Cevap anahtarından bağımsız adjudication gerekli")
    if question_pdf_path is not None:
        question_pdf_checksum = hashlib.sha256(question_pdf_path.read_bytes()).hexdigest()
        if question_pdf_checksum != transcriptions.get("source_checksum"):
            raise ValueError("Soru PDF checksum'ı temiz transkripsiyon kaynağıyla eşleşmiyor")
    source_paths = _source_paths(corpus, root)
    question_rows = {row["candidate_id"]: row for row in transcriptions.get("rows", [])}
    selected = select_unseen_cards(
        v6, v7, adjudications, excluded_ids, include_previous=include_previous)
    old_signatures_by_question = {
        row["candidate_id"]: {crop_signature(card) for card in row.get("suggestions", [])}
        for row in v6.get("proposals", [])
    }
    pack_schema = (f"dort-dortluk-{queue_label}-combined-review-pack-v1"
                   if include_previous else
                   f"dort-dortluk-{queue_label}-delta-review-pack-v1")
    previous_limit = max(
        (len(row.get("suggestions", [])) for row in v6.get("proposals", [])),
        default=0,
    )
    expanded_limit = max(
        (len(row.get("suggestions", [])) for row in v7.get("proposals", [])),
        default=0,
    )
    review_scope = f"all_top{expanded_limit}" if include_previous else "new_delta_only"
    reviewed_crop_count = sum(len(cards) for cards in selected.values())
    new_crop_count = sum(
        sum(crop_signature(card) not in old_signatures_by_question.get(candidate_id, set())
            for card in cards)
        for candidate_id, cards in selected.items()
    )
    rows: list[dict[str, Any]] = []
    with ExitStack() as stack:
        pdfs = {checksum: stack.enter_context(pymupdf.open(path))
                for checksum, path in source_paths.items()}
        question_pdf = (stack.enter_context(pymupdf.open(question_pdf_path))
                        if question_pdf_path is not None else None)
        for candidate_id, cards in sorted(selected.items()):
            question_row = question_rows.get(candidate_id)
            if not question_row:
                raise ValueError(f"Soru transkripsiyonu bulunamadı: {candidate_id}")
            card_rows = []
            for card in cards:
                checksum = card["source_checksum"]
                pdf = pdfs[checksum]
                page_number = int(card["page"])
                if page_number < 1 or page_number > pdf.page_count:
                    raise ValueError(f"PDF sayfası sınır dışında: {candidate_id} {page_number}")
                page = pdf[page_number - 1]
                safe_id = candidate_id.replace(":", "-")
                crop_name = (f"{safe_id}-rank{card['_expanded_rank']:02d}-"
                             f"{card['chunk_id']}.png")
                card_rows.append({
                    "rank_in_expanded_queue": card["_expanded_rank"],
                    "chunk_id": card["chunk_id"],
                    "source_name": card["source_name"],
                    "source_checksum": checksum,
                    "source_page": page_number,
                    "bbox": card["bbox"],
                    "section_title": card["section_title"],
                    "index_layer": card.get("index_layer", "chunk"),
                    "heading": card.get("heading"),
                    "extraction_method": card.get("extraction_method"),
                    "indexed_excerpt": card.get("text", ""),
                    "claim_coverage": card.get("claim_coverage", []),
                    "quality_warnings": card.get("quality_warnings", []),
                    "crop_filename": crop_name,
                    "crop_visual_checked": False,
                })
            question = question_row.get("question", {})
            question_source_page, question_number = _question_page_and_number(candidate_id)
            if question_pdf is not None and not (1 <= question_source_page <= question_pdf.page_count):
                raise ValueError(f"Soru PDF sayfası sınır dışında: {candidate_id}")
            rows.append({
                "candidate_id": candidate_id,
                "topic": question_row.get("topic", "belirsiz"),
                "question": question,
                "question_source_checksum": transcriptions.get("source_checksum"),
                "question_source_pdf_page": question_source_page,
                "question_number_on_page": question_number,
                "question_source_page_image": (
                    f"questions/{candidate_id.replace(':', '-')}-source-page.png"
                    if question_pdf is not None else None
                ),
                "question_source_page_visual_checked": False,
                "new_evidence_cards": card_rows,
                "review_decision": "pending_blind_evidence_review",
            })

        # Assign each question once, before rendering crops, so partition and image
        # owner cannot drift apart. Keep each question's complete slate together.
        rows_a, rows_b = _balanced_partition(rows)
        for agent_name, agent_rows in (("agent-a", rows_a), ("agent-b", rows_b)):
            crop_dir = output / agent_name / "crops"
            crop_dir.mkdir(parents=True, exist_ok=True)
            question_dir = output / agent_name / "questions"
            if question_pdf is not None:
                question_dir.mkdir(parents=True, exist_ok=True)
            for row in agent_rows:
                if question_pdf is not None:
                    source_page = question_pdf[int(row["question_source_pdf_page"]) - 1]
                    image_name = Path(row["question_source_page_image"]).name
                    source_page.get_pixmap(matrix=pymupdf.Matrix(1.35, 1.35),
                                            alpha=False).save(question_dir / image_name)
                for card in row["new_evidence_cards"]:
                    checksum = card["source_checksum"]
                    page = pdfs[checksum][int(card["source_page"]) - 1]
                    # The review crop intentionally matches the indexed bbox
                    # exactly. Padding can display neighbouring PDF text and
                    # invite a reviewer to quote material absent from the
                    # provenance-bound record.
                    bbox = pymupdf.Rect(card["bbox"]) & page.rect
                    page.get_pixmap(matrix=pymupdf.Matrix(1.55, 1.55), clip=bbox,
                                    alpha=False).save(crop_dir / card["crop_filename"])
                    card["crop"] = f"crops/{card['crop_filename']}"
                    del card["crop_filename"]

    for agent_name, agent_rows in (("agent-a", rows_a), ("agent-b", rows_b)):
        pack_dir = output / agent_name
        pack_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema": pack_schema,
            "review_partition": agent_name,
            "source_queue": f"dort-dortluk-meb-evidence-proposals-{queue_label}.json",
            "source_checksum": v7.get("source_checksum"),
            "corpus_checksum": corpus.get("corpus_checksum"),
            "review_scope": review_scope,
            "question_count": len(agent_rows),
            "crop_count": sum(len(row["new_evidence_cards"]) for row in agent_rows),
            "new_crop_count": sum(
                sum(crop_signature({
                    "source_checksum": card["source_checksum"],
                    "page": card["source_page"],
                    "bbox": card["bbox"],
                }) not in old_signatures_by_question.get(row["candidate_id"], set())
                    for card in row["new_evidence_cards"])
                for row in agent_rows
            ),
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
            "teacher_approval": False,
            "runtime_enabled": False,
            "qlora_enabled": False,
            "kaggle_enabled": False,
            "question_source_checksum": transcriptions.get("source_checksum"),
            "question_source_pages_visually_checked": False,
            "reviews": agent_rows,
        }
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        sections = []
        for row in agent_rows:
            question = row["question"]
            parts = " ".join(part.get("text", "") for part in question.get("parts", []))
            choices = "".join(f"<li>{html.escape(choice['label'])}. {html.escape(choice['text'])}</li>"
                              for choice in question.get("choices", []))
            cards = "".join(
                f"<figure><img src='{html.escape(card['crop'])}' alt='PDF kaynak kesiti, "
                f"sayfa {card['source_page']}, sıra {card['rank_in_expanded_queue']}' "
                f"loading='lazy'><figcaption>Sıra {card['rank_in_expanded_queue']} · "
                f"{html.escape(card['source_name'])} · sayfa {card['source_page']} · "
                f"{html.escape(card['section_title'])} · katman: "
                f"{html.escape(card['index_layer'])} · çıkarım: "
                f"{html.escape(str(card.get('extraction_method') or 'belirtilmemiş'))}"
                f"</figcaption><details><summary>İndeks metni</summary><p>"
                f"{html.escape(card['indexed_excerpt'])}</p></details></figure>"
                for card in row["new_evidence_cards"]
            )
            question_page = ""
            if row.get("question_source_page_image"):
                question_page = (
                    f"<figure><img src='{html.escape(row['question_source_page_image'])}' "
                    f"alt='Orijinal soru sayfası {row['question_source_pdf_page']}; "
                    f"incelenecek soru {row['question_number_on_page']}' loading='lazy'>"
                    f"<figcaption>Orijinal soru PDF sayfası "
                    f"{row['question_source_pdf_page']} · sayfadaki soru "
                    f"{row['question_number_on_page']}. Görsel bağımlılığını bu sayfadan kontrol edin.</figcaption></figure>"
                )
            sections.append(
                f"<section><h2>{html.escape(row['candidate_id'])} · {html.escape(row['topic'])}</h2>"
                f"{question_page}<p>{html.escape(parts)}</p><ol>{choices}</ol>{cards}</section>"
            )
        (pack_dir / "index.html").write_text(
            f"<!doctype html><meta charset='utf-8'><title>AYT kaynak kanıtı top-{expanded_limit}</title>"
            "<style>body{font:16px system-ui;max-width:1300px;margin:auto;color:#123}"
            "section{padding:1.2rem;margin:1rem;border:1px solid #abc;border-radius:10px}"
            "figure{display:inline-block;vertical-align:top;width:31%;margin:1%}"
            "img{max-width:100%;border:1px solid #789}figcaption{font-size:.85em}</style>"
            f"<h1>AYT Tarih: top-{expanded_limit} MEB kanıt adayları</h1><p>"
            + (f"Top-{expanded_limit} havuzundaki tüm kesitler gösterilir. Önceki inceleme kararlarından "
               f"bağımsız olarak {expanded_limit} kesitin tamamını birlikte değerlendirin. "
               if include_previous else
               f"Yalnız önceki top-{previous_limit} kuyruğunda bulunmayan top-{expanded_limit} "
               f"kaynak kesitleri gösterilir. ")
            + "Şık/cevap anahtarı ve çözümler yoktur. "
            "Her soruda kaynakların kökü gerçekten destekleyip desteklemediğini ve eksik/çelişkili "
            "iddiaları ayrı değerlendirin; bu paket onay değildir.</p>" + "".join(sections),
            encoding="utf-8")
    return {
        "schema": pack_schema,
        "review_scope": review_scope,
        "source_checksum": v7.get("source_checksum"),
        "corpus_checksum": corpus.get("corpus_checksum"),
        "question_count": len(rows),
        "crop_count": reviewed_crop_count,
        "new_crop_count": new_crop_count,
        "agent_a_questions": len(rows_a),
        "agent_b_questions": len(rows_b),
        "answer_key_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v6", type=Path, required=True)
    parser.add_argument("--v7", type=Path, required=True)
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--exclude-id", action="append", default=[])
    parser.add_argument(
        "--include-previous", action="store_true",
        help="Review all top-24 crops together, including candidates from the previous top-12.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--queue-label", default="v7-top24")
    parser.add_argument("--question-pdf", type=Path)
    args = parser.parse_args()
    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in (
        args.v6, args.v7, args.transcriptions, args.corpus, args.adjudications)]
    result = build(*inputs[:2], inputs[2], inputs[3], inputs[4],
                   set(args.exclude_id), args.output, args.root,
                   include_previous=args.include_previous,
                   queue_label=args.queue_label,
                   question_pdf_path=args.question_pdf)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
