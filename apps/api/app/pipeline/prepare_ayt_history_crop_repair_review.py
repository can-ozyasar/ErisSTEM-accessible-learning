"""Create a local, prioritized repair queue for non-exact PDF crop evidence.

The queue is deliberately diagnostic: it renders a small amount of page
context and records the deterministic audit result.  It neither rewrites a
candidate's evidence nor changes its publication/training eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf

SCHEMA = "ayt-history-crop-repair-review-v1"
AUDIT_SCHEMA = "ayt-history-candidate-pdf-crop-text-audit-v1"


def _checksum(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sources(catalog: dict, root: Path) -> dict[str, tuple[dict, Path]]:
    if catalog.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    resolved_root = root.resolve()
    result: dict[str, tuple[dict, Path]] = {}
    for source in catalog.get("sources", []):
        relative = Path(str(source.get("relative_path", "")))
        path = (resolved_root / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(resolved_root)
                or not path.is_file()):
            raise ValueError("Kaynak kataloğunda güvenli bir yerel PDF yolu gerekli")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != source.get("source_checksum"):
            raise ValueError("Yerel MEB PDF checksum'ı katalogla uyuşmuyor")
        if source.get("id") in result:
            raise ValueError("Benzersiz kaynak kimliği gerekli")
        result[source["id"]] = (source, path)
    return result


def build(candidate_pack: dict, audit: dict, source_catalog: dict, source_root: Path, output: Path) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün aday paketi gerekli")
    if len(candidate_pack.get("questions", [])) != 120:
        raise ValueError("Tam 120 aday soru gerekli")
    if audit.get("schema") != AUDIT_SCHEMA or audit.get("candidate_checksum") != candidate_pack.get("candidate_checksum"):
        raise ValueError("Aday paketiyle eşleşen PDF kırpım denetimi gerekli")
    records = audit.get("records", [])
    if len(records) != 120 or len({row.get("id") for row in records}) != 120:
        raise ValueError("Her aday için tam bir PDF kırpım denetim kaydı gerekli")
    question_by_id = {row.get("id"): row for row in candidate_pack["questions"]}
    source_by_id = _sources(source_catalog, source_root)
    pending = [row for row in records if row.get("quote_present_in_bbox") is not True]
    # Material mismatches first; near matches remain review work rather than an automatic correction.
    pending.sort(key=lambda row: (row.get("character_similarity", 0) >= 0.9, row.get("character_similarity", 0), row["id"]))
    output.mkdir(parents=True, exist_ok=True)
    crop_dir = output / "context-crops"
    crop_dir.mkdir(exist_ok=True)
    documents: dict[str, pymupdf.Document] = {}
    reviews = []
    try:
        for priority, record in enumerate(pending, start=1):
            question = question_by_id.get(record["id"])
            source_data = source_by_id.get(record.get("source_id"))
            if question is None or source_data is None:
                raise ValueError("Denetim kaydı aday ve katalog kaynağıyla eşleşmeli")
            evidence = question.get("source_evidence", {})
            source, path = source_data
            if (evidence.get("source_id") != source["id"] or evidence.get("source_checksum") != source.get("source_checksum")
                    or evidence.get("page") != record.get("page") or evidence.get("bbox") != record.get("bbox")):
                raise ValueError("Denetim kaydı aday kanıtıyla eşleşmiyor")
            document = documents.setdefault(source["id"], pymupdf.open(path))
            page = document[record["page"] - 1]
            rect = pymupdf.Rect(record["bbox"])
            if rect.is_empty or not page.rect.contains(rect):
                raise ValueError("Kanıt bbox değeri kaynak sayfası dışında")
            # Enough surrounding context to diagnose a boundary, while avoiding a full-book export.
            context = rect + (-42, -42, 42, 42)
            context &= page.rect
            filename = f"{priority:02d}-{record['id']}-{source['source_checksum'][:12]}-p{record['page']}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=context, alpha=False).save(crop_dir / filename)
            similarity = float(record.get("character_similarity", 0))
            reviews.append({
                "priority": priority,
                "id": record["id"],
                "status": "review_required",
                "reason": "material_text_mismatch" if similarity < 0.9 else "near_text_match",
                "character_similarity": similarity,
                "source_id": source["id"],
                "source_checksum": source["source_checksum"],
                "page": record["page"],
                "bbox": record["bbox"],
                "context_crop": (Path("context-crops") / filename).as_posix(),
                "candidate_quote": evidence.get("quote"),
                "checks": {"bbox_boundary_correct": None, "quote_transcription_correct": None,
                           "source_supports_question": None, "text_only_accessible": None},
                "reviewer": None,
                "reviewed_at": None,
                "notes": "",
            })
    finally:
        for document in documents.values():
            document.close()
    return {
        "schema": SCHEMA,
        "candidate_checksum": candidate_pack["candidate_checksum"],
        "audit_checksum": _checksum(audit),
        "source_catalog_checksum": _checksum(source_catalog),
        "review_count": len(reviews),
        "reviews": reviews,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "is_human_teacher_approval": False,
        "notice": "Local diagnostic repair queue only. No review result changes source evidence, runtime, or training eligibility automatically.",
    }


def _write_html(result: dict, questions: dict[str, dict], output: Path) -> None:
    cards = []
    for review in result["reviews"]:
        question = questions[review["id"]]
        choices = "".join(f"<li>{html.escape(str(choice))}</li>" for choice in question["choices"])
        cards.append(
            f"<article><h2>#{review['priority']} — {html.escape(review['id'])}</h2>"
            f"<p><strong>Neden:</strong> {html.escape(review['reason'])}; benzerlik: {review['character_similarity']:.4f}</p>"
            f"<p>{html.escape(question['question'])}</p><ol type='A'>{choices}</ol>"
            f"<p><strong>Aday alıntı:</strong> {html.escape(str(review['candidate_quote']))}</p>"
            f"<p>Kaynak: {html.escape(review['source_id'])}, s. {review['page']}</p>"
            f"<img src='{html.escape(review['context_crop'])}' alt='Yerel MEB PDF bağlam kırpımı'>"
            "<p>İnceleme yalnız tanısaldır; bu kart yayımlama veya insan onayı değildir.</p></article>"
        )
    (output / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>AYT Tarih kanıt onarım incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:960px;margin:2rem auto;padding:0 1rem}article{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}img{max-width:100%;border:1px solid #bcccdc}</style>"
        "<h1>AYT Tarih: kanıt sınırı/alıntı onarım incelemesi</h1><p>Bu sayfa otomatik onay vermez.</p>"
        + "".join(cards),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    candidate_pack = load(args.candidate_pack)
    result = build(candidate_pack, load(args.audit), load(args.source_catalog), args.source_root, args.output)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, {row["id"]: row for row in candidate_pack["questions"]}, args.output)
    print(json.dumps({"review_count": result["review_count"], "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
