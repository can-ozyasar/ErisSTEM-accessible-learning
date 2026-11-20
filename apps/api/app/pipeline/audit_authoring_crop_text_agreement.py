"""Audit whether a rendered authoring crop still contains its recorded excerpt."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"\xad\s*", "", text).casefold()
    return re.findall(r"[a-zçğıöşü0-9]+", cleaned)


def build(pack: dict, source_root: Path, *, minimum_recall: float = 0.9) -> dict:
    if pack.get("schema") != "ayt-history-authoring-source-crop-pack-v1":
        raise ValueError("Özgün kaynak crop paketi gerekli")
    if not isinstance(pack.get("queue_checksum"), str) or len(pack["queue_checksum"]) != 64:
        raise ValueError("Kaynak kuyruğu checksum'ı gerekli")
    if not 0 < minimum_recall <= 1:
        raise ValueError("Minimum alıntı geri çağırımı geçersiz")
    files = { _checksum(path): path for path in source_root.glob("*.pdf") }
    documents = {}
    rows = []
    try:
        for row in pack.get("reviews", []):
            checksum = row["source_checksum"]
            path = files.get(checksum)
            if path is None:
                raise ValueError("Crop için checksum bağlı PDF bulunamadı")
            document = documents.setdefault(checksum, pymupdf.open(path))
            page = document[row["page"] - 1]
            clip = pymupdf.Rect(row["bbox"]) + (-2, -2, 2, 2)
            crop_text = " ".join(word[4] for word in page.get_text("words") if pymupdf.Rect(word[:4]).intersects(clip))
            quote_tokens, crop_tokens = _tokens(row["quote"]), set(_tokens(crop_text))
            recall = sum(token in crop_tokens for token in quote_tokens) / len(quote_tokens) if quote_tokens else 0
            rows.append({"id": row["id"], "source_checksum": checksum, "page": row["page"],
                         "quote_token_count": len(quote_tokens), "quote_token_recall": round(recall, 4),
                         "pdf_text_bbox_agreement": recall >= minimum_recall,
                         "pdf_crop_checked": False, "quality_checked": False})
    finally:
        for document in documents.values():
            document.close()
    return {"schema": "ayt-history-authoring-crop-text-audit-v1", "corpus_checksum": pack["corpus_checksum"],
            "queue_checksum": pack["queue_checksum"],
            "minimum_quote_token_recall": minimum_recall, "records": rows,
            "summary": {"reviewed": len(rows), "agreement_count": sum(row["pdf_text_bbox_agreement"] for row in rows),
                        "held_out": sum(not row["pdf_text_bbox_agreement"] for row in rows)},
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Automated PDF text/bbox agreement only; it is not visual crop or pedagogical approval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-recall", type=float, default=0.9)
    args = parser.parse_args()
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    result = build(pack, args.source_root, minimum_recall=args.minimum_recall)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
