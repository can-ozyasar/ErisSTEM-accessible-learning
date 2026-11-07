"""Build a private, source-bound QLoRA research pack from an approved graph.

This command never reads a PDF, answer key or solved-question book.  It
accepts only an already checksum-bound graph and writes the Kaggle-safe
train/dev rows separately from the sealed local evaluation rows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..ayt_autonomy import (
    ConceptBasedDataSplitter,
    GraphToQuestionGenerator,
    HistoryTeacherValidatorAgent,
    SplitRecord,
)
from ..ayt_knowledge_graph import KnowledgeGraph
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


def build(graph_payload: dict, *, limit: int = 40, seed: int = 42) -> tuple[dict[str, list[dict]], dict, list[dict]]:
    # The research-graph file carries top-level operational metadata
    # (research_only, review status). KnowledgeGraph itself is intentionally
    # strict, so pass only its immutable graph fields into the model.
    graph = KnowledgeGraph.model_validate({
        key: graph_payload[key] for key in ("schema", "corpus_checksum", "nodes", "edges")
    })
    drafts = GraphToQuestionGenerator(graph).generate(limit=limit)
    if len(drafts) != limit:
        raise ValueError(f"Kaynak izli {limit} taslak üretilemedi; yalnız {len(drafts)} ilişki uygun")
    validations = [HistoryTeacherValidatorAgent(graph).validate_generated_draft(draft) for draft in drafts]
    rejected = [validation.question_id for validation in validations if validation.decision != "direct"]
    if rejected:
        raise ValueError(f"Öğretmen ajanı {len(rejected)} tersine üretilen taslağı doğrudan kanıtlayamadı")
    private_drafts = [draft.model_dump(mode="json") for draft in drafts]
    split = ConceptBasedDataSplitter(seed=seed).split([
        SplitRecord(id=draft.id, concept_keys=draft.concept_keys, payload={"draft_id": draft.id})
        for draft in drafts
    ])
    groups = {name: rows for name, rows in (("train", split.train), ("dev", split.dev), ("sealed_test", split.test))}
    by_id = {draft["id"]: draft for draft in private_drafts}
    rows = {name: [row for item in records for row in _rows_for_draft(by_id[item.id])]
            for name, records in groups.items()}
    manifest = {
        "schema": "autonomous-graph-qlora-research-pack-v1",
        "status": "research_ready",
        "review_status": "agent_generated_source_traceable",
        "question_groups": len(private_drafts),
        "examples": sum(len(value) for value in rows.values()),
        "splits": {name: len(records) for name, records in groups.items()},
        "source_bound": True,
        "teacher_agent_direct_validations": len(validations),
        "answer_keys_included": False,
        "human_review_required_before_production": True,
        "corpus_checksum": graph.corpus_checksum,
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
    return rows, manifest, private_drafts


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--kaggle-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--private-drafts-output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    payload = json.loads(args.graph.read_text(encoding="utf-8"))
    rows, manifest, drafts = build(payload, limit=args.limit, seed=args.seed)
    for name in ("train", "dev"):
        _write_jsonl(args.kaggle_output / f"{name}.jsonl", rows[name])
    _write_jsonl(args.sealed_output / "sealed_test.jsonl", rows["sealed_test"])
    args.private_drafts_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_drafts_output.write_text(json.dumps({"schema": "autonomous-graph-drafts-v1", "drafts": drafts}, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.kaggle_output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
