"""Render a private, answer-free evidence-role review form for AYT crops."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROLE_LABELS = {
    "": "Rol seçilmedi",
    "primary": "Doğrudan kanıt",
    "context": "Açıklayıcı bağlam",
    "relation": "İlişki kanıtı",
    "contrast": "Karıştırılan bilgiyi ayırır",
}
OUTCOME_LABELS = {
    "pending": "Henüz karar vermedim",
    "evidence_selected": "Kaynak seçildi",
    "reretrieve": "Yeniden kaynak ara",
    "insufficient": "Yeterli kanıt yok",
}


def build(manifest: dict, target: Path) -> None:
    """Write an offline form whose download matches the retrieval-gold schema.

    No answer labels are rendered or exported. Browser-side validation requires
    a visible reviewer identifier, crop confirmation and a primary role before
    a case can be marked as evidence selected.
    """
    if manifest.get("schema") != "ayt-evidence-review-pack-v1":
        raise ValueError("Beklenen AYT PDF kırpım inceleme paketi bulunamadı")
    rows = []
    for review in manifest.get("reviews", []):
        cards = []
        for card in review.get("cards", []):
            roles = "".join(
                f'<option value="{role}">{label}</option>' for role, label in ROLE_LABELS.items()
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
        outcome = "".join(
            f'<option value="{value}">{label}</option>' for value, label in OUTCOME_LABELS.items()
        )
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
        "label{display:block;margin:.5rem 0}input,select{font:inherit}.guide{background:#eaf5ff;"
        "border-radius:12px;padding:1rem;margin:1rem 0}.guide li{margin:.35rem 0}</style>"
        "<h1>AYT Tarih-2 kanıt rol incelemesi</h1>"
        "<p>Bu form cevap anahtarı içermez. Kaynak rolü seçmek, öğrencide kullanıma açmak değildir.</p>"
        "<section class=guide><h2>Bu sayfada ne yapacağım?</h2><ol>"
        "<li>Önce soruyu, sonra her MEB PDF kesitini oku.</li>"
        "<li>Kesit sorudaki bilgiyi doğrudan söylüyorsa <b>Doğrudan kanıt</b> seç.</li>"
        "<li>Yalnız yardımcı açıklama veya bağlantı kuruyorsa uygun bağlam ya da ilişki rolünü seç.</li>"
        "<li>Hiçbiri soruyu güvenle desteklemiyorsa roller boş kalsın; sonuçta <b>Yeniden kaynak ara</b> ya da <b>Yeterli kanıt yok</b> seç.</li>"
        "<li>Her soruda karar verdikten sonra PDF kontrol kutusunu işaretle. En sonunda inceleyen kodunu yazıp indir düğmesine bas.</li>"
        "</ol></section>"
        '<label>İnceleyen kodu <input id="reviewer" required maxlength="80" placeholder="Örnek: canoz"></label>'
        '<button id="export">İncelemeyi private JSON olarak indir</button>' + "".join(rows)
        + "<script>const roles=['primary','context','relation','contrast'];"
        "document.getElementById('export').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();"
        "const cases=[...document.querySelectorAll('[data-case]')].map(section=>{const judgments=[...section.querySelectorAll('figure')].map(card=>({"
        "source_key:card.querySelector('[data-checksum]').value+':'+card.querySelector('[data-chunk]').value,"
        "source_checksum:card.querySelector('[data-checksum]').value,chunk_id:card.querySelector('[data-chunk]').value,"
        "role:card.querySelector('[data-role]').value||null}));return {candidate_id:section.dataset.id,exam_year:+section.dataset.year,"
        "outcome:section.querySelector('[data-outcome]').value,crop_checked:section.querySelector('[data-crop]').checked,"
        "reviewer:reviewer||null,judgments:judgments,note:section.querySelector('[data-note]').value||null};});"
        "const invalid=!reviewer||cases.some(x=>x.outcome==='evidence_selected'&&(!x.crop_checked||!x.judgments.some(j=>j.role==='primary')));"
        "if(invalid){alert('İnceleyen kodu, PDF kontrolü ve kaynak seçildi sonucunda en az bir Doğrudan kanıt gerekli.');return;}"
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
