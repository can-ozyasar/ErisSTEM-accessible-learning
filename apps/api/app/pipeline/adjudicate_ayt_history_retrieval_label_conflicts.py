"""Fail-closed, answer-blind adjudication for conflicting PDF-card labels."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from .deepseek_crop_visual_review import _call

DECISIONS = {"relevant", "wrong", "insufficient"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def collect(manifests: dict[str, dict], labels: dict[str, dict]) -> list[dict]:
    cards: dict[tuple[str, str], dict] = {}
    decisions: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for method, manifest in manifests.items():
        if manifest.get("schema") != "ayt-history-rank-blind-pdf-retrieval-review-template-v1":
            raise ValueError("Rank-blind PDF manifest gerekli")
        by_question = {row["id"]: row for row in manifest.get("reviews", [])}
        for label in labels[method].get("labels", []):
            review = by_question.get(label.get("id"))
            if review is None:
                raise ValueError("Etiket ve manifest soru kimlikleri eşleşmiyor")
            by_source = {card["source_key"]: card for card in review.get("cards", [])}
            for decision, key in (("relevant", "relevant_source_ids"), ("wrong", "wrong_source_ids"), ("insufficient", "insufficient_source_ids")):
                for source_key in label.get(key, []):
                    card = by_source.get(source_key)
                    if card is None:
                        raise ValueError("Etiketli kart manifestte bulunamadı")
                    record_key = (label["id"], source_key)
                    cards.setdefault(record_key, {"id": label["id"], "source_key": source_key, "question": review["question"],
                                                  "choices": review["choices"], "card": card, "method": method})
                    decisions[record_key].append({"method": method, "decision": decision})
    return [{**cards[key], "prior_decisions": values} for key, values in sorted(decisions.items())
            if len({value["decision"] for value in values}) > 1]


def _request(row: dict, crop_root: Path, model: str) -> tuple[dict, Path]:
    relative = Path(row["card"]["crop"])
    image = (crop_root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not image.is_relative_to(crop_root.resolve()) or not image.is_file():
        raise ValueError("Güvenli yerel PDF kırpımı gerekli")
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    payload = {"question": row["question"], "choices": row["choices"], "excerpt": row["card"]["excerpt"]}
    prompt = (
        "Sen Türkçe tarih kaynak kanıtı için bağımsız, cevap-kör PDF inceleme ajanısın. Yalnız soru, şıklar, "
        "kart alıntısı ve PDF görüntüsünü kullan; dış bilgi kullanma, doğru cevap/şık/çözüm yazma. Kart sorunun "
        "şıklarını ayırt etmeye doğrudan yetiyorsa relevant; çelişiyor/ilgisizse wrong; ilgili fakat ayırt etmeye "
        "yetmiyorsa insufficient seç. Önceki değerlendirmeler sana gösterilmez. JSON dışında yanıt verme: "
        '{"decision":"relevant|wrong|insufficient","rationale":"12-40 kelime"}.\n'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    return ({"model": model, "temperature": 0, "thinking": {"type": "disabled"}, "max_tokens": 256,
             "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": [
                 {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
             ]}]}, image)


def _parse(response: dict) -> dict:
    try:
        result = json.loads(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Adjudication geçerli JSON dönmedi") from error
    if result.get("decision") not in DECISIONS or not isinstance(result.get("rationale"), str) or not 12 <= len(result["rationale"].strip()) <= 320:
        raise ValueError("Adjudication kararı veya gerekçesi geçersiz")
    return {"decision": result["decision"], "rationale": result["rationale"].strip()}


def adjudicate(conflicts: list[dict], roots: dict[str, Path], api_key: str, *, model: str, request_fn=_call) -> dict:
    if not api_key:
        raise ValueError("API anahtarı gerekli")
    records = []
    for row in conflicts:
        root = roots[row["method"]]
        outcomes = []
        for _ in range(2):
            request, image = _request(row, root, model)
            started = time.perf_counter()
            response = request_fn(request, api_key, 60)
            outcomes.append({**_parse(response), "request_sha256": _digest(request),
                             "crop_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                             "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        decision = outcomes[0]["decision"] if outcomes[0]["decision"] == outcomes[1]["decision"] else "review_required"
        records.append({"id": row["id"], "source_key": row["source_key"], "prior_decisions": row["prior_decisions"],
                        "fresh_reviews": outcomes, "resolution": decision})
    return {"schema": "ayt-history-retrieval-label-conflict-adjudication-v1", "model": model, "records": records,
            "summary": {"conflict_count": len(records), "resolved_count": sum(row["resolution"] != "review_required" for row in records),
                        "review_required_count": sum(row["resolution"] == "review_required" for row in records)},
            "answer_key_accessed": False, "student_data_accessed": False, "is_human_teacher_approval": False,
            "runtime_enabled": False, "notice": "Two fresh answer-blind agent reviews. Disagreement is retained as review_required; this is not human approval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--labels", type=Path, action="append", required=True)
    parser.add_argument("--crop-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--allow-external-private-evaluation", action="store_true")
    args = parser.parse_args()
    if not args.allow_external_private_evaluation or not (len(args.manifest) == len(args.labels) == len(args.crop_root) == 3):
        raise SystemExit("Üç yöntem için manifest/etiket/kırpım kökü ve açık dış değerlendirme izni gerekli")
    methods = ("bm25", "qwen_dense", "rrf")
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    manifests, labels = dict(zip(methods, map(load, args.manifest), strict=True)), dict(zip(methods, map(load, args.labels), strict=True))
    result = adjudicate(collect(manifests, labels), dict(zip(methods, args.crop_root, strict=True)), os.getenv(args.api_key_env, ""), model=args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
