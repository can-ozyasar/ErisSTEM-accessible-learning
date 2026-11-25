"""Build a local, checksum-bound review pack for real OGM AYT question crops."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

SCHEMA = "ogm-ayt-real-question-review-v1"


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render(document: pymupdf.Document, page: int, bbox: list[float], target: Path) -> None:
    if not 1 <= page <= document.page_count:
        raise ValueError("Soru sayfası PDF sınırları dışında")
    source_page = document[page - 1]
    clip = pymupdf.Rect(bbox) + (-12, -12, 12, 12)
    clip &= source_page.rect
    if clip.is_empty or clip.is_infinite:
        raise ValueError("Soru kırpım kutusu geçersiz")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=clip, alpha=False).save(target)


def build(candidate: dict, source_pdf: Path, output: Path) -> dict:
    if candidate.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("OGM AYT soru aday paketi gerekli")
    checksum = _checksum(source_pdf)
    if checksum != candidate.get("source_checksum"):
        raise ValueError("Yerel deneme PDF checksum'ı aday paketiyle uyuşmuyor")
    rows = candidate.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Soru adayları bulunamadı")
    reviews = []
    with pymupdf.open(source_pdf) as document:
        for item in rows:
            question = item.get("question", {})
            choices = question.get("choices", [])
            source = question.get("source", {})
            if question.get("question_type") != "multiple_choice" or [choice.get("label") for choice in choices] != list("ABCDE"):
                continue
            parts = question.get("parts", [])
            text = "\n\n".join(part.get("text", "").strip() for part in parts if part.get("text", "").strip())
            if not text or len(choices) != 5 or any(not choice.get("text", "").strip() for choice in choices):
                continue
            page, bbox = source.get("page"), source.get("bbox")
            if not isinstance(page, int) or not isinstance(bbox, list) or len(bbox) != 4:
                continue
            identifier = item.get("candidate_id")
            if not isinstance(identifier, str):
                continue
            filename = f"{identifier.rsplit(':', 1)[-1]}-{hashlib.sha256(identifier.encode()).hexdigest()[:10]}.png"
            relative = Path("crops") / filename
            _render(document, page, bbox, output / relative)
            reviews.append({"id": identifier, "deneme_number": item.get("deneme_number"), "page": page,
                            "question_number": question.get("number"), "question": text,
                            "choices": [{"label": choice["label"], "text": choice["text"]} for choice in choices],
                            "crop": relative.as_posix(),
                            "checks": {"pdf_text_matches": None, "choices_complete_and_ordered": None,
                                       "text_only_accessible": None, "scope_appropriate": None},
                            "notes": "", "status": "review_required"})
    if not reviews:
        raise ValueError("İncelenebilir çoktan seçmeli soru bulunamadı")
    return {"schema": SCHEMA, "source_name": source_pdf.name, "source_checksum": checksum,
            "candidate_input_checksum": hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "review_count": len(reviews), "reviews": reviews, "license_status": "local_pilot_usage_verification_required",
            "runtime_enabled": False, "answer_key_accessed": False,
            "notice": "Local review only. PDF crop confirms transcription; no answer key, coaching, or student publication is enabled."}


def _write_html(pack: dict, output: Path) -> None:
    template = json.dumps(pack, ensure_ascii=False).replace("<", "\\u003c")
    page = """<!doctype html><meta charset="utf-8"><title>OGM AYT gerçek soru incelemesi</title><style>
