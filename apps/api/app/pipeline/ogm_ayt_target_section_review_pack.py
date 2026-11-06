"""Render a private PDF-crop pack for broad OGM AYT candidates.

The pack joins the answer-free question transcription with MEB evidence
candidate crops.  It is an inspection artifact only: no answer key, solution,
approval or runtime/QLoRA export is created.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf

from .ayt_evidence_review_pack import _render_crop

TRANSCRIPTION_SCHEMA = "ogm-ayt-private-transcription-v1"
QUEUE_SCHEMA = "ayt-target-atom-context-review-queue-v1"


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_path(roots: list[Path], name: str) -> Path:
    for root in roots:
        path = root / name
        if path.is_file():
            return path
    raise ValueError(f"Kaynak PDF bulunamadı: {name}")


def build(transcriptions: dict, queue: dict, corpus: dict, roots: list[Path], output: Path,
          section_audit: dict | None = None, per_question: int = 3) -> dict:
    if transcriptions.get("schema") != TRANSCRIPTION_SCHEMA:
        raise ValueError("Özel OGM transkripsiyonu gerekli")
    if queue.get("schema") != QUEUE_SCHEMA:
        raise ValueError("AYT atom-bağlam kuyruğu gerekli")
    if queue.get("answer_key_accessed") is not False or queue.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap anahtarı veya çözüm erişimli kuyruk kullanılamaz")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü MEB corpus gerekli")
    if per_question < 1:
        raise ValueError("Soru başına en az bir kanıt kartı gerekli")
    questions = {row["candidate_id"]: row for row in transcriptions.get("rows", [])}
    audit_by_id = {row.get("candidate_id"): row for row in (section_audit or {}).get("records", [])}
    books = {book["source_checksum"]: book for book in corpus.get("books", [])}
    pdfs: dict[str, pymupdf.Document] = {}
    rows, crop_count = [], 0
    try:
        for proposal in queue.get("proposals", []):
            question = questions.get(proposal.get("candidate_id"))
            if question is None:
                raise ValueError("Kuyruk sorusu transkripsiyonda yok")
            cards = []
            for rank, suggestion in enumerate(proposal.get("suggestions", [])[:per_question], 1):
                checksum = suggestion["source_checksum"]
                book = books.get(checksum)
                if book is None:
                    raise ValueError("Kanıt kaynağı corpus içinde yok")
                pdf_path = _source_path(roots, book["source_name"])
                if _checksum(pdf_path) != checksum:
                    raise ValueError("MEB PDF checksum doğrulaması başarısız")
                document = pdfs.setdefault(checksum, pymupdf.open(pdf_path))
                filename = f"{checksum[:12]}-{suggestion['record_id']}.png"
                rel = Path("crops") / filename
                _render_crop(document, suggestion["page"], suggestion["bbox"], output / rel)
                cards.append({
                    "rank": rank, "record_id": suggestion["record_id"], "source_name": book["source_name"],
                    "source_checksum": checksum, "grade": book.get("grade"),
                    "section_id": suggestion.get("section_id"), "section_title": suggestion.get("section_title"),
                    "page": suggestion["page"], "bbox": suggestion["bbox"], "crop": rel.as_posix(),
                    "granularity": suggestion.get("granularity"), "review_status": "candidate_unverified",
                })
                crop_count += 1
            rows.append({
                "candidate_id": proposal["candidate_id"], "topic": question.get("topic"),
                "question": question["question"], "section_proposal": audit_by_id.get(proposal["candidate_id"]),
                "need_plan": proposal.get("need_plan"), "cards": cards,
                "status": "pdf_crop_review_required",
            })
    finally:
        for pdf in pdfs.values():
            pdf.close()
    manifest = {
        "schema": "ogm-ayt-target-section-review-pack-v1",
        "corpus_checksum": corpus["corpus_checksum"], "question_source_checksum": transcriptions["source_checksum"],
        "review_count": len(rows), "crop_count": crop_count, "per_question": per_question, "reviews": rows,
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Private PDF crop review only. Candidates are not source-approved and contain no answers or solutions.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    blocks = []
    for row in rows:
        choices = "".join(f"<li>{html.escape(c['label'])}. {html.escape(c['text'])}</li>" for c in row["question"].get("choices", []))
        cards = "".join(f"<figure><figcaption>#{c['rank']} · {html.escape(c['source_name'])} · s. {c['page']} · {html.escape(c.get('section_title') or '')}</figcaption><img src='{html.escape(c['crop'])}' alt='MEB PDF kanıt kırpımı'></figure>" for c in row["cards"])
        blocks.append(f"<section><h2>{html.escape(row['candidate_id'])}</h2><p>{html.escape(row['question'].get('stem',''))}</p><ol>{choices}</ol><div>{cards}</div><p>Durum: PDF kesitiyle inceleme gerekli.</p></section>")
    (output / "index.html").write_text("<!doctype html><meta charset=utf-8><title>AYT bölüm ve kanıt incelemesi</title><style>body{font:16px system-ui;max-width:1500px;margin:2rem auto;color:#102a43}section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}figure{display:inline-block;vertical-align:top;width:30%;margin:1%}img{max-width:100%;border:1px solid #bcccdc}</style><h1>AYT hedef bölüm / MEB kanıt incelemesi</h1><p>Bu paket cevap içermez ve hiçbir kanıtı onaylamaz.</p>" + "".join(blocks), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, action="append", required=True)
    parser.add_argument("--section-audit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-question", type=int, default=3)
    args = parser.parse_args()
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    result = build(load(args.transcriptions), load(args.queue), load(args.corpus), args.source_root, args.output,
                   load(args.section_audit) if args.section_audit else None, args.per_question)
    print(json.dumps({"reviews": result["review_count"], "crops": result["crop_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
