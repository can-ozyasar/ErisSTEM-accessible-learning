"""Materialize top evidence candidates as checksum-verified PDF crops for review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

SOURCE_FILES = {
    "a7bd70d3ddf7ead61f201b10a35079a2d0f87088f5e61bab830cc33a515335fe": "tarih-9sinif-ders-kitabi_20261006.pdf",
    "153da42644c9ae772a4fa85a722c2e970eff7e04c00b9807256cb1697e09a439": "tarih-10sinif-ders-kitabi_20261013.pdf",
    "8593338d9bc04e0e00480d237e678b942556405dcdf096c30240caf2c07059b3": "tarih-11sinif-ders-kitabi_20260908.pdf",
    "64a392e28af85a936003f25840a7a792ab006ef648ebea7ba34931b9e1421847": "inkilap-12-aday-eba.pdf",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(queue: dict, source_dir: Path, output: Path, per_question: int = 3) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("gerçek soru kanıt kuyruğu gerekli")
    if per_question < 1:
        raise ValueError("soru başına en az bir kesit gerekli")
    documents = {}
    for checksum, name in SOURCE_FILES.items():
        path = source_dir / name
        if not path.is_file() or _sha(path) != checksum:
            raise ValueError(f"MEB kaynak checksum doğrulaması başarısız: {name}")
        documents[checksum] = pymupdf.open(path)
    try:
        output.mkdir(parents=True, exist_ok=True)
        reviewed = []
        for row in queue["proposals"]:
            candidates = []
            for rank, item in enumerate(row["suggestions"][:per_question], 1):
                page = documents[item["source_checksum"]][item["page"] - 1]
                clip = pymupdf.Rect(item["bbox"]) + (-12, -12, 12, 12)
                clip &= page.rect
                name = f'{hashlib.sha256((row["candidate_id"] + item["id"]).encode()).hexdigest()[:20]}.png'
                relative = Path("crops") / name
                if not (output / relative).exists():
                    (output / relative).parent.mkdir(exist_ok=True)
                    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip, alpha=False).save(output / relative)
                candidates.append({**item, "rank": rank, "crop": relative.as_posix(), "verdict": "pending"})
            reviewed.append({"candidate_id": row["candidate_id"], "question_text": row["question_text"],
                             "status": "review_required", "candidates": candidates,
                             "coverage_complete": None, "abstain": None, "notes": ""})
    finally:
        for document in documents.values():
            document.close()
    return {"schema": "ogm-ayt-real-question-evidence-pdf-review-v1", "queue_checksum": hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest(),
            "question_source_checksum": queue["question_source_checksum"], "corpus_checksum": queue["corpus_checksum"],
            "review_count": len(reviewed), "per_question": per_question, "reviews": reviewed,
            "runtime_enabled": False, "notice": "PDF crop review only. Select no runtime evidence without complete claim coverage."}


def _write_html(pack: dict, output: Path) -> None:
    data = json.dumps(pack, ensure_ascii=False).replace("<", "\\u003c")
    html = f'''<!doctype html><meta charset="utf-8"><title>MEB kanıt incelemesi</title><style>body{{font:16px system-ui;max-width:1300px;margin:2rem auto;padding:0 1rem;color:#102a43}}.bar{{position:sticky;top:0;background:#fff;padding:.75rem 0;border-bottom:2px solid #486581;z-index:2}}button,input,textarea{{font:inherit;padding:.45rem;margin:.15rem}}.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem}}.card{{border:1px solid #9fb3c8;border-radius:8px;padding:.7rem}}img{{max-width:100%;border:1px solid #486581}}p{{white-space:pre-wrap;line-height:1.4}}textarea{{width:100%;min-height:4rem;box-sizing:border-box}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}.bar{{position:static}}}}</style>
<h1>MEB kanıt kesiti incelemesi</h1><p>Sorunun çözümü için gerekli tüm iddiaları destekleyen kesitleri seç. Üç kesit birlikte de yetersizse <strong>Kanıt yok / yetersiz</strong> seç. Bu ekran cevap anahtarını göstermez ve öğrenciye içerik yayınlamaz.</p><div class="bar"><button onclick="go(-1)">Önceki</button><button onclick="go(1)">Sonraki</button><button onclick="download(false)">Ara kaydı indir</button><button onclick="download(true)">Tam incelemeyi indir</button><label>Devam dosyası <input id="up" type="file" accept="application/json"></label><span id="p"></span></div><main></main><script>const original={data};let state=structuredClone(original),i=0;function done(r){{return r.abstain===true||(r.coverage_complete===true&&r.candidates.some(x=>x.verdict==='support'))}}function go(n){{i=Math.max(0,Math.min(state.reviews.length-1,i+n));render()}}function render(){{const r=state.reviews[i],m=document.querySelector('main');m.replaceChildren();const h=document.createElement('h2');h.textContent=`${{i+1}}/${{state.reviews.length}}`;m.append(h);const q=document.createElement('p');q.textContent=r.question_text;m.append(q);const g=document.createElement('div');g.className='grid';r.candidates.forEach((c,k)=>{{const a=document.createElement('article');a.className='card';const img=document.createElement('img');img.src=c.crop;img.alt=`MEB kaynak kesiti ${{k+1}}`;a.append(img);const l=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.checked=c.verdict==='support';box.onchange=()=>{{c.verdict=box.checked?'support':'wrong';r.abstain=false;render()}};l.append(box,document.createTextNode(' Bu kesit kanıtı destekliyor'));a.append(l);g.append(a)}});m.append(g);const yes=document.createElement('button');yes.textContent='Seçilen kesitler tam kanıt sağlıyor';yes.onclick=()=>{{r.coverage_complete=true;r.abstain=false;render()}};const no=document.createElement('button');no.textContent='Kanıt yok / yetersiz';no.onclick=()=>{{r.abstain=true;r.coverage_complete=false;r.candidates.forEach(c=>c.verdict='wrong');render()}};m.append(yes,no);const note=document.createElement('textarea');note.placeholder='Not (özellikle yetersiz veya çelişkiliyse)';note.value=r.notes;note.oninput=()=>r.notes=note.value;m.append(note);document.querySelector('#p').textContent=`${{state.reviews.filter(done).length}}/${{state.reviews.length}} karar verildi`}}function download(final){{if(final&&!state.reviews.every(done))return alert('Tüm sorular için kanıt veya yetersiz kararı ver.');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(state,null,2)],{{type:'application/json'}}));a.download=final?'ogm-meb-kanit-incelemesi.json':'ogm-meb-kanit-ara-kaydi.json';a.click();URL.revokeObjectURL(a.href)}}document.querySelector('#up').onchange=async e=>{{try{{const x=JSON.parse(await e.target.files[0].text());if(x.schema!==original.schema||x.queue_checksum!==original.queue_checksum)throw Error();state=x;render()}}catch{{alert('Bu kuyruğa ait olmayan kayıt reddedildi.')}}}};render()</script>'''
    (output / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.queue.read_text(encoding="utf-8")), args.source_dir, args.output)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, args.output)
    print(json.dumps({"reviews": result["review_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
