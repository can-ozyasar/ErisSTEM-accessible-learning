"""Prepare a private, human PDF-crop review queue for the 120 AYT candidates.

This tool is deliberately a one-way gate: it can create review work, never a
published exam pack.  Source PDFs and the rendered crops stay in a local,
ignored directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

SCHEMA = "ayt-history-human-pdf-crop-review-template-v1"


def _canonical_checksum(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pdfs_by_checksum(source_root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in source_root.glob("*.pdf"):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum in paths:
            raise ValueError("Aynı checksum taşıyan birden fazla yerel PDF var")
        paths[checksum] = path
    return paths


def build(candidate_pack: dict, source_catalog: dict, source_root: Path, output: Path) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün 120 soruluk aday paketi gerekli")
    questions = candidate_pack.get("questions")
    if not isinstance(questions, list) or len(questions) != 120:
        raise ValueError("İnsan inceleme kuyruğu için tam 120 aday gerekli")
    # ``candidate_checksum`` identifies the pre-publication selection input;
    # its source rows may have had a different workflow status.  Do not
    # rewrite that provenance into a different value.  Instead bind this
    # review queue to both the upstream selection checksum and the exact
    # candidate rows it displays.
    candidate_checksum = candidate_pack.get("candidate_checksum")
    if not isinstance(candidate_checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate_checksum):
        raise ValueError("Aday paketi seçim checksum'ı geçersiz")
    question_set_checksum = _canonical_checksum(questions)
    if source_catalog.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    sources = {item.get("source_checksum"): item for item in source_catalog.get("sources", [])}
    if not sources:
        raise ValueError("MEB kaynak kataloğunda en az bir kaynak gerekli")
    local_pdfs = _pdfs_by_checksum(source_root)
    output.mkdir(parents=True, exist_ok=True)
    crop_dir = output / "crops"
    crop_dir.mkdir(exist_ok=True)
    documents: dict[str, pymupdf.Document] = {}
    reviews = []
    try:
        for question in questions:
            evidence = question.get("source_evidence", {})
            checksum = evidence.get("source_checksum")
            source = sources.get(checksum)
            if (question.get("status") != "source_crop_validation_required"
                    or question.get("runtime_enabled") is not False
                    or source is None or source.get("id") != evidence.get("source_id")
                    or checksum not in local_pdfs):
                raise ValueError("Her aday, yayımlanmamış durumda yerel ve kataloglanmış MEB kaynağına bağlı olmalı")
            document = documents.setdefault(checksum, pymupdf.open(local_pdfs[checksum]))
            page_number, bbox = evidence.get("page"), evidence.get("bbox")
            if not isinstance(page_number, int) or not 1 <= page_number <= len(document):
                raise ValueError("Kanıt sayfası yerel PDF sınırları dışında")
            rect = pymupdf.Rect(bbox)
            page = document[page_number - 1]
            if rect.is_empty or not page.rect.contains(rect):
                raise ValueError("Kanıt bbox değeri yerel PDF sayfası dışında")
            crop = crop_dir / f"{question['id']}-{checksum[:12]}-p{page_number}.png"
            clip = rect + (-18, -18, 18, 18)
            clip &= page.rect
            page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=clip, alpha=False).save(crop)
            reviews.append({
                "id": question["id"], "status": "review_required", "question_checksum": _canonical_checksum(question),
                "source_id": evidence.get("source_id"), "source_checksum": checksum, "page": page_number,
                "bbox": bbox, "crop": (Path("crops") / crop.name).as_posix(),
                "checks": {"question_choices_match": None, "correct_label_grounded": None,
                           "explanation_grounded": None, "spoken_text_checked": None,
                           "text_only_accessible": None},
                "reviewer": None, "reviewed_at": None, "notes": "",
            })
    finally:
        for document in documents.values():
            document.close()
    return {
        "schema": SCHEMA, "candidate_checksum": candidate_checksum,
        "question_set_checksum": question_set_checksum,
        "source_catalog_checksum": _canonical_checksum(source_catalog), "review_count": len(reviews),
        "reviews": reviews, "runtime_enabled": False, "qlora_enabled": False,
        "is_human_teacher_approval": False,
        "notice": "Private human review template only. All entries remain review_required; completing this file does not publish an exam pack.",
    }


def _write_html(result: dict, candidate_pack: dict, output: Path) -> None:
    by_id = {item["id"]: item for item in candidate_pack["questions"]}
    display = [{"id": review["id"], "question": by_id[review["id"]]["question"],
                "spoken_question": by_id[review["id"]]["spoken_question"], "choices": by_id[review["id"]]["choices"],
                "correct_label": by_id[review["id"]]["correct_label"], "explanation": by_id[review["id"]]["explanation"],
                "source_quote": by_id[review["id"]]["source_evidence"]["quote"]}
               for review in result["reviews"]]
    template_json = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c")
    display_json = json.dumps(display, ensure_ascii=False).replace("<", "\\u003c")
    html = """<!doctype html><meta charset="utf-8"><title>AYT Tarih soru doğrulama</title>
