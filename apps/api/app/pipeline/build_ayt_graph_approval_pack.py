"""Render a private, answer-free PDF crop pack for graph approval."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render(document: pymupdf.Document, page: int, bbox: list[float], target: Path) -> None:
    if not isinstance(page, int) or page < 1 or page > len(document):
        raise ValueError("Geçersiz PDF sayfası")
    clip = pymupdf.Rect(bbox)
    clip &= document[page - 1].rect
    if clip.is_empty or clip.is_infinite:
        raise ValueError("Geçersiz PDF koordinatı")
    target.parent.mkdir(parents=True, exist_ok=True)
    document[page - 1].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), clip=clip, alpha=False).save(target)


def build(corpus: dict, source_root: Path, output: Path, *, limit: int | None = None) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Corpus şeması geçersiz")
    documents: dict[str, pymupdf.Document] = {}
    rows = []
    try:
        for book in corpus.get("books", []):
            source = source_root / str(book.get("source_name", ""))
            checksum = str(book.get("source_checksum", ""))
            if not source.is_file() or _checksum(source) != checksum:
                raise ValueError("Kaynak PDF checksum eşleşmiyor")
            documents[checksum] = pymupdf.open(source)
            for chunk in book.get("index", {}).get("chunks", []):
                if limit is not None and len(rows) >= limit:
                    break
                crop = f"crops/{checksum[:12]}-{chunk['id']}.png"
                _render(documents[checksum], int(chunk["page"]), chunk["bbox"], output / crop)
                rows.append({"source_checksum": checksum, "source_name": book["source_name"],
                             "chunk_id": str(chunk["id"]), "section_id": chunk.get("section_id"),
                             "section_title": chunk.get("section_title", ""), "page": chunk["page"],
                             "bbox": chunk["bbox"], "text": chunk.get("text", ""), "crop": crop,
                             "decision": "pending"})
            if limit is not None and len(rows) >= limit:
                break
    finally:
        for document in documents.values():
            document.close()
    manifest = {"schema": "ayt-graph-teacher-approval-pack-v1",
                "corpus_checksum": corpus["corpus_checksum"], "review_count": len(rows),
                "reviews": rows,
                "notice": "Private PDF crop review aid. This pack does not approve graph evidence."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    blocks = []
    for index, row in enumerate(rows):
        blocks.append(
            f'<section data-index="{index}"><h2>{html.escape(row["chunk_id"])} · s. {row["page"]} · '
            f'{html.escape(row["section_title"])}</h2><p>{html.escape(row["text"])}</p>'
            f'<img src="{html.escape(row["crop"])}" alt="PDF kanıt kesiti">'
            '<label>Karar <select class="decision"><option>pending</option>'
            '<option>approved_for_runtime</option><option>rejected</option></select></label>'
            '<label>PDF kesiti kontrol edildi <input class="crop" type="checkbox"></label>'
            '<label>Kalite kontrol edildi <input class="quality" type="checkbox"></label>'
            '<label>Birebir alıntı <textarea class="quote" rows="3"></textarea></label></section>')
    rows_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    (output / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>AYT grafik onay paketi</title>"
        "<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto}section{border:1px solid #9fb3c8;padding:1rem;margin:1rem 0;border-radius:10px}img{max-width:100%;border:1px solid #bcccdc}label{display:block;margin:.6rem 0}textarea{display:block;width:100%;min-height:4rem}</style>"
        "<h1>AYT bilgi grafiği PDF onay paketi</h1>"
        "<p>Her kesiti kaynak PDF ile karşılaştırın. Onaylanacak parçayı seçip alıntıyı yazın.</p>"
        '<label>Öğretmen kimliği <input id="reviewer" required></label>'
        '<button type="button" id="export">Onay manifestini indir</button>'
        + "".join(blocks)
        + f'''<script>
const rows={rows_json};
document.getElementById("export").onclick=()=>{{
 const reviewer=document.getElementById("reviewer").value.trim();
 if(!reviewer){{alert("Öğretmen kimliği gerekli");return;}}
 const approvals=[];
 document.querySelectorAll("section[data-index]").forEach((section,index)=>{{
  const decision=section.querySelector(".decision").value;
  if(decision!=="approved_for_runtime") return;
  const quote=section.querySelector(".quote").value.trim();
  if(!quote || !section.querySelector(".crop").checked || !section.querySelector(".quality").checked){{
   throw new Error("Onaylanan her parçada alıntı ve iki kontrol işareti zorunlu");
  }}
  const row=rows[index]; approvals.push({{source_checksum:row.source_checksum,chunk_id:row.chunk_id,
   page:row.page,bbox:row.bbox,decision,quote,quote_sha256:"",pdf_crop_checked:true,quality_checked:true}});
 }});
 const value={{schema:"ayt-teacher-graph-approval-v1",corpus_checksum:{json.dumps(corpus["corpus_checksum"])},
  reviewer_id:reviewer,reviewer_kind:"human_history_teacher",is_human_teacher_approval:true,
  answer_key_accessed:false,worked_explanation_accessed:false,qlora_enabled:false,approvals}};
 const blob=new Blob([JSON.stringify(value,null,2)],{{type:"application/json"}});
 const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="ayt-graph-teacher-approval-manifest-v1.json";link.click();URL.revokeObjectURL(link.href);
}};
</script>''', encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = build(json.loads(args.corpus.read_text(encoding="utf-8")), args.source_root,
                     args.output, limit=args.limit)
    print(json.dumps({"schema": manifest["schema"], "review_count": manifest["review_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
