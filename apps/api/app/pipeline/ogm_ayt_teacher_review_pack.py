"""Render a private teacher-review pack for OGM questions and MEB evidence."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf

from .ayt_evidence_review_pack import _render_crop


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(transcriptions: dict, queue: dict, corpus: dict, source_root: Path,
          references: dict, worked_root: Path, output: Path, per_question: int = 3,
          include_worked_references: bool = True) -> dict:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private OGM transkripsiyonu gerekli")
    if queue.get("schema") not in {"ogm-ayt-evidence-review-queue-v1", "ogm-ayt-evidence-review-queue-v2",
                                   "ogm-ayt-evidence-review-queue-v3",
                                   "ogm-ayt-manual-source-discovery-v1",
                                   "ogm-ayt-relation-discovery-review-queue-v1",
                                   "ogm-ayt-evidence-human-review-queue-v1"}:
        raise ValueError("OGM kanıt inceleme kuyruğu gerekli")
    if queue.get("source_checksum") != transcriptions.get("source_checksum"):
        raise ValueError("Transkripsiyon ve kanıt kuyruğu kaynakları eşleşmiyor")
    if per_question < 1:
        raise ValueError("Her soru için en az bir kanıt kartı gerekli")
    by_source = {book["source_checksum"]: book for book in corpus.get("books", [])}
    questions = {row["candidate_id"]: row for row in transcriptions.get("rows", [])}
    reference_pages = {unit["topic"]: unit["teacher_only_reference_pages"] for unit in references.get("units", [])}
    documents: dict[str, pymupdf.Document] = {}
    reviews, crop_count = [], 0
    try:
        for proposal in queue.get("proposals", []):
            question = questions[proposal["candidate_id"]]
            if (queue["schema"] != "ogm-ayt-manual-source-discovery-v1"
                    and proposal.get("status") not in {"teacher_agent_source_review_required",
                                                       "teacher_human_source_approval_required"}):
                continue
            cards = []
            for suggestion in proposal["suggestions"][:per_question]:
                book = by_source.get(suggestion["source_checksum"])
                if book is None:
                    raise ValueError("Kanıt kaynağı corpus içinde yok")
                pdf = source_root / book["source_name"]
                if not pdf.is_file() or _checksum(pdf) != book["source_checksum"]:
                    raise ValueError("MEB PDF checksum doğrulaması başarısız")
                document = documents.setdefault(book["source_checksum"], pymupdf.open(pdf))
                name = f'{suggestion["source_checksum"][:12]}-{suggestion["chunk_id"]}.png'
                _render_crop(document, suggestion["page"], suggestion["bbox"], output / "crops" / name)
                cards.append({key: suggestion[key] for key in ("chunk_id", "source_name", "page", "section_title")})
                cards[-1]["score"] = suggestion.get("score", suggestion.get("fusion_score"))
                cards[-1]["source_checksum"] = suggestion["source_checksum"]
                cards[-1]["grade"] = suggestion.get("grade")
                cards[-1]["in_topic_section"] = suggestion.get("in_topic_section")
                cards[-1]["pre_review_decision"] = suggestion.get("pre_review_decision")
                cards[-1]["quality_warnings"] = suggestion.get("quality_warnings", [])
                cards[-1]["lexical_overlap_hint"] = (suggestion.get("claim_coverage") or {}).get("lexical_overlap_hint")
                cards[-1]["crop"] = f"crops/{name}"
                crop_count += 1
            refs = ([f"../pilot-worked-pages-v1/pages/{page:03d}.jpg"
                     for page in reference_pages.get(question["topic"], [])
                     if (worked_root / "pages" / f"{page:03d}.jpg").is_file()]
                    if include_worked_references else [])
            reviews.append({"candidate_id": question["candidate_id"], "topic": question["topic"],
                            "question": question["question"], "evidence_cards": cards,
                            "teacher_only_worked_reference_images": refs,
                            "status": "teacher_review_required"})
    finally:
        for document in documents.values():
            document.close()
    manifest = {"schema": "ogm-ayt-teacher-review-pack-v1", "review_count": len(reviews), "crop_count": crop_count,
                "reviews": reviews, "answer_key_accessed": False, "runtime_enabled": False,
                "notice": "Private teacher-review material. Worked references may be consulted only for evaluation; no answer or solution is exported to runtime or QLoRA."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _html(manifest, output / "index.html")
    return manifest


def _html(manifest: dict, target: Path) -> None:
    blocks = []
    for row in manifest["reviews"]:
        choices = "".join(f'<li>{html.escape(choice["label"])}. {html.escape(choice["text"])}</li>' for choice in row["question"]["choices"])
        cards = "".join(
            '<figure><figcaption>'
            + html.escape(card["section_title"])
            + f' · s. {card["page"]}'
            + (f' · {card["grade"]}. sınıf' if card.get("grade") else '')
            + (' · konu bölümü' if card.get("in_topic_section") else ' · diğer bölüm' if card.get("grade") else '')
            + (f' · {html.escape(card["pre_review_decision"])}' if card.get("pre_review_decision") else '')
            + '</figcaption><img src="' + html.escape(card["crop"])
            + '" alt="MEB kanıt kesiti. Kaynak ilişkisi öğretmen onayı bekliyor."></figure>'
            for card in row["evidence_cards"]
        )
        refs = "".join(f'<a href="{html.escape(ref)}">Çözümlü açıklama sayfası</a> ' for ref in row["teacher_only_worked_reference_images"])
        blocks.append(f'<section><h2>{html.escape(row["topic"])} · {html.escape(row["candidate_id"])}</h2><p>{html.escape(row["question"]["stem"])}</p><ol>{choices}</ol><div>{cards}</div><p>{refs or "Çözümlü açıklama referansı yok."}</p></section>')
    target.write_text("<!doctype html><meta charset=utf-8><title>AYT öğretmen incelemesi</title><style>body{font:16px system-ui;max-width:1400px;margin:2rem auto}section{border:1px solid #9fb3c8;margin:1rem;padding:1rem;border-radius:10px}figure{display:inline-block;vertical-align:top;width:30%;margin:1%}img{max-width:100%}</style><h1>AYT öğretmen inceleme paketi</h1><p>Bu paket private’tır. Kanıt onayı ve eğitim dışa aktarımı ayrı işlemdir.</p>" + "".join(blocks), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--worked-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-question", type=int, default=3)
    parser.add_argument("--hide-worked-references", action="store_true")
    args = parser.parse_args()
    build(json.loads(args.transcriptions.read_text(encoding="utf-8")), json.loads(args.queue.read_text(encoding="utf-8")),
          json.loads(args.corpus.read_text(encoding="utf-8")), args.source_root,
          json.loads(args.references.read_text(encoding="utf-8")), args.worked_root, args.output,
          per_question=args.per_question,
          include_worked_references=not args.hide_worked_references)


if __name__ == "__main__":
    main()