<style>
body{font:17px system-ui;max-width:1180px;margin:2rem auto;padding:0 1rem;color:#102a43;background:#f7fafc}header,.card{border:1px solid #9fb3c8;border-radius:12px;padding:1.2rem;margin:1rem 0;background:#fff}.bar,.audio-actions{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap}.bar{position:sticky;top:0;background:#fff;padding:.8rem 0;border-bottom:2px solid #486581;z-index:1}button,input,textarea{font:inherit;padding:.5rem}button{cursor:pointer}.muted{color:#486581}.comparison{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.9fr);gap:1.2rem;align-items:start}.panel{min-width:0;border:1px solid #bcccdc;border-radius:10px;padding:1rem;background:#fff}.source-panel{background:#f0f4f8}.source-crop{display:block;width:100%;max-height:650px;object-fit:contain;border:1px solid #486581;background:#fff}.source-link{display:inline-block;margin-top:.7rem}.speech-preview{white-space:pre-wrap;padding:.8rem;background:#e6fffa;border-left:5px solid #0b6e4f;line-height:1.5}blockquote.source-quote{white-space:pre-wrap;margin:.8rem 0;padding:1rem;border-left:5px solid #486581;background:#f0f4f8;line-height:1.55}fieldset{margin:.8rem 0;padding:.8rem;border:1px solid #bcccdc;border-radius:8px}legend{font-weight:700}label{display:block;margin:.45rem 0}textarea{width:100%;min-height:5rem;box-sizing:border-box}.ok{color:#0b6e4f}.warn{color:#9c2c2c}details{margin:.8rem 0}@media(max-width:560px){.comparison{grid-template-columns:1fr}.bar{position:static}}
</style>
<header><h1>AYT Tarih soru doğrulaması</h1><p><strong>Bu öğrenci denemesi değildir.</strong> Solda öğrenciye gidecek özgün soru, şıklar ve sesletim metni; sağda bu soru için seçilmiş MEB PDF kesiti bulunur. Kitaptan ayrıca soru araman gerekmez.</p><p>Özgün soru MEB kitabından aynen kopyalanmış değildir; kaynak bilgisi temel alınarak hazırlanmıştır. Soru kökü “Kaynağa göre” deyip öğrencinin önünde kaynak yoksa, ilk kontrolde <strong>Hayır</strong> seçip not yaz.</p><p>Bir kaydı tamamlamak için alttaki beş kontrolün tümünü işaretle. Hata gördüğünde <strong>Hayır</strong> ve kısa not yaz; kayıt yayınlanmaz.</p></header>
<div class="bar"><label>İncelemeci adı <input id="reviewer" autocomplete="name" required></label><button id="prev" type="button">Önceki</button><button id="next" type="button">Sonraki</button><button id="save" type="button">Ara kaydı indir</button><button id="download" type="button">Tamamlanmış incelemeyi indir</button><label>Devam dosyası yükle <input id="upload" type="file" accept="application/json"></label><span id="progress"></span></div><main id="main"></main>
<script>
const template=__TEMPLATE__, display=__DISPLAY__;
let state=structuredClone(template),index=0;
const checks=['question_choices_match','correct_label_grounded','explanation_grounded','spoken_text_checked','text_only_accessible'];
const labels={question_choices_match:'1. Öğrenci sorusu ve şıkları, sağdaki kaynak bilgiden doğru türetilmiş mi?',correct_label_grounded:'2. Kaydedilmiş doğru şık, kaynakta açıkça var mı?',explanation_grounded:'3. Açıklama yalnız kaynak metne dayanıyor mu?',spoken_text_checked:'4. Aşağıdaki sesletim metni soru anlamını aynen koruyor mu?',text_only_accessible:'5. Öğrenci bu soruyu görsel veya tablo olmadan çözebilir mi?'};
const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n};
let activeAudio=null,activeUrl=null;
function stop(){if(activeAudio){activeAudio.pause();activeAudio=null}if(activeUrl){URL.revokeObjectURL(activeUrl);activeUrl=null}}
async function speak(candidateId,status){stop();status.textContent='Fine-tuned V5 kaydı aranıyor…';try{const response=await fetch(`./audio/${encodeURIComponent(candidateId)}`,{method:'POST',headers:{'X-Role':'reviewer'}});if(!response.ok)throw Error(String(response.status));activeUrl=URL.createObjectURL(await response.blob());activeAudio=new Audio(activeUrl);activeAudio.onended=()=>{stop();status.textContent='V5 seslendirmesi tamamlandı.'};activeAudio.onerror=()=>{stop();status.textContent='Fine-tuned V5 kaydı oynatılamadı.'};await activeAudio.play();status.textContent='Fine-tuned V5 Türkçe sesi okunuyor.'}catch{stop();status.textContent='Bu soru için doğrulanmış fine-tuned V5 kaydı yok. Piper veya Chrome sesi kullanılmadı.'}}
function render(){stop();const r=state.reviews[index],q=display[index],root=document.querySelector('#main');root.replaceChildren();const card=el('section');card.className='card';card.append(el('p',`${index+1}. kayıt · ${r.id}`));const comparison=el('div');comparison.className='comparison';const student=el('section');student.className='panel';student.append(el('h2','Öğrenciye gösterilecek soru'),el('p',q.question));const list=el('ol');list.type='A';q.choices.forEach(x=>list.append(el('li',x)));student.append(list);student.append(el('h3','Öğrenciye dinletilecek sesletim metni'));const speech=el('p',q.spoken_question);speech.className='speech-preview';student.append(speech);const audio=el('div');audio.className='audio-actions';const play=el('button','Fine-tuned V5 kaydını dinle');play.type='button';const audioStatus=el('span','');audioStatus.className='muted';play.onclick=()=>void speak(r.id,audioStatus);const halt=el('button','Sesi durdur');halt.type='button';halt.onclick=()=>{stop();audioStatus.textContent='Ses durduruldu.'};audio.append(play,halt,audioStatus);student.append(audio);const sourcePanel=el('section');sourcePanel.className='panel source-panel';sourcePanel.append(el('h2','Seçilen MEB kaynak kesiti'),el('p',`Kaynak: ${r.source_id} · sayfa ${r.page}`));const image=document.createElement('img');image.src=r.crop;image.alt='Bu soru için seçilen MEB kaynak metni kesiti';image.className='source-crop';sourcePanel.append(image);const sourceLink=document.createElement('a');sourceLink.href=r.crop;sourceLink.target='_blank';sourceLink.rel='noreferrer';sourceLink.className='source-link';sourceLink.textContent='Kesiti yeni sekmede büyüt';sourcePanel.append(sourceLink);comparison.append(student,sourcePanel);card.append(comparison);card.append(el('h2','Kaynak metnin yazı hâli — öğrenciye gösterilmez'));const quote=el('blockquote',q.source_quote);quote.className='source-quote';card.append(quote);const d=document.createElement('details');d.append(el('summary','Doğru şık ve açıklamayı incele — öğrenciye gösterilmez'),el('p',`Kaydedilmiş doğru cevap: ${q.correct_label}`),el('p',`Açıklama: ${q.explanation}`));card.append(d);const noteLabel=el('label','Hata notu — yalnız “Hayır” seçtiysen zorunlu');const note=el('textarea');note.value=r.notes||'';note.placeholder='Örnek: Öğrenci kaynak metni görmediği hâlde soru kökü “Kaynağa göre” diye başlıyor.';note.addEventListener('input',()=>{r.notes=note.value;updateStatus()});noteLabel.append(note);card.append(noteLabel);const approve=el('button','Bu kaydın beş kontrolüne Evet — PDF kesitini inceledim');approve.type='button';approve.onclick=()=>{if(!confirm('Bu işlem yalnız ekrandaki soru, şıklar, sesletim ve PDF kesitini gerçekten kontrol ettiysen kullanılmalı. Beş kontrol Evet olarak işaretlenecek.'))return;checks.forEach(key=>r.checks[key]=true);r.notes='';render()};card.append(approve);checks.forEach(key=>{const fs=document.createElement('fieldset');fs.append(el('legend',labels[key]));for(const [text,val] of [['Evet',true],['Hayır',false]]){const label=el('label'),input=document.createElement('input');input.type='radio';input.name=key;input.value=String(val);input.checked=r.checks[key]===val;input.addEventListener('change',()=>{r.checks[key]=val;updateStatus();if(val===false){note.focus();note.scrollIntoView({block:'center'})}});label.append(input,document.createTextNode(` ${text}`));fs.append(label)}card.append(fs)});root.append(card);updateStatus()}
function complete(r){return checks.every(k=>typeof r.checks[k]==='boolean')&&(!checks.some(k=>r.checks[k]===false)||r.notes.trim().length>=12)}
function updateStatus(){const r=state.reviews[index],done=state.reviews.filter(complete).length,no=checks.some(k=>r.checks[k]===false);if(complete(r))r.status=no?'review_required':'human_approved';document.querySelector('#progress').textContent=` ${done}/${state.reviews.length} tamamlandı${no?' · Bu kayıt inceleme gerektiriyor':''}`}
function move(step){if(!complete(state.reviews[index])){alert('Bu kayıtta beş kontrolü tamamla; “Hayır” varsa en az 12 karakter not yaz.');return}index=Math.max(0,Math.min(state.reviews.length-1,index+step));render()}
function download(final){const name=document.querySelector('#reviewer').value.trim();if(!name){alert('İncelemeci adını yaz.');return}if(final&&!state.reviews.every(complete)){alert('Tüm kayıtları tamamla. Şimdilik Ara kaydı indir düğmesini kullanabilirsin.');return}const now=new Date().toISOString();state.reviewer=name;state.reviews.forEach(r=>{if(complete(r)){r.reviewer=name;r.reviewed_at=now;r.status=checks.some(k=>r.checks[k]===false)?'review_required':'human_approved'}});const a=document.createElement('a'),b=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});a.href=URL.createObjectURL(b);a.download=final?'ayt-tarih-tamamlanmis-insan-incelemesi.json':'ayt-tarih-inceleme-ara-kaydi.json';a.click();URL.revokeObjectURL(a.href)}
document.querySelector('#prev').onclick=()=>move(-1);document.querySelector('#next').onclick=()=>move(1);document.querySelector('#save').onclick=()=>download(false);document.querySelector('#download').onclick=()=>download(true);document.querySelector('#upload').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const x=JSON.parse(await f.text());if(x.schema!==template.schema||x.candidate_checksum!==template.candidate_checksum||!Array.isArray(x.reviews)||x.reviews.length!==template.reviews.length)throw Error();state=x;document.querySelector('#reviewer').value=x.reviewer||x.reviews[0]?.reviewer||'';render()}catch{alert('Bu şablonla eşleşmeyen dosya reddedildi.')}};render();
</script>"""
    (output / "index.html").write_text(
        html.replace("__TEMPLATE__", template_json).replace("__DISPLAY__", display_json), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate_pack = json.loads(args.candidate_pack.read_text(encoding="utf-8"))
    catalog = json.loads(args.source_catalog.read_text(encoding="utf-8"))
    result = build(candidate_pack, catalog, args.source_root, args.output)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, candidate_pack, args.output)
    print(json.dumps({"review_count": result["review_count"], "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
