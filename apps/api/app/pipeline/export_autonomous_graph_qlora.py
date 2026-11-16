"""Build a private, source-bound QLoRA research pack from an approved graph.

This command never reads a PDF, answer key or solved-question book.  It
accepts only an already checksum-bound graph and writes the Kaggle-safe
train/dev rows separately from the sealed local evaluation rows.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..ayt_autonomy import (
    ConceptBasedDataSplitter,
    GeneratedDraftQualityGate,
    GraphToQuestionGenerator,
    HistoryTeacherValidatorAgent,
    SplitRecord,
)
from ..ayt_knowledge_graph import KnowledgeGraph
from ..question_scope import AccessibilityAndScopeFilter
from ..tutor_dataset import CASES


def _error_type(relation: str) -> str:
    if relation in {"DONEMINDE_OLMUSTUR", "KRONOLOJIK_SONRASIDIR"}:
        return "kronoloji"
    if relation in {"SEBEBIDIR", "SONUCUDUR", "AMACIDIR"}:
        return "neden_sonuc"
    if relation == "AKTORUDUR":
        return "kisi"
    if relation == "COGRAFYASIDIR":
        return "yer"
    return "kaynak_yorumu"


def _coach_completion(case: str, *, subject: str, relation: str, quote: str) -> str:
    """Keep early coaching turns short and free of answer labels."""
    abbreviated_quote = quote.strip()[:420]
    templates = {
        "soruyu_anlama": (
            f"Soruda iki bilgi arasındaki bağı arıyorsun: {subject}. Önce şıklardaki ilişki sözlerini ayır."
        ),
        "hatirlayani_ortaya_cikar": (
            "Bu iki bilgiden hangisini daha net hatırlıyorsun? Önce onu söyle; sonra ötekiyle nasıl bağlandığını düşün."
        ),
        "kanitla_bag_kur": (
            f"Kaynakta şu ipucu var: “{abbreviated_quote}” Bu cümle iki bilgi arasında nasıl bir bağ kuruyor?"
        ),
        "siki_sina": (
            "Her şıktaki ilişkiyi kaynak cümlesiyle tek tek karşılaştır. Kaynağın kurmadığı bağı eleyebilirsin."
        ),
        "yanlis_cevabi_duzelt": (
            f"Burada ilişki türleri karışmış olabilir. Kaynak, {subject} için “{relation}” bağını gösteriyor. Bunu kendi sözlerinle yeniden kurar mısın?"
        ),
        "dogruyu_pekistir": (
            f"Güzel. Kaynaktaki ilişki “{relation}”. Bu bağı hatırlarsan benzer sorularda şıkları daha rahat ayırırsın."
        ),
    }
    return templates[case]


def _rows_for_draft(draft: dict) -> list[dict]:
    question = draft["runtime_question"]
    relation_type = draft["relation_type"]
    relation = relation_type.replace("_", " ").casefold()
    subject = question["stem"].removeprefix("Kaynağa göre ").removesuffix(" arasındaki ilişki hangisidir?")
    choices = " | ".join(f"{item['label']}) {item['text']}" for item in question["choices"])
    output = []
    for case in CASES:
        prompt = "\n".join((
            "Sen görme engelli bir lise öğrencisine kısa, sakin ve Sokratik tarih koçluğu yapıyorsun.",
            f"Koçluk durumu: {case}",
            f"Soru: {question['stem']}",
            f"Şıklar: {choices}",
            f"Onaylı kaynak alıntısı: {draft['source_quote']}",
            "Koç:",
        ))
        output.append({
            "group_id": draft["id"],
            "case": case,
            "error_type": _error_type(relation_type),
            "prompt": prompt,
            "completion": _coach_completion(case, subject=subject, relation=relation, quote=draft["source_quote"]),
        })
    return output


def build(graph_payload: dict, *, scope: dict, limit: int = 40,
          seed: int = 42) -> tuple[dict[str, list[dict]], dict, list[dict], list[dict]]:
    # The research-graph file carries top-level operational metadata
    # (research_only, review status). KnowledgeGraph itself is intentionally
    # strict, so pass only its immutable graph fields into the model.
    graph = KnowledgeGraph.model_validate({
        key: graph_payload[key] for key in ("schema", "corpus_checksum", "nodes", "edges")
    })
    # Generate a wider private candidate pool.  Source traceability alone is
    # insufficient: OCR fragments can still form an unusable spoken question.
    # The deterministic quality gate runs *before* the split, so rejected
    # drafts can never leak into Kaggle training or sealed evaluation.
    # Source books are uneven: the first relation-ranked candidates can share
    # an OCR layout pattern. Search a wider private pool before deciding that
    # the target count is unavailable; the quality gate still decides every
    # individual record.
    if graph.corpus_checksum != scope["source_binding"]["corpus_checksum"]:
        raise ValueError("Hedef kapsam ve graf corpus checksum'ı uyuşmuyor")
    bindings = scope.get("source_bindings")
    if bindings:
        source_page_ranges = {
            binding["source_checksum"]: [(section["start"], section["end"])
                                         for section in binding["sections"]]
            for binding in bindings
        }
        allowed_section_ids = [section["section_id"] for binding in bindings
                               for section in binding["sections"]]
    else:
        source_checksum = scope["source_binding"]["meb_source_checksum"]
        page_ranges = [(section["book_page_range"]["start"], section["book_page_range"]["end"])
                       for section in scope["sections"]]
        source_page_ranges = {source_checksum: page_ranges}
        allowed_section_ids = [section["section_id"] for section in scope["sections"]]
    scope_filter = AccessibilityAndScopeFilter(
        target_section_ids=allowed_section_ids,
        source_page_ranges=source_page_ranges,
    )
    # Exhaust the finite source graph. A rejected candidate is logged and the
    # loop continues; exhaustion is reported as a shortage instead of silently
    # fabricating questions or hanging in an unbounded while loop.
    generator = GraphToQuestionGenerator(graph, source_page_ranges=source_page_ranges)
    candidates = generator.generate(limit=max(len(graph.edges), 1))
    quality_gate = GeneratedDraftQualityGate()
    scope_rejections: Counter[str] = Counter()
    quality_rejections: Counter[str] = Counter()
    validation_rejections: Counter[str] = Counter()
    teacher_validator = HistoryTeacherValidatorAgent(graph)
    drafts = []
    validations = []
    for draft in candidates:
        scope_result = scope_filter.evaluate(
            {"stem": draft.runtime_question.stem,
             "choices": [choice.model_dump(mode="json") for choice in draft.runtime_question.choices]},
            page=draft.page, source_checksum=draft.source_checksum,
        )
        if not scope_result.eligible:
            scope_rejections.update(scope_result.reasons)
            continue
        quality = quality_gate.review(draft)
        if not quality.accepted:
            quality_rejections.update(quality.issues)
            continue
        validation = teacher_validator.validate_generated_draft(draft)
        if validation.decision != "direct":
            validation_rejections[validation.decision] += 1
            continue
        drafts.append(draft)
        validations.append(validation)
        if len(drafts) == limit:
            break
    private_drafts = [draft.model_dump(mode="json") for draft in drafts]
    complete_target = len(private_drafts) == limit
    if complete_target:
        split = ConceptBasedDataSplitter(seed=seed).split([
            SplitRecord(id=draft.id, concept_keys=draft.concept_keys, payload={"draft_id": draft.id})
            for draft in drafts
        ])
        groups = {name: items for name, items in (("train", split.train), ("dev", split.dev), ("sealed_test", split.test))}
        by_id = {draft["id"]: draft for draft in private_drafts}
        rows = {name: [row for item in items for row in _rows_for_draft(by_id[item.id])]
                for name, items in groups.items()}
    else:
        groups = {"train": [], "dev": [], "sealed_test": []}
        rows = {name: [] for name in groups}
    manifest = {
        "schema": "autonomous-graph-qlora-research-pack-v1",
        "status": "candidate_review_required" if complete_target else "source_pool_exhausted_below_target",
        "review_status": "agent_generated_source_traceable",
        "question_groups": len(private_drafts),
        "target_question_groups": limit,
        "shortfall": max(0, limit - len(private_drafts)),
        "source_pool_exhausted": not complete_target,
        "examples": 0,
        "draft_coaching_turns_for_private_review": sum(len(value) for value in rows.values()),
        "splits": {name: len(records) for name, records in groups.items()},
        "source_bound": True,
        "teacher_agent_direct_validations": len(validations),
        "semantic_duplicate_candidates_collapsed": generator.semantic_duplicates_collapsed,
        "deterministic_draft_quality_gate": {
            "candidate_count": len(candidates),
            "accepted_count": len(drafts),
            "scope_rejection_reasons": dict(sorted(scope_rejections.items())),
            "quality_rejection_reasons": dict(sorted(quality_rejections.items())),
            "teacher_validation_rejections": dict(sorted(validation_rejections.items())),
            "gate": "deterministic_draft_quality_gate_v1",
        },
        "relation_distribution": dict(sorted(Counter(draft.relation_type for draft in drafts).items())),
        "answer_keys_included": False,
        "human_review_required_before_production": True,
        "training_eligible_without_human_review": False,
        "kaggle_exported": False,
        "qlora_block_reason": "120 kaynaklı soru grubu ve 720 onaylı koçluk turu tamamlanmadı",
        "qlora_enabled": False,
        "corpus_checksum": graph.corpus_checksum,
        "scope_applied": True,
        "scope_grade": scope.get("grade"),
        "seed": seed,
        "kaggle_runner": {
            "script": "experiments/kaggle/history_tutor_qwen14b_qlora.py",
            "environment": {
                "TUTOR_QLORA_EXPECTED_TRAIN_GROUPS": str(len(groups["train"])),
                "TUTOR_QLORA_EXPECTED_DEV_GROUPS": str(len(groups["dev"])),
            },
            "sealed_test_uploaded": False,
        },
    }
    return rows, manifest, private_drafts, [item.model_dump(mode="json") for item in validations]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--kaggle-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--private-drafts-output", type=Path, required=True)
    parser.add_argument("--quality-audit-output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scope", type=Path, required=True,
                        help="Private target-scope manifest; limits graph drafts to its book and pages")
    args = parser.parse_args()
    payload = json.loads(args.graph.read_text(encoding="utf-8"))
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    _rows, manifest, drafts, reviews = build(payload, limit=args.limit, seed=args.seed, scope=scope)
    # These are agent-generated review candidates, not approved training rows.
    # Keep them private. The reviewed DB exporter is the only Kaggle writer.
    args.private_drafts_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_drafts_output.write_text(json.dumps({"schema": "autonomous-graph-drafts-v1", "drafts": drafts}, ensure_ascii=False, indent=2), encoding="utf-8")
    args.quality_audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.quality_audit_output.write_text(json.dumps({"schema": "generated-draft-teacher-validation-v1", "reviews": reviews}, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = args.private_drafts_output.parent / "candidate-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**manifest, "private_manifest": str(manifest_path),
                      "kaggle_output_written": False, "sealed_output_written": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
