"""Promote explicit human PDF reviews into the runtime-safe graph corpus.

Agent audits and extractor guesses are never sufficient here.  Each promoted
chunk must be tied to the exact corpus checksum and an alıntı copied from the
same PDF crop.  The output remains a private corpus artifact.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "ayt-teacher-graph-approval-v1"
CORPUS_SCHEMA = "multi-history-rag-v1"


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "").strip()).casefold()


def _quote_digest(value: str) -> str:
    return hashlib.sha256(_plain(value).encode("utf-8")).hexdigest()


def build_template(corpus: dict) -> dict:
    """Create a blank, private teacher-review manifest from corpus geometry."""
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("Corpus şeması geçersiz")
    approvals = []
    for book in corpus.get("books", []):
        for chunk in book.get("index", {}).get("chunks", []):
            approvals.append({
                "source_checksum": book.get("source_checksum"),
                "chunk_id": str(chunk.get("id", "")),
                "section_id": chunk.get("section_id"),
                "section_title": chunk.get("section_title"),
                "page": chunk.get("page"),
                "bbox": chunk.get("bbox"),
                "decision": "pending",
                "quote": "",
                "quote_sha256": "",
                "pdf_crop_checked": False,
                "quality_checked": False,
            })
    return {
        "schema": SCHEMA,
        "corpus_checksum": corpus.get("corpus_checksum"),
        "reviewer_id": "",
        "reviewer_kind": "human_history_teacher",
        "is_human_teacher_approval": True,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "qlora_enabled": False,
        "approvals": approvals,
        "notice": "Karar, alıntı ve işaretler öğretmen tarafından PDF kesiti üzerinden doldurulmadan terfi edilemez.",
    }


def promote(corpus: dict, manifest: dict) -> dict:
    """Return a copied corpus with only explicitly human-approved chunks promoted."""
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("Corpus şeması geçersiz")
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Öğretmen onay manifesti şeması geçersiz")
    if (not manifest.get("is_human_teacher_approval")
            or manifest.get("reviewer_kind") != "human_history_teacher"
            or not str(manifest.get("reviewer_id", "")).strip()):
        raise ValueError("Runtime grafi için insan tarih öğretmeni onayı gerekli")
    if manifest.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Corpus checksum eşleşmiyor")
    for field in ("answer_key_accessed", "worked_explanation_accessed", "qlora_enabled"):
        if manifest.get(field, False) is not False:
            raise ValueError(f"Güvenlik alanı açık: {field}")
    approvals = manifest.get("approvals")
    if not isinstance(approvals, list) or not approvals:
        raise ValueError("En az bir öğretmen onayı gerekli")

    result = copy.deepcopy(corpus)
    rows: dict[tuple[str, str], dict] = {}
    for book in result.get("books", []):
        checksum = book.get("source_checksum")
        for chunk in book.get("index", {}).get("chunks", []):
            rows[(checksum, str(chunk.get("id")))] = chunk

    seen: set[tuple[str, str]] = set()
    promoted = []
    for approval in approvals:
        source_checksum = approval.get("source_checksum")
        chunk_id = str(approval.get("chunk_id", ""))
        key = (source_checksum, chunk_id)
        if key in seen:
            raise ValueError("Aynı parça iki kez onaylanamaz")
        seen.add(key)
        chunk = rows.get(key)
        if chunk is None:
            raise ValueError("Onay parçası corpus içinde bulunamadı")
        if approval.get("decision") != "approved_for_runtime":
            raise ValueError("Yalnız approved_for_runtime terfi ettirilebilir")
        quote = approval.get("quote", "")
        if not isinstance(quote, str) or len(_plain(quote)) < 12:
            raise ValueError("Onay alıntısı çok kısa")
        if _plain(quote) not in _plain(chunk.get("text", "")):
            raise ValueError("Onay alıntısı aynı PDF parçasında bulunmuyor")
        if approval.get("quote_sha256") != _quote_digest(quote):
            raise ValueError("Onay alıntısı checksum eşleşmiyor")
        if approval.get("pdf_crop_checked") is not True or approval.get("quality_checked") is not True:
            raise ValueError("PDF kırpımı ve kalite kontrolü zorunlu")
        if approval.get("page") != chunk.get("page") or approval.get("bbox") != chunk.get("bbox"):
            raise ValueError("PDF sayfa veya koordinatları corpus ile eşleşmiyor")
        quality = chunk.get("quality", {})
        if any(bool(quality.get(name)) for name in ("visual_or_caption_risk", "instruction_risk", "ocr_fragment_risk")):
            raise ValueError("Riskli parça runtime grafiğe alınamaz")
        chunk["review_status"] = "approved_for_runtime"
        chunk["pre_review"] = {
            "decision": "approved_for_runtime",
            "confidence": "high",
            "explanation": "PDF kesiti insan tarih öğretmeni tarafından doğrulandı.",
            "reviewer_id": manifest.get("reviewer_id"),
            "reviewer_kind": "human_history_teacher",
        }
        chunk["quality"] = {**quality, "quality_checked": True}
        promoted.append({"source_checksum": source_checksum, "chunk_id": chunk_id,
                         "quote_sha256": approval["quote_sha256"]})
    result["promotion"] = {"schema": "ayt-teacher-graph-promotion-v1", "count": len(promoted),
                           "reviewer_id": manifest.get("reviewer_id"), "approvals": promoted}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = promote(load(args.corpus), load(args.manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"schema": output["promotion"]["schema"], "count": output["promotion"]["count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
