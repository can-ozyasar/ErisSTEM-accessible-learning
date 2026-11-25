"""Render a rank-blind, local PDF-crop review template for frozen retrieval.

It creates work for an independent reviewer.  It never fabricates a review,
does not expose answer keys/reference atoms, and cannot enable runtime RAG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

SCHEMA = "ayt-history-rank-blind-pdf-retrieval-review-template-v1"
BASELINE_SCHEMA = "ayt-history-provisional-atom-bm25-baseline-v1"


def _checksum(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source_files(catalog: dict, source_root: Path) -> dict[str, Path]:
    if catalog.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    root = source_root.resolve()
    result: dict[str, Path] = {}
    for source in catalog.get("sources", []):
        checksum, relative = source.get("source_checksum"), Path(str(source.get("relative_path", "")))
        path = (root / relative).resolve()
        if (not isinstance(checksum, str) or relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root)
                or not path.is_file()):
            raise ValueError("Katalogda güvenli yerel PDF yolu gerekli")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError("Yerel PDF checksum'ı kaynak kataloğuyla uyuşmuyor")
        if checksum in result:
            raise ValueError("Kaynak checksum'ı benzersiz olmalı")
        result[checksum] = path
    return result


def _atoms(corpus: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for book in corpus.get("books", []):
        checksum = book.get("source_checksum")
        for atom in book.get("index", {}).get("evidence_atoms", []):
            atom_id = atom.get("id")
            if not isinstance(checksum, str) or not isinstance(atom_id, str) or not isinstance(atom.get("text"), str):
                raise TypeError("Atom metni ve kaynak kimliği gerekli")
            key = f"{checksum}:{atom_id}"
            row = {"source_checksum": checksum, "atom_id": atom_id, "page": atom.get("page"),
                   "bbox": atom.get("bbox"), "text": atom["text"]}
            if key in result and result[key] != row:
                raise ValueError("Aynı atom kimliği farklı içerikle yineleniyor")
            result[key] = row
    return result


def _blind_order(case_id: str, cards: list[dict]) -> list[dict]:
    # The reviewer should not learn the retriever rank.  Stable pseudorandom
    # ordering keeps the reviewed file reproducible and auditable.
    return sorted(cards, key=lambda card: hashlib.sha256(f"{case_id}:{card['source_key']}".encode()).hexdigest())


def build(candidate_pack: dict, split: dict, corpus: dict, baseline: dict, source_catalog: dict,
          source_root: Path, output: Path) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1" or len(candidate_pack.get("questions", [])) != 120:
        raise ValueError("Tam 120 soruluk özgün aday paketi gerekli")
    if split.get("schema") != "ayt-history-candidate-split-v1" or split.get("candidate_checksum") != candidate_pack.get("candidate_checksum"):
        raise ValueError("Aday paketiyle eşleşen dondurulmuş split gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or corpus.get("corpus_checksum") != candidate_pack.get("corpus_checksum"):
        raise ValueError("Aday paketiyle eşleşen atom corpus'u gerekli")
    if (baseline.get("schema") != BASELINE_SCHEMA or baseline.get("candidate_checksum") != candidate_pack.get("candidate_checksum")
            or baseline.get("corpus_checksum") != corpus.get("corpus_checksum") or baseline.get("k") != 3):
        raise ValueError("Eşleşen top-3 BM25 baseline gerekli")
    retrieval_ids = {row.get("id") for row in split.get("records", []) if row.get("split") == "retrieval_test"}
    cases = {row.get("id"): row for row in baseline.get("cases", [])}
    questions = {row.get("id"): row for row in candidate_pack["questions"]}
    if len(retrieval_ids) != 24 or set(cases) != retrieval_ids or not retrieval_ids <= set(questions):
        raise ValueError("Tam 24 kilitli retrieval vakası gerekli")
    files, atoms = _source_files(source_catalog, source_root), _atoms(corpus)
    output.mkdir(parents=True, exist_ok=True)
    crop_dir = output / "crops"
    crop_dir.mkdir(exist_ok=True)
    documents: dict[str, pymupdf.Document] = {}
    rendered: dict[str, str] = {}
    reviews = []
    try:
        for case_id in sorted(retrieval_ids):
            cards = []
            atom_ids = cases[case_id].get("retrieved_atom_ids")
            if not isinstance(atom_ids, list) or len(atom_ids) != 3 or len(set(atom_ids)) != 3:
                raise ValueError("Her baseline vakası üç tekil atom taşımalı")
            for source_key in atom_ids:
                atom = atoms.get(source_key)
                if atom is None or atom["source_checksum"] not in files:
                    raise ValueError("Baseline atomunun yerel, checksum doğrulanmış PDF'si gerekli")
                page_number, bbox = atom["page"], atom["bbox"]
                if not isinstance(page_number, int) or not isinstance(bbox, list):
                    raise TypeError("Atom sayfası ve bbox değeri gerekli")
                if source_key not in rendered:
                    document = documents.setdefault(atom["source_checksum"], pymupdf.open(files[atom["source_checksum"]]))
                    if not 1 <= page_number <= len(document):
                        raise ValueError("Atom sayfası PDF sınırları dışında")
                    page, rect = document[page_number - 1], pymupdf.Rect(bbox)
                    if rect.is_empty or not page.rect.contains(rect):
                        raise ValueError("Atom bbox değeri PDF sayfası dışında")
                    clip = rect + (-18, -18, 18, 18)
                    clip &= page.rect
                    filename = f"{atom['source_checksum'][:12]}-{atom['atom_id']}.png"
                    page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=clip, alpha=False).save(crop_dir / filename)
                    rendered[source_key] = (Path("crops") / filename).as_posix()
                cards.append({"source_key": source_key, "source_checksum": atom["source_checksum"], "atom_id": atom["atom_id"],
                              "page": page_number, "bbox": bbox, "crop": rendered[source_key], "excerpt": atom["text"],
                              "decision": None, "rationale": ""})
            question = questions[case_id]
            reviews.append({"id": case_id, "question": question["question"], "choices": question["choices"],
                            "status": "review_required", "cards": _blind_order(case_id, cards),
                            "case_decision": None, "reviewer": None, "reviewed_at": None, "notes": ""})
    finally:
        for document in documents.values():
            document.close()
    return {"schema": SCHEMA, "candidate_checksum": candidate_pack["candidate_checksum"],
            "corpus_checksum": corpus["corpus_checksum"], "split_checksum": baseline.get("split_checksum"),
            "source_catalog_checksum": _checksum(source_catalog), "review_count": len(reviews), "reviews": reviews,
            "reviewer_instructions": {"card_decision": ["relevant", "wrong", "insufficient"],
                                        "case_decision": ["sufficient", "insufficient", "review_required"],
                                        "rule": "Her kart, PDF kesitinin soru ve şıkları ayırt etmeye somut katkısına göre etiketlenir. Doğru cevap veya BM25 sırası görülmeden karar verilir."},
            "answer_key_accessed": False, "worked_explanation_accessed": False, "reference_atom_accessed": False,
            "is_human_teacher_approval": False, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Rank-blind local human PDF review template. Blank decisions are not labels; completing this template alone never publishes content or enables runtime retrieval."}


def _write_html(result: dict, output: Path) -> None:
    # Embed only the answer-blind template. Escaping ``<`` prevents a source
    # excerpt from terminating the script block in this local static file.
    template_json = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c")
    (output / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>AYT Tarih kör PDF kanıt incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem}article,section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}img{max-width:100%;border:1px solid #bcccdc}label{display:block;margin:.55rem 0}textarea{display:block;width:100%;min-height:5rem}button,input,select{font:inherit;padding:.4rem}.bar{position:sticky;top:0;background:#fff;padding:1rem 0;border-bottom:2px solid #486581}</style>"
        "<h1>AYT Tarih: sıralama-kör PDF kanıt incelemesi</h1><p>Doğru cevap, adayın referans atomu ve BM25 sırası gösterilmez. Kararlar yalnız bu cihazda işlenir; tamamlayınca JSON indirip doğrulayıcıdan geçirin.</p>"
        "<div class=bar><label>İncelemeci <input id=reviewer required></label><button id=download>Completed JSON indir</button> <label>Devam dosyası yükle <input id=upload type=file accept=application/json></label><span id=status></span></div><main id=reviews></main>"
        f"<script>const template={template_json};let state=structuredClone(template);const el=(tag,text)=>{{const n=document.createElement(tag);if(text)n.textContent=text;return n}};"
        "function bind(v,fn){v.addEventListener('input',fn);v.addEventListener('change',fn)}"
        "function render(){const root=document.querySelector('#reviews');root.replaceChildren();let done=0;state.reviews.forEach((r,i)=>{const a=el('article');a.append(el('h2',`${i+1}. ${r.id}`),el('p',r.question));const ol=el('ol');ol.type='A';r.choices.forEach(x=>ol.append(el('li',x)));a.append(ol);r.cards.forEach((c,j)=>{const s=el('section');s.append(el('h3',`Kanıt kartı ${j+1}`),el('p',c.excerpt));const img=document.createElement('img');img.src=c.crop;img.alt='Yerel MEB PDF kanıt kırpımı';s.append(img);const select=document.createElement('select');select.append(new Option('Kart kararı seçin',''));['relevant','wrong','insufficient'].forEach(x=>select.append(new Option(x,x)));select.value=c.decision||'';bind(select,()=>{c.decision=select.value||null;update()});const label=el('label','Kart kararı ');label.append(select);const why=document.createElement('textarea');why.value=c.rationale||'';why.placeholder='PDF kesitine dayalı gerekçe (en az 12 karakter)';bind(why,()=>{c.rationale=why.value;update()});s.append(label,why);a.append(s)});const caseSelect=document.createElement('select');caseSelect.append(new Option('Soru kararı seçin',''));['sufficient','insufficient','review_required'].forEach(x=>caseSelect.append(new Option(x,x)));caseSelect.value=r.case_decision||'';bind(caseSelect,()=>{r.case_decision=caseSelect.value||null;update()});const caseLabel=el('label','Soru düzeyi karar ');caseLabel.append(caseSelect);a.append(caseLabel);const note=document.createElement('textarea');note.value=r.notes||'';note.placeholder='İsteğe bağlı not';bind(note,()=>{r.notes=note.value});a.append(note);if(r.cards.every(c=>c.decision&&c.rationale.trim().length>=12)&&r.case_decision)done++;root.append(a)});document.querySelector('#status').textContent=` ${done}/${state.reviews.length} soru tamamlandı`;}"
        "function update(){state.reviewer=document.querySelector('#reviewer').value||null;state.reviews.forEach(r=>{r.reviewer=state.reviewer;r.reviewed_at=state.reviewer?new Date().toISOString():null});render()}"
        "document.querySelector('#reviewer').addEventListener('input',update);document.querySelector('#download').addEventListener('click',()=>{const reviewer=document.querySelector('#reviewer').value.trim();if(!reviewer){alert('İncelemeci adı gerekli.');return}state.reviewer=reviewer;state.reviews.forEach(r=>{r.reviewer=reviewer;r.reviewed_at=new Date().toISOString()});const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='completed-manifest.json';a.click();URL.revokeObjectURL(a.href)});"
        "document.querySelector('#upload').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;try{const x=JSON.parse(await f.text());if(x.schema!==template.schema||x.candidate_checksum!==template.candidate_checksum||x.corpus_checksum!==template.corpus_checksum||!Array.isArray(x.reviews)||x.reviews.length!==template.reviews.length)throw Error();state=x;document.querySelector('#reviewer').value=x.reviewer||x.reviews[0]?.reviewer||'';render()}catch{alert('Bu inceleme şablonuyla eşleşmeyen dosya reddedildi.')}});render();</script>", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate_pack), load(args.split), load(args.corpus), load(args.baseline),
                   load(args.source_catalog), args.source_root, args.output)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, args.output)
    print(json.dumps({"review_count": result["review_count"], "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