body{font:17px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#102a43}.bar{position:sticky;top:0;background:#fff;padding:.8rem 0;border-bottom:2px solid #486581;z-index:2}button,input,textarea{font:inherit;padding:.5rem}button{cursor:pointer}.card{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.grid>*{min-width:0;border:1px solid #bcccdc;border-radius:8px;padding:1rem}img{max-width:100%;border:1px solid #486581}p{white-space:pre-wrap;line-height:1.45}fieldset{margin:.8rem 0}textarea{width:100%;min-height:5rem;box-sizing:border-box}@media(max-width:560px){.grid{grid-template-columns:1fr}.bar{position:static}}</style>
<h1>OGM AYT gerçek soru doğrulaması</h1><p>Solda öğrenciye verilecek metin, sağda aynı sorunun orijinal PDF kırpımı bulunur. Bu paket yalnız yerel insan incelemesidir: cevap anahtarı, LLM koçluğu ve öğrenci yayını kapalıdır.</p><p>Önce soruları hızlıca gezebilirsin. Metin ve PDF kırpımı uygunsa <strong>Bu sorunun tümünü evetle</strong> kullan; hata varsa ilgili kontrolü <strong>Hayır</strong> yapıp not yaz. Tamamlanmış dosya yalnız tüm sorular karar aldığında indirilebilir.</p><div class="bar"><label>İncelemeci <input id="reviewer" required></label><button id="prev">Önceki</button><button id="next">Sonraki</button><button onclick="index=Math.max(0,index-1);render()">Serbest geri</button><button onclick="index=Math.min(state.reviews.length-1,index+1);render()">Serbest ileri</button><button onclick="const r=state.reviews[index];keys.forEach(key=>r.checks[key]=true);r.notes='';r.status='human_reviewed';render()">Bu sorunun tümünü evetle</button><button id="save">Ara kaydı indir</button><button id="done">Tamamlanmış incelemeyi indir</button><label>Devam dosyası <input id="upload" type="file" accept="application/json"></label><span id="progress"></span></div><main id="main"></main><script>
const template=__TEMPLATE__;let state=structuredClone(template),index=0;const keys=['pdf_text_matches','choices_complete_and_ordered','text_only_accessible','scope_appropriate'];const labels={pdf_text_matches:'1. Soldaki soru metni PDF kırpımıyla birebir eşleşiyor mu?',choices_complete_and_ordered:'2. A–E şıkları eksiksiz ve aynı sırada mı?',text_only_accessible:'3. Soru görsel, tablo, harita veya şema olmadan çözülebilir mi?',scope_appropriate:'4. Bu soru AYT Tarih yerel pilot kapsamına uygun mu?'};const e=(t,x)=>{const n=document.createElement(t);if(x)n.textContent=x;return n};function complete(r){return keys.every(k=>typeof r.checks[k]==='boolean')&&(!keys.some(k=>r.checks[k]===false)||r.notes.trim().length>=12)}function render(){const r=state.reviews[index],main=document.querySelector('#main');main.replaceChildren();const card=e('article');card.className='card';card.append(e('h2',`Deneme ${r.deneme_number} · Soru ${r.question_number} · ${index+1}/${state.reviews.length}`));const grid=e('div');grid.className='grid';const text=e('section');text.append(e('h3','Öğrencinin çözeceği metin'),e('p',r.question));const choices=e('ol');choices.type='A';r.choices.forEach(c=>choices.append(e('li',c.text)));text.append(choices);const pdf=e('section');pdf.append(e('h3','Orijinal deneme PDF kırpımı'));const image=document.createElement('img');image.src=r.crop;image.alt='Aynı deneme sorusunun PDF kırpımı';pdf.append(image);grid.append(text,pdf);card.append(grid);const noteLabel=e('label','Hata notu — yalnız Hayır seçtiysen zorunlu');const note=e('textarea');note.value=r.notes||'';note.oninput=()=>{r.notes=note.value;update()};noteLabel.append(note);card.append(noteLabel);keys.forEach(key=>{const fs=e('fieldset');fs.append(e('legend',labels[key]));[['Evet',true],['Hayır',false]].forEach(([label,value])=>{const l=e('label'),i=document.createElement('input');i.type='radio';i.name=key;i.checked=r.checks[key]===value;i.onchange=()=>{r.checks[key]=value;update();if(value===false)note.focus()};l.append(i,document.createTextNode(` ${label}`));fs.append(l)});card.append(fs)});main.append(card);update()}function update(){const r=state.reviews[index],no=keys.some(k=>r.checks[k]===false);if(complete(r))r.status=no?'review_required':'human_reviewed';document.querySelector('#progress').textContent=`${state.reviews.filter(complete).length}/${state.reviews.length} tamamlandı`}function move(d){if(!complete(state.reviews[index]))return alert('Dört kontrolü tamamla; Hayır varsa not yaz.');index=Math.max(0,Math.min(state.reviews.length-1,index+d));render()}function download(final){if(final&&!state.reviews.every(complete))return alert('Önce tüm kayıtları tamamla.');state.reviewer=document.querySelector('#reviewer').value.trim();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(state,null,2)],{type:'application/json'}));a.download=final?'ogm-ayt-gercek-soru-incelemesi.json':'ogm-ayt-inceleme-ara-kaydi.json';a.click();URL.revokeObjectURL(a.href)}document.querySelector('#prev').onclick=()=>move(-1);document.querySelector('#next').onclick=()=>move(1);document.querySelector('#save').onclick=()=>download(false);document.querySelector('#done').onclick=()=>download(true);document.querySelector('#upload').onchange=async ev=>{const f=ev.target.files[0];if(!f)return;try{const x=JSON.parse(await f.text());if(x.schema!==template.schema||x.source_checksum!==template.source_checksum||x.reviews.length!==template.reviews.length)throw Error();state=x;document.querySelector('#reviewer').value=x.reviewer||'';render()}catch{alert('Bu inceleme paketiyle eşleşmeyen dosya reddedildi.')}};render();</script>"""
    (output / "index.html").write_text(page.replace("__TEMPLATE__", template), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.candidate.read_text(encoding="utf-8")), args.source_pdf, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, args.output)
    print(json.dumps({"review_count": result["review_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
