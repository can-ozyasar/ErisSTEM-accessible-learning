"""Render a private, answer-free evidence-role review form for AYT crops."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROLES = ("", "primary", "context", "relation", "contrast")
OUTCOMES = ("pending", "evidence_selected", "reretrieve", "insufficient")


def build(manifest: dict, target: Path) -> None:
    """Write an offline form whose download matches the retrieval-gold schema.

    No answer labels are rendered or exported. Browser-side validation requires
    a visible reviewer identifier, crop confirmation and a primary role before
    a case can be marked as evidence selected.
    """
    if manifest.get("schema") != "ayt-evidence-review-pack-v1":
        raise ValueError("Beklenen AYT PDF kırpım inceleme paketi bulunamadı")
    rows = []
    for index, review in enumerate(manifest.get("reviews", [])):
        cards = []
        for card_index, card in enumerate(review.get("cards", [])):
            roles = "".join(
                f'<option value="{role}">{role or "rol seçilmedi"}</option>' for role in ROLES
            )
            cards.append(
                "<figure><figcaption>"
                f'{html.escape(card["source_name"])} · {card["grade"]}. sınıf · s. {card["page"]}<br>'
                f'{html.escape(card["section_title"])}</figcaption>'
                f'<img src="{html.escape(card["crop"])}" alt="MEB PDF kanıt kırpımı">'
                f'<label>Rol <select data-role>{roles}</select></label>'
                f'<input type="hidden" data-checksum value="{html.escape(card["source_checksum"])}">'
                f'<input type="hidden" data-chunk value="{html.escape(card["chunk_id"])}">'
                "</figure>"
            )
        outcome = "".join(f'<option value="{value}">{value}</option>' for value in OUTCOMES)
        rows.append(
            f'<section data-case data-id="{html.escape(review["candidate_id"])}" '
            f'data-year="{review["exam_year"]}"><h2>{html.escape(str(review["exam_year"]))} AYT</h2>'
            f'<pre>{html.escape(review["question_text"])}</pre><div class="cards">{"".join(cards)}</div>'
            f'<label>Sonuç <select data-outcome>{outcome}</select></label>'
            '<label><input type="checkbox" data-crop> PDF kırpımlarını kontrol ettim</label>'
            '<label>Not <input data-note maxlength="600"></label></section>'
        )
    target.write_text(
        "<!doctype html><meta charset=utf-8><title>AYT kanıt rol incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#102a43}"
        "section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}"
        ".cards{display:flex;gap:1rem;overflow:auto}figure{min-width:340px;margin:0}"
        "img{max-width:100%;border:1px solid #bcccdc}pre{white-space:pre-wrap;font:inherit}"
        "label{display:block;margin:.5rem 0}input,select{font:inherit}</style>"
        "<h1>AYT Tarih-2 kanıt rol incelemesi</h1>"
        "<p>Bu form cevap anahtarı içermez. Kaynak rolü seçmek, öğrencide kullanıma açmak değildir.</p>"
        '<label>İnceleyen kodu <input id="reviewer" required maxlength="80"></label>'
        '<button id="export">Private inceleme JSON’unu indir</button>' + "".join(rows)
        + "<script>const roles=['primary','context','relation','contrast'];"
        "document.getElementById('export').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();"
        "const cases=[...document.querySelectorAll('[data-case]')].map(section=>{const judgments=[...section.querySelectorAll('figure')].map(card=>({"
        "source_key:card.querySelector('[data-checksum]').value+':'+card.querySelector('[data-chunk]').value,"
        "source_checksum:card.querySelector('[data-checksum]').value,chunk_id:card.querySelector('[data-chunk]').value,"
        "role:card.querySelector('[data-role]').value||null}));return {candidate_id:section.dataset.id,exam_year:+section.dataset.year,"
        "outcome:section.querySelector('[data-outcome]').value,crop_checked:section.querySelector('[data-crop]').checked,"
        "reviewer:reviewer||null,judgments:judgments,note:section.querySelector('[data-note]').value||null};});"
        "const invalid=!reviewer||cases.some(x=>x.outcome==='evidence_selected'&&(!x.crop_checked||!x.judgments.some(j=>j.role==='primary')));"
        "if(invalid){alert('İnceleyen kodu, kırpım onayı ve seçilen kanıtta primary rolü gerekli.');return;}"
        f"const out={{schema:'ayt-retrieval-gold-v1',corpus_checksum:'{manifest['corpus_checksum']}',"
        f"question_source_checksum:'{manifest['question_source_checksum']}',cases:cases,notice:'Private human crop-review record. No answer key included.'}};"
        "const url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));const a=document.createElement('a');"
        "a.href=url;a.download='ayt-retrieval-gold-reviewed.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};</script>",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(json.loads(args.manifest.read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()
