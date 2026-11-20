"""Build source-bound six-state coaching candidates from frozen question items."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ..tutor_dataset import CASES
from ..tutor_authoring import infer_error_type, learner_state


def _quote(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _response(case: str, error_type: str, quote: str) -> tuple[str, str]:
    focus = {
        "tarih": "zamanı gösteren sözcük", "kronoloji": "önce-sonra ilişkisi",
        "neden_sonuc": "neden ile sonuç arasındaki bağ", "kisi": "kişinin görevi",
        "yer": "yer adı", "kaynak_yorumu": "metnin doğrudan söylediği bilgi",
        "asiri_genelleme": "geniş yargıyı sınırlayan ayrıntı", "genel": "belirleyici ayrıntı",
    }[error_type]
    values = {
        "soruyu_anlama": ("focus_question", f"Soru kökünde aradığın {focus} nedir?"),
        "hatirlayani_ortaya_cikar": ("recall", f"Kaynaktaki ‘{quote}’ bilgisi sana neyi hatırlatıyor?"),
        "kanitla_bag_kur": ("evidence_link", f"Kaynaktaki hangi söz, sorudaki {focus} ile bağ kurmana yardım eder?"),
        "siki_sina": ("evidence_comparison", "Seçtiğin ifadedeki hangi ayrıntıyı kaynakla karşılaştırmalısın?"),
        "yanlis_cevabi_duzelt": ("source_reanchor", f"Kaynaktaki ‘{quote}’ bilgisi seçiminle hangi noktada uyuşmuyor?"),
        "dogruyu_pekistir": ("self_explanation", "Seçimini kaynakta geçen bilgiyle kendi cümlenle nasıl gerekçelendirirsin?"),
    }
    return values[case]


def build(pack: dict) -> dict:
    if pack.get("schema") != "ayt-history-question-bank-training-candidate-v1" or not pack.get("question_bank_training_candidate_ready"):
        raise ValueError("Donmuş soru-bankası eğitim adayı gerekli")
    questions = pack.get("questions", [])
    if len(questions) != 120:
        raise ValueError("Koçluk adayları tam 120 sorudan üretilmeli")
    records = []
    for question in questions:
        evidence = question.get("source_evidence", {})
        quote = _quote(str(evidence.get("quote", "")))
        if not quote:
            raise ValueError("Her koçluk adayı kısa kaynak alıntısı taşımalı")
        error_type = infer_error_type(question.get("question", ""))
        source_id = f"{evidence.get('source_checksum')}:{evidence.get('atom_id')}"
        turns = []
        for case in CASES:
            strategy, response = _response(case, error_type, quote)
            turns.append({"case": case, "learner_state": learner_state(case), "strategy": strategy,
                          "guide_response": response, "source_ids": [source_id], "evidence_quotes": [quote],
                          "grounding_mode": "source_evidence", "early_answer_disclosed": False,
                          "runtime_enabled": False})
        records.append({"question_id": question["id"], "question_checksum": hashlib.sha256(json.dumps(question, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                        "error_type": error_type, "turns": turns, "runtime_enabled": False})
    return {"schema": "ayt-history-source-bound-coaching-drafts-v1", "corpus_checksum": pack["corpus_checksum"],
            "question_bank_checksum": pack["frozen_checksum"], "records": records,
            "summary": {"question_groups": len(records), "draft_turns": len(records) * len(CASES), "cases_per_question": len(CASES)},
            "answer_key_accessed": False, "student_data_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Deterministic source-bound coaching candidates only; independent teacher-style review remains required."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.pack.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
