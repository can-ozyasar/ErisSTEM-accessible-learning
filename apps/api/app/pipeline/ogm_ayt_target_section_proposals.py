"""Create auditable target-section proposals for private OGM AYT questions.

This is a discovery aid only.  It never reads an answer key or solution and
never marks a question as approved.  Broad OGM topics are split into the six
locked 12th-grade sections using transparent lexical evidence; ambiguous rows
remain in the review queue.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "ogm-ayt-target-section-proposals-v1"
INPUT_SCHEMA = "ogm-ayt-private-transcription-v1"

SECTION_TERMS = {
    "1.3": ("I. DÜNYA SAVAŞI", "I. DÜNYA SAVAŞI SÜRECİNDE OSMANLI", "ÇANAKKALE", "MONDROS", "SEVR", "OSMANLI DEVLETİ"),
    "2.1": ("HAVZA", "AMASYA", "ERZURUM", "SİVAS", "MİSAK-I MİLLÎ", "MİSAK-I MILLI", "TBMM", "BMM", "MİLLÎ MÜCADELE’YE HAZIRLIK", "MILLI MÜCADELEYE HAZIRLIK"),
    "2.4": ("DOĞU CEPHESİ", "GÜNEY CEPHESİ", "GÜMRÜ", "KARS", "MARAŞ", "URFA", "ANTEP", "KAZIM KARABEKİR", "ANKARA ANTLAŞMASI"),
    "2.5": ("BATI CEPHESİ", "I. İNÖNÜ", "II. İNÖNÜ", "SAKARYA", "DUMLUPINAR", "BÜYÜK TAARRUZ", "KÜTAHYA", "ESKİŞEHİR", "İSMET İNÖNÜ", "FARUK"),
    "3.1": ("ATATÜRK İLKELERİ", "CUMHURİYETÇİLİK", "MİLLİYETÇİLİK", "MİLLİYETÇİLİK", "HALKÇILIK", "LAİKLİK", "DEVLETÇİLİK", "İNKILAPÇILIK", "İLKE"),
    "3.2": ("SALTANAT", "HALİFELİK", "CUMHURİYETİN İLANI", "SİYASİ", "SİYASİ ALANDA", "MECLİS", "TEŞKİLAT-I ESASİYE", "KABİNE", "PARTİ"),
}

TOPIC_HINTS = {
    "Millî Mücadele": {"2.1", "2.4", "2.5"},
    "Atatürkçülük ve Türk İnkılabı": {"3.1", "3.2"},
}


def _question_text(row: dict) -> str:
    question = row.get("question", {})
    parts = [question.get("stem", "")]
    parts.extend(choice.get("text", "") for choice in question.get("choices", []))
    return " ".join(parts).upper()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip()


def propose(payload: dict) -> dict:
    if payload.get("schema") != INPUT_SCHEMA:
        raise ValueError("Özel OGM transkripsiyon şeması gerekli")
    rows = payload.get("rows", [])
    if not rows:
        raise ValueError("Boş soru havuzu")
    proposals = []
    for row in rows:
        if row.get("answer_key_accessed") is not False or row.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözüm erişimli kayıt bulunamaz")
        text = _normalise(_question_text(row))
        allowed = TOPIC_HINTS.get(row.get("topic"), set())
        scores = []
        for section_id in sorted(allowed):
            hits = sorted({term for term in SECTION_TERMS[section_id] if term in text})
            if hits:
                scores.append((len(hits), section_id, hits))
        scores.sort(key=lambda item: (-item[0], item[1]))
        best = scores[0][0] if scores else 0
        selected = [item for item in scores if item[0] == best and best > 0]
        confidence = "high" if best >= 2 and len(selected) == 1 else "medium" if best == 1 and len(selected) == 1 else "ambiguous"
        proposals.append({
            "candidate_id": row.get("candidate_id"),
            "topic": row.get("topic"),
            "candidate_section_ids": [item[1] for item in selected] or sorted(allowed),
            "term_hits": {item[1]: item[2] for item in scores},
            "confidence": confidence,
            "needs_pdf_crop_review": True,
            "status": "proposal_only",
        })
    return {
        "schema": SCHEMA,
        "source_checksum": payload["source_checksum"],
        "candidate_count": len(proposals),
        "proposals": proposals,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Lexical target-section proposal only; PDF crop and source evidence review are mandatory.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = propose(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"proposals": result["candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
