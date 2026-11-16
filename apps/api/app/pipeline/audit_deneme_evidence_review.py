"""Audit private teacher evidence proposals against the exact source PDFs.

This audit verifies provenance, not the historical inference or production approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pymupdf


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(box: list[float], page: pymupdf.Page) -> bool:
    return (len(box) == 4 and box[0] >= 0 and box[1] >= 0
            and box[2] > box[0] and box[3] > box[1]
            and box[2] <= page.rect.width + 0.5 and box[3] <= page.rect.height + 0.5)


def _crop_text(page: pymupdf.Page, segments: list[list[float]]) -> str:
    return " ".join(page.get_textbox(pymupdf.Rect(segment)).strip() for segment in segments)


def audit(review: dict, pool: dict, scope: dict, *, question_pdf: Path,
          source_pdf: Path, review_source_name: str) -> dict:
    if review.get("schema") != "ayt-deneme-evidence-teacher-review-v1":
        raise ValueError("Beklenen öğretmen kanıt inceleme şeması yok")
    if pool.get("schema") != "official-ayt-target-discovery-pool-v1":
        raise ValueError("PDF denetimli soru havuzu gerekli")
    if review.get("answer_key_accessed") is not False or review.get("worked_solution_accessed") is not False:
        raise ValueError("Cevap anahtarı veya çözüm kullanılmış")
    if review.get("student_runtime_enabled") is not False or review.get("qlora_enabled") is not False:
        raise ValueError("İnceleme verisi erken etkinleştirilmiş")
    if review.get("meb_pdf_checksum") != _sha256(source_pdf):
        raise ValueError("MEB PDF checksum'ı değişmiş")
    if pool.get("question_source_checksum") != _sha256(question_pdf):
        raise ValueError("Soru PDF checksum'ı değişmiş")
    if review.get("question_source") != review_source_name:
        raise ValueError("Öğretmen incelemesi beklenen soru havuzuna bağlı değil")

    sections = {item["section_id"]: item["book_page_range"] for item in scope["sections"]}
    questions = {item["candidate_id"]: item for item in pool["rows"]}
    if len(questions) != len(pool["rows"]):
        raise ValueError("Yinelenen soru kimliği")

    flags: list[dict] = []
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    seen_atoms: dict[str, tuple] = {}
    with pymupdf.open(question_pdf) as qdoc, pymupdf.open(source_pdf) as sdoc:
        for row in review["rows"]:
            qid = row["candidate_id"]
            if qid in seen or qid not in questions:
                raise ValueError(f"Yinelenen veya bilinmeyen soru: {qid}")
            seen.add(qid)
            question = questions[qid]
            section = row["teacher_section_id"]
            if section not in sections or question["target_section_options"] != [section]:
                raise ValueError(f"Soru bölüm etiketi uyuşmuyor: {qid}")
            if row.get("answer_key_or_solution_used") is not False:
                raise ValueError(f"Cevap/çözüm sızıntısı: {qid}")
            if row.get("production_or_qlora_approved") is not False:
                raise ValueError(f"İnsan onayı olmadan üretim/QLoRA açılmış: {qid}")
            if row.get("question_pdf_page") != question["page"] or row.get("question_bbox") != question["bbox"]:
                raise ValueError(f"Soru kesiti uyuşmuyor: {qid}")
            qpage = qdoc[question["page"] - 1]
            if not _inside(row["question_bbox"], qpage):
                raise ValueError(f"Soru kesiti sayfa dışında: {qid}")
            if row.get("assessment") not in {"direct", "bounded_inference", "insufficient", "wrong"}:
                raise ValueError(f"Geçersiz kanıt kararı: {qid}")
            atoms = row.get("evidence_atoms", [])
            if row.get("evidence_count") != len(atoms) or len(atoms) > 3:
                raise ValueError(f"Kanıt atomu sayısı geçersiz: {qid}")
            counts[row["assessment"]] += 1
            for atom in atoms:
                page_no = atom["page"]
                signature = (atom["source_checksum"], page_no, tuple(atom["bbox"]), atom["quote"])
                old_signature = seen_atoms.setdefault(atom["atom_id"], signature)
                if old_signature != signature:
                    raise ValueError(f"Kanıt atomu kimliği birden fazla kesite bağlı: {atom['atom_id']}")
                if atom["source_checksum"] != review["meb_pdf_checksum"] or not 1 <= page_no <= len(sdoc):
                    raise ValueError(f"Kaynak bağı geçersiz: {qid}")
                page = sdoc[page_no - 1]
                segments = atom.get("bbox_segments") or [atom["bbox"]]
                if not all(_inside(segment, page) for segment in segments):
                    raise ValueError(f"Kanıt kesiti sayfa dışında: {qid}")
                crop = _crop_text(page, segments)
                if " ".join(atom["quote"].split()) not in " ".join(crop.split()):
                    flags.append({"candidate_id": qid, "kind": "quote_not_contiguous_in_crop",
                                  "source_page": page_no, "teacher_section_id": section})
                if atom.get("teacher_status") != "candidate_quote_verified_not_approved":
                    raise ValueError(f"Kaynak onayı durumu geçersiz: {qid}")
                page_range = sections[section]
                if not page_range["start"] <= page_no <= page_range["end"]:
                    flags.append({"candidate_id": qid, "kind": "outside_teacher_section",
                                  "source_page": page_no, "teacher_section_id": section})
                if len(atom["quote"].split()) < 4:
                    flags.append({"candidate_id": qid, "kind": "short_quote_needs_claim_check",
                                  "source_page": page_no, "teacher_section_id": section})

    if review.get("questions_reviewed") != len(seen):
        raise ValueError("Özet soru sayısı uyuşmuyor")
    if dict(counts) != review.get("assessment_counts"):
        raise ValueError("Özet karar sayıları uyuşmuyor")
    missing = sorted(set(questions) - seen)
    provenance_passed = not any(item["kind"] == "quote_not_contiguous_in_crop" for item in flags)
    return {"schema": "ayt-deneme-evidence-provenance-audit-v1", "reviewed": len(seen),
            "pool_total": len(questions), "missing_review_ids": missing,
            "assessment_counts": dict(counts), "flags": flags,
            "quote_provenance_passed": provenance_passed, "semantic_approval": False,
            "runtime_enabled": False, "qlora_enabled": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("review", "pool", "scope", "question-pdf", "source-pdf", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--review-source-name", help="Öğretmenin incelediği eski havuz dosyasının adı")
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = audit(load(args.review), load(args.pool), load(args.scope),
                   question_pdf=args.question_pdf, source_pdf=args.source_pdf,
                   review_source_name=args.review_source_name or args.pool.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("reviewed", "pool_total", "assessment_counts", "flags")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
