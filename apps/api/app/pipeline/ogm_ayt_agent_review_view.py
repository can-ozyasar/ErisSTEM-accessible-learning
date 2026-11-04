"""Render a private, accessible view of agent source judgments and PDF crops."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

LABELS = {"direct": "Doğrudan aday", "partial": "Kısmi bağlam",
          "irrelevant": "İlgisiz", "uncertain": "Belirsiz"}


def render(audit: dict, pack: dict, validation: dict) -> str:
    if (audit.get("schema") != "ogm-ayt-full-agent-audit-v1"
            or pack.get("schema") != "ogm-ayt-teacher-review-pack-v1"
            or validation.get("schema") != "ogm-ayt-agent-audit-validation-v1"
            or audit.get("source_checksum") != validation.get("source_checksum")
            or validation.get("question_count") != pack.get("review_count")):
        raise ValueError("Denetim, PDF paketi ve doğrulama sürümleri eşleşmiyor")
    pack_rows = {row["candidate_id"]: row for row in pack["reviews"]}
    sections = []
    for review in audit["reviews"]:
        row = pack_rows[review["candidate_id"]]
        if len(review["cards"]) != len(row["evidence_cards"]):
            raise ValueError("PDF kartlarının sayısı agent kararlarıyla eşleşmiyor")
        choices = "".join(f'<li>{html.escape(str(choice["label"]))}. '
                          f'{html.escape(choice["text"])}</li>'
                          for choice in row["question"]["choices"])
        figures = []
        for judgment, card in zip(review["cards"], row["evidence_cards"]):
            if (judgment["chunk_id"] != card["chunk_id"]
                    or judgment["source_checksum"] != card["source_checksum"]):
                raise ValueError("PDF kartlarının sırası agent kararlarıyla eşleşmiyor")
            verdict = LABELS[judgment["verdict"]]
            figures.append(
                f'<article class="card"><h4>{html.escape(verdict)} · '
                f'{html.escape(card["section_title"])} · s. {card["page"]}</h4>'
                f'<p>{html.escape(judgment["reason"])}</p>'
                + (f'<blockquote>{html.escape(judgment["quote"])}</blockquote>'
                   if judgment.get("quote") else "")
                + f'<img loading="lazy" src="{html.escape(card["crop"])}" '
                'alt="MEB PDF kesiti; tarihsel ilişki kararı ayrıca denetlenmelidir."></article>'
            )
        sections.append(
            f'<section><h2>{html.escape(row["topic"])} · '
            f'{html.escape(review["candidate_id"])}</h2>'
            f'<p>{html.escape(row["question"]["stem"])}</p><ol>{choices}</ol>'
            f'<div class="cards">{"".join(figures)}</div></section>'
        )
    counts = validation["verdict_counts"]
    summary = ", ".join(f"{html.escape(LABELS[key])}: {counts.get(key, 0)}" for key in LABELS)
    return (
        '<!doctype html><html lang="tr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>AYT kaynak ön incelemesi</title>'
        '<style>body{font:18px/1.6 system-ui;background:#eef7fc;color:#102f43;'
        'max-width:1200px;margin:auto;padding:1rem}section,.card{background:white;'
        'border:2px solid #a5c8d9;border-radius:12px;padding:1rem;margin:1rem 0}'
        '.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1rem}'
        '.card{margin:0}img{max-width:100%;height:auto}blockquote{border-left:4px solid #4082a5;'
        'padding-left:1rem}*:focus-visible{outline:4px solid #005f9c}</style>'
        '<main><h1>AYT kaynak ön incelemesi</h1>'
        '<p><strong>Bu kararlar ajan ön incelemesidir; öğretmen onayı, Gold etiket '
        'veya öğrenciye gösterilecek kanıt değildir.</strong></p>'
        f'<p>{validation["question_count"]} soru, {validation["card_count"]} kesit. '
        f'{summary}.</p>{"".join(sections)}</main></html>'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body = render(json.loads(args.audit.read_text(encoding="utf-8")),
                  json.loads(args.pack.read_text(encoding="utf-8")),
                  json.loads(args.validation.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()
