"""Project PDF-checked deneme scope decisions into private evidence discovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(pool: dict, teacher: dict | list[dict], scope: dict) -> dict:
    if pool.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("AYT deneme aday havuzu gerekli")
    reviews = teacher if isinstance(teacher, list) else [teacher]
    supported = {"ayt-deneme-scope-teacher-review-v1",
                 "ayt-deneme-inline-repair-teacher-review-v1",
                 "ayt-deneme-remaining-scope-teacher-review-v1"}
    for item in reviews:
        if item.get("schema") not in supported:
            raise ValueError("PDF kesitli tarih öğretmeni denetimi gerekli")
        if item.get("source_pdf_checksum") != pool.get("source_checksum"):
            raise ValueError("Soru PDF checksum'ı uyuşmuyor")
        if item.get("answer_key_accessed") is not False or item.get("worked_solution_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözüm erişimli denetim kullanılamaz")
        if item.get("schema") != "ayt-deneme-scope-teacher-review-v1" and item.get("all_choice_boxes_match_pdf") is not True:
            raise ValueError("Onarılmış şık kutuları PDF ile doğrulanmamış")
        if item.get("schema") == "ayt-deneme-remaining-scope-teacher-review-v1" and item.get("all_question_parts_match_pdf") is not True:
            raise ValueError("Soru kökü parçaları PDF ile doğrulanmamış")
    if pool.get("answer_key_accessed") is not False or pool.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap anahtarı veya çözüm erişimli havuz kullanılamaz")
    target = {section["section_id"] for section in scope["sections"]}
    if len(target) != 6:
        raise ValueError("Altı hedef bölüm gerekli")
    source_by_id = {row["candidate_id"]: row for row in pool["rows"]}
    if len(source_by_id) != len(pool["rows"]):
        raise ValueError("Yinelenen aday kimliği")
    rows = []
    seen_reviews: set[str] = set()
    for review_set, review in ((batch, row) for batch in reviews for row in batch["rows"]):
        candidate_id = review["candidate_id"]
        if candidate_id in seen_reviews:
            raise ValueError(f"Yinelenen öğretmen kararı: {candidate_id}")
        seen_reviews.add(candidate_id)
        if review["teacher_scope_decision"] != "in_scope_text_question":
            continue
        original = source_by_id.get(candidate_id)
        if original is None:
            raise ValueError(f"İncelenen soru aday havuzunda yok: {candidate_id}")
        section_id = review.get("teacher_section_id")
        if section_id not in target:
            raise ValueError("İncelenen bölüm allowlist dışında")
        if review_set["schema"] != "ayt-deneme-scope-teacher-review-v1":
            if (review.get("question_pdf_crop_visually_checked") is not True
                    or review.get("stem_and_statement_text_pdf_checked") is not True
                    or review.get("question_bbox") != original["question"]["source"]["bbox"]
                    or len(review.get("choice_geometry_checks", [])) != 5):
                raise ValueError("Soru PDF denetimi eksik")
            if (review_set["schema"] == "ayt-deneme-inline-repair-teacher-review-v1"
                    and original.get("layout_repair") != review.get("layout_repair_method")):
                raise ValueError("Onarılmış soru kaynak yöntemi uyuşmuyor")
            checks = review["choice_geometry_checks"]
            for choice, check in zip(original["question"]["choices"], checks):
                if (choice["label"] != check.get("label")
                        or check.get("pdf_text_match") is not True
                        or check.get("box_inside_question") is not True
                        or choice["source"]["bbox"] != check.get("bbox")):
                    raise ValueError("Onarılmış şık koordinatı öğretmen denetimiyle uyuşmuyor")
            if review_set["schema"] == "ayt-deneme-remaining-scope-teacher-review-v1":
                part_checks = review.get("part_geometry_checks", [])
                if len(part_checks) != len(original["question"]["parts"]):
                    raise ValueError("Soru kökü parça denetimi eksik")
                for part, check in zip(original["question"]["parts"], part_checks):
                    if (check.get("pdf_text_match") is not True
                            or part["source"]["bbox"] != check.get("bbox")):
                        raise ValueError("Soru kökü koordinatı öğretmen denetimiyle uyuşmuyor")
        elif (review.get("pdf_crop_checked") is not True
              or review.get("stem_and_five_choices_pdf_checked") is not True
              or review.get("choice_count") != 5
              or review.get("pdf_crop_bbox") != original["question"]["source"]["bbox"]):
            raise ValueError("Soru PDF ve metin kapsam denetimi eksik")
        if review.get("visual_dependency") not in {False, "none_detected_in_question_crop"}:
            raise ValueError("Görsel soru metin kapsamına giremez")
        question = original["question"]
        if question["source"]["source_checksum"] != pool["source_checksum"]:
            raise ValueError("Soru kaynak izi PDF ile uyuşmuyor")
        stem = " ".join(part.get("text", "") for part in question["parts"]).strip()
        if not stem or len(question["choices"]) != 5:
            raise ValueError("Soru metni veya şıkları eksik")
        rows.append({
            "candidate_id": candidate_id,
            "source_kind": original["source_kind"],
            "source_checksum": original["source_checksum"],
            "page": original["page"],
            "bbox": question["source"]["bbox"],
            "question": {"stem": stem, "parts": question["parts"],
                         "choices": question["choices"]},
            "target_section_options": [section_id],
            "transcription_status": "private_teacher_review_required",
            "teacher_scope_review": {
                "reviewer_role": review_set["reviewer_role"],
                "review_schema": review_set["schema"],
                "decision": review["teacher_scope_decision"],
                "pdf_crop_checked": True,
                "transcription_verdict": review.get("transcription_verdict"),
                "flags": review.get("flags", []),
            },
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
        })
    return {
        "schema": "official-ayt-target-discovery-pool-v1",
        "corpus_checksum": scope["source_binding"]["corpus_checksum"],
        "candidate_section_ids": sorted(target),
        "question_source_checksum": pool["source_checksum"],
        "rows": rows,
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Agent PDF scope review only; evidence, answer and coaching approval remain pending.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--teacher", type=Path, required=True, action="append")
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = build(load(args.pool), [load(path) for path in args.teacher], load(args.scope))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": report["candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
