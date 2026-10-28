"""Prepare private source-bound demo narration inputs from the local app."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from app import history_source
from app.history_speech import history_spoken_text
from app.question_bank_routes import _layout_contaminated
from app.question_bank_structure import (
    Question,
    navigation_units,
    question_audio_segments,
)

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
QUESTIONS = ROOT / "data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf"
OUTPUT = ROOT / "data/private/tts-v5-demo-input-v1"
PAGES = range(40, 50)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("demo_manifest_already_exists")
    book_sha, question_sha = sha256(HISTORY), sha256(QUESTIONS)
    history_source.BOOK = HISTORY
    entries = []

    def add(kind: str, identity: str, page: int, text: str) -> None:
        text = history_spoken_text(text)
        if not text or len(text) > 8000:
            raise ValueError("unsupported_or_empty_spoken_text")
        entries.append({"kind": kind, "id": identity, "page": page, "spoken_text": text,
                        "spoken_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "contains_digits": bool(re.search(r"\d", text))})

    for page in PAGES:
        for region in history_source._page_data(page)["regions"]:
            if region["spoken_text"] and region["kind"] != "external_link":
                add("history", region["id"], page, region["spoken_text"])

    query = "select coalesce(json_agg(json_build_object('id',id,'payload',payload)), '[]'::json) from learning_records where kind='qb'"
    raw = subprocess.check_output(["docker", "compose", "exec", "-T", "db", "psql", "-U", "eristem", "-d", "eristem", "-t", "-A", "-c", query], cwd=ROOT, text=True)
    records = json.loads(raw)
    approved = 0
    for record in records:
        candidate = record["payload"]["question"]
        if candidate.get("status") != "approved" or _layout_contaminated(candidate):
            continue
        question = Question.model_validate(candidate)
        if record["id"] != f"qb-v1:{question_sha[:12]}:{question.id}":
            raise ValueError("question_pdf_revision_mismatch")
        approved += 1
        for unit in [*navigation_units(question), *question_audio_segments(question)]:
            add("question", f"{question.id}:{unit['id']}", question.source.page, unit["spoken_text"])
        choices = [unit["spoken_text"] for unit in navigation_units(question) if unit["kind"] == "choice"]
        if choices:
            add("question", f"{question.id}:choices", question.source.page, "\n".join(choices))
    identities = [(row["kind"], row["id"]) for row in entries]
    if not approved or len(identities) != len(set(identities)):
        raise ValueError("no_approved_questions_or_duplicate_ids")
    OUTPUT.mkdir(parents=True)
    manifest = {"schema_version": "v5-demo-input-v1", "history_pdf_sha256": book_sha,
                "question_pdf_sha256": question_sha, "history_pages": list(PAGES),
                "approved_questions": approved, "items": entries}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"history_pages": len(PAGES), "approved_questions": approved,
                      "history_units": sum(x["kind"] == "history" for x in entries),
                      "question_units": sum(x["kind"] == "question" for x in entries),
                      "unique_texts": len({x["spoken_text_sha256"] for x in entries}),
                      "units_with_digits": sum(x["contains_digits"] for x in entries),
                      "characters": sum(len(x["spoken_text"]) for x in entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
