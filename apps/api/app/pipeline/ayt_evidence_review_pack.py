"""Render a private, checksum-verified PDF-crop review pack for AYT evidence.

The pack is an offline teacher aid. It contains no answers, changes no review
state and is written only below ``data/private`` by the caller.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _question_text(question: dict) -> str:
    pieces = [part.get("text", "") for part in question.get("parts", [])]
    pieces.extend(f'{choice.get("label", "")}): {choice.get("text", "")}'
                  for choice in question.get("choices", []))
    return "\n".join(piece.strip() for piece in pieces if piece.strip())


def _render_crop(pdf: pymupdf.Document, page: int, bbox: list[float], target: Path) -> None:
    source_page = pdf[page - 1]
    clip = pymupdf.Rect(bbox) + (-20, -20, 20, 20)
    clip &= source_page.rect
    if clip.is_empty or clip.is_infinite:
        raise ValueError("Geçersiz kanıt kırpımı")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), clip=clip, alpha=False).save(target)


def build(questions: dict, proposals: dict, source_root: Path, output: Path,
          per_question: int | None = None) -> dict:
    if questions.get("schema") != "ayt-tarih2-candidates-v1":
        raise ValueError("Beklenen AYT aday şeması bulunamadı")
    if proposals.get("schema") not in {"ayt-evidence-proposals-v1", "ayt-evidence-bundle-proposals-v1"}:
        raise ValueError("Beklenen kanıt öneri şeması bulunamadı")
    if questions.get("source_checksum") != proposals.get("question_source_checksum"):
        raise ValueError("Soru ve öneri checksum'ları eşleşmiyor")
    if per_question is not None and per_question < 1:
        raise ValueError("Her soru için en az bir kırpım gerekli")

    source_by_checksum = {}
    for proposal in proposals.get("proposals", []):
        for suggestion in proposal.get("suggestions", []):
            path = source_root / suggestion["source_name"]
            source_by_checksum.setdefault(suggestion["source_checksum"], path)
    for checksum, path in source_by_checksum.items():
        if not path.is_file() or _checksum(path) != checksum:
            raise ValueError("MEB kaynak PDF checksum'ı eşleşmiyor")

    candidates = {row["candidate_id"]: row for row in questions.get("candidates", [])}
    documents = {checksum: pymupdf.open(path) for checksum, path in source_by_checksum.items()}
    try:
        rows = []
        crop_count = 0
        for proposal in proposals.get("proposals", []):
            if proposal.get("status") not in {"teacher_review_required", "reretrieve_required"}:
                continue
            question = candidates.get(proposal["candidate_id"])
            if question is None:
                raise ValueError("Öneri için soru adayı bulunamadı")
            cards = []
            suggestions = proposal.get("suggestions", [])
            if per_question is not None:
                suggestions = suggestions[:per_question]
            for rank, suggestion in enumerate(suggestions, 1):
                filename = f'{suggestion["source_checksum"][:12]}-{suggestion["chunk_id"]}.png'
                relative = Path("crops") / filename
                _render_crop(documents[suggestion["source_checksum"]], suggestion["page"], suggestion["bbox"],
                             output / relative)
                cards.append({
                    "rank": rank, "source_name": suggestion["source_name"], "grade": suggestion["grade"],
                    "section_title": suggestion["section_title"], "page": suggestion["page"],
                    "source_checksum": suggestion["source_checksum"], "chunk_id": suggestion["chunk_id"],
                    "crop": relative.as_posix(), "pre_review": suggestion.get("pre_review", {}),
                    "constraint_clause_id": suggestion.get("constraint_clause_id"),
                    "constraint_clause_ids": suggestion.get("constraint_clause_ids"),
                    "source_type": suggestion.get("source_type"),
                    "claim_id": suggestion.get("claim_id"), "claim_ids": suggestion.get("claim_ids"),
                    "suggested_role": suggestion.get("suggested_role"),
                    "suggested_roles": suggestion.get("suggested_roles"),
                    "claim_match_status": suggestion.get("claim_match_status"),
                    "entity_groups_covered": suggestion.get("entity_groups_covered"),
                    "entity_group_count": suggestion.get("entity_group_count"),
                })
                crop_count += 1
            rows.append({"candidate_id": proposal["candidate_id"], "exam_year": proposal["exam_year"],
                         "question_text": _question_text(question["question"]), "cards": cards,
                         "evidence_plan": proposal.get("evidence_plan"),
                         "status": proposal["status"]})
    finally:
        for document in documents.values():
            document.close()

    manifest = {
        "schema": "ayt-evidence-review-pack-v1", "corpus_checksum": proposals["corpus_checksum"],
        "question_source_checksum": questions["source_checksum"], "per_question": per_question,
        "review_count": len(rows), "crop_count": crop_count, "reviews": rows,
        "notice": "Private teacher PDF-crop review only. This pack does not approve evidence or expose answers.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    _write_html(manifest, output / "index.html")
    return manifest


def _write_html(manifest: dict, target: Path) -> None:
    def constraint_caption(card: dict) -> str:
        bits = []
        if card.get("constraint_clause_id"):
            clauses = card.get("constraint_clause_ids") or [card["constraint_clause_id"]]
            bits.append("Kısıt: " + html.escape(", ".join(clauses)))
        if card.get("claim_id"):
            claims = card.get("claim_ids") or [card["claim_id"]]
            roles = card.get("suggested_roles") or [card.get("suggested_role")]
            roles = [role for role in roles if role]
            bits.append("Önerilen kanıt: " + html.escape(", ".join(claims))
                        + (" · rol: " + html.escape(", ".join(roles)) if roles else ""))
        if card.get("claim_match_status") == "partial_candidate":
            bits.append("Keşif adayı: zorunlu ilişkinin yalnız "
                        f'{card.get("entity_groups_covered", 0)}/{card.get("entity_group_count", 0)} '
                        "ucu metinde bulundu; kanıt değildir")
        if not bits:
            return ""
        source_type = f'<br>Kaynak türü: {html.escape(card["source_type"])}' if card.get("source_type") else ""
        return "<br>" + "<br>".join(bits) + source_type

    blocks = []
    for row in manifest["reviews"]:
        cards = "".join(
            "<figure><figcaption>"
            f'#{card["rank"]} · {html.escape(card["source_name"])} · {card["grade"]}. sınıf · '
            f's. {card["page"]}<br>{html.escape(card["section_title"])}'
            f'{constraint_caption(card)}</figcaption>'
            f'<img src="{html.escape(card["crop"])}" alt="MEB PDF kanıt kırpımı"></figure>'
            for card in row["cards"]
        )
        plan = row.get("evidence_plan") or {}
        plan_caption = ""
        if plan:
            labels = ", ".join(plan.get("topic_labels", []))
            required = ", ".join(plan.get("required_claim_ids", []))
            missing = ", ".join(plan.get("missing_claim_ids", [])) or "yok"
            plan_caption = (f'<p><strong>Konu:</strong> {html.escape(labels) or "belirtilmedi"}<br>'
                            f'<strong>Zorunlu kanıt iddiaları:</strong> {html.escape(required)}<br>'
                            f'<strong>Bulunamayan iddia:</strong> {html.escape(missing)}</p>')
        blocks.append(
            f'<section><h2>{html.escape(str(row["exam_year"]))} AYT · '
            f'{html.escape(row["candidate_id"])}</h2><pre>{html.escape(row["question_text"])}</pre>'
            f'{plan_caption}<div class="cards">{cards}</div><p>Durum: '
            f'{"hedefli yeniden getirme gerekli; kartlar kanıt değildir." if row.get("status") == "reretrieve_required" else "PDF kırpımıyla inceleme bekliyor."}'
            "</p></section>"
        )
    target.write_text(
        "<!doctype html><meta charset=utf-8><title>AYT kanıt incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#102a43}"
        "section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}"
        ".cards{display:flex;gap:1rem;overflow:auto}figure{min-width:360px;margin:0}"
        "img{max-width:100%;border:1px solid #bcccdc}pre{white-space:pre-wrap;font:inherit}</style>"
        "<h1>AYT Tarih-2 kanıt inceleme paketi</h1>"
        "<p>Bu paket cevap içermez ve hiçbir kanıtı onaylamaz. Her kırpımı PDF ile karşılaştırın.</p>"
        + "".join(blocks), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-question", type=int,
                        help="İnceleme paketi için isteğe bağlı kart sınırı; verilmezse tüm kanıt adayları gösterilir")
    args = parser.parse_args()
    build(json.loads(args.questions.read_text(encoding="utf-8")),
          json.loads(args.proposals.read_text(encoding="utf-8")), args.source_root, args.output,
          args.per_question)


if __name__ == "__main__":
    main()
