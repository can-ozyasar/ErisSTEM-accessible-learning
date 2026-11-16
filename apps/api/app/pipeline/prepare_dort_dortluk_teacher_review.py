"""Render answer-free source crops for private review of Dört Dörtlük items."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf

SCHEMA = "ogm-dort-dortluk-teacher-review-pack-v1"


def build(candidates: dict, source: Path, output: Path) -> dict:
    if candidates.get("schema") != "ogm-dort-dortluk-ayt-target-candidates-v1":
        raise ValueError("Dört Dörtlük private aday havuzu gerekli")
    if candidates.get("answer_key_accessed") is not False or candidates.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap/çözüm erişimli aday paketi kullanılamaz")
    raw = source.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != candidates.get("source_checksum"):
        raise ValueError("Aday ve PDF checksum'ları eşleşmiyor")
    rows = []
    output.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        for item in [*candidates.get("rows", []), *candidates.get("review_queue", [])]:
            page_no = item["source_physical_page"]
            bbox = pymupdf.Rect(item["source_bbox"]) + (-14, -10, 14, 10)
            page = pdf[page_no - 1]
            bbox &= page.rect
            name = f"{item['candidate_id'].split(':')[-2]}-{item['candidate_id'].split(':')[-1]}.png"
            rel = Path("crops") / name
            (output / rel).parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), clip=bbox, alpha=False).save(output / rel)
            rows.append({
                "candidate_id": item["candidate_id"],
                "page_scope_candidates": item["page_scope_candidates"],
                "source_physical_page": page_no,
                "source_printed_page": item["source_printed_page"],
                "question": item["question"],
                "extraction_issues": item["extraction_issues"],
                "pdf_crop": rel.as_posix(),
                "crop_checked": False,
                "target_section_decision": "pending",
                "visual_independence": "pending",
                "training_approval": False,
            })
    manifest = {
        "schema": SCHEMA,
        "source_checksum": checksum,
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "student_rag_enabled": False,
        "kaggle_export_enabled": False,
        "qlora_enabled": False,
        "rows": rows,
        "notice": "Özel inceleme paketi. Hiçbir soru veya kesit onaylanmış değildir; cevap anahtarı ve çözümler pakete alınmamıştır.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sections = []
    for row in rows:
        q = row["question"]
        parts = " ".join(p.get("text", "") for p in q.get("parts", []))
        choices = "".join(f"<li>{html.escape(c['label'])}. {html.escape(c['text'])}</li>"
                          for c in q.get("choices", []))
        sections.append(
            f"<section><h2>{html.escape(row['candidate_id'])} · basılı s. {row['source_printed_page']}</h2>"
            f"<p>Ünite adayı: {html.escape(', '.join(row['page_scope_candidates']))}</p>"
            f"<p>{html.escape(parts)}</p><ol>{choices}</ol>"
            f"<img src='{html.escape(row['pdf_crop'])}' alt='Sorunun doğrulanacağı asıl PDF kesiti'>"
            f"<p>Çıkarım uyarıları: {html.escape(', '.join(row['extraction_issues']) or 'yok')}</p></section>"
        )
    (output / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Dört Dörtlük soru incelemesi</title>"
        "<style>body{font:17px system-ui;max-width:1200px;margin:2rem auto;color:#102a43}"
        "section{border:1px solid #9fb3c8;padding:1.2rem;margin:1rem 0;border-radius:12px}"
        "img{display:block;max-width:100%;border:1px solid #bcccdc}</style>"
        "<h1>Dört Dörtlük AYT Tarih: özel soru inceleme paketi</h1>"
        "<p>Kaynak metni, şıklar ve PDF kesiti karşılaştırılmalı. Cevap anahtarı/çözümler yoktur."
        " Görsel bağımlı sorular pilot kapsamı dışıdır. Tüm kararlar beklemededir.</p>"
        + "".join(sections), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    result = build(candidates, args.source, args.output)
    print(json.dumps({"candidate_count": result["candidate_count"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
