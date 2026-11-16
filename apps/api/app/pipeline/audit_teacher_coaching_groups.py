"""Audit real AYT coaching groups before they can join QLoRA training.

This checks mechanical integrity and prepares a private semantic review queue.
Word overlap is diagnostic only: it cannot establish that a historical claim
is supported. No output from this audit authorizes QLoRA or student runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from ..question_scope import visual_cue_in_text, visual_dependency_reasons
from ..tutor_dataset import CASES, EARLY_ANSWER_CASES

CASE_ALIASES = {
    "soru_analizi": "soruyu_anlama",
    "hatırlamayı_ortaya_çıkarma": "hatirlayani_ortaya_cikar",
    "kanıtla_bağ_kurma": "kanitla_bag_kur",
    "şık_sınama": "siki_sina",
    "yanlış_cevap_düzeltme": "yanlis_cevabi_duzelt",
    "doğru_cevabı_gerekçelendirme": "dogruyu_pekistir",
}
TOKEN_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]{3,}")
OCR_BREAK_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]{2,}-\s+[a-zçğıöşüâîû]")
ANSWER_LEAK_RE = re.compile(r"\b(?:doğru cevap|doğru şık|cevap\s*[:：]|şık\s*[A-E]\b|[A-E]\s*ş(?:ı|i)kk?ı)\b", re.IGNORECASE)
NON_HISTORY_RE = re.compile(
    r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])(?:cos|sin|cot|tan)(?=[0-9xαñ(])|"
    r"\b(?:trigonometr\w*|fonksiyon\w*|türev\w*|integral\w*|"
    r"gerçel\s+sayı|dik\s+koordinat|eşkenar\s+dörtgen|açıortay|çokgen|"
    r"doğru\s+sıralanış\w*)\b", re.IGNORECASE,
)
NON_PEDAGOGICAL_PHRASES = (
    "olay, kişi, ilişki veya çıkarım hangisi öne çıkıyor",
    "sunucu kaynak bağlılığını değerlendirecek",
    "kaynakta bulunmayan ayrıntıyı tamamlayarak kesin cevap verme",
)
STOPWORDS = {
    "aşağıdakilerden", "hangisi", "hangisinin", "olarak", "olan", "olduğu", "değildir",
    "bir", "ile", "için", "sonra", "önce", "göre", "dönemi", "soru", "öğrenci",
    "kaynak", "bilgi", "arasında", "sırasında", "üzerinde", "tarafından", "ancak",
}


def _clean(text: str) -> str:
    return " ".join(text.split())


def _terms(text: str) -> set[str]:
    return {word.casefold() for word in TOKEN_RE.findall(text) if word.casefold() not in STOPWORDS}


def _question_map(payload: dict) -> dict[str, str]:
    if payload.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Özel soru transkripsiyonu gerekli")
    if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap anahtarı veya çözüm erişimli transkripsiyon kabul edilmez")
    result = {}
    for row in payload.get("rows", []):
        question = row.get("question", {})
        text = " ".join([question.get("stem", ""), *(choice.get("text", "") for choice in question.get("choices", []))])
        if isinstance(row.get("candidate_id"), str) and text.strip():
            result[row["candidate_id"]] = _clean(text)
    return result


def _candidate_question_map(payloads: list[dict]) -> dict[str, str]:
    """Read private question candidates without answer or solution material."""
    result: dict[str, str] = {}
    for payload in payloads:
        if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözümlü kaynak erişimli soru adayı kabul edilmez")
        for row in payload.get("rows", []):
            question = row.get("question", {})
            pieces = [part.get("text", "") for part in question.get("parts", [])]
            pieces.extend(choice.get("text", "") for choice in question.get("choices", []))
            candidate_id = row.get("candidate_id")
            text = _clean(" ".join(value for value in pieces if isinstance(value, str)))
            if isinstance(candidate_id, str) and text:
                result.setdefault(candidate_id, text)
    return result


def _question_locators(payloads: list[dict]) -> dict[str, dict]:
    """Keep crop coordinates private and never infer them from OCR text."""
    locators = {}
    for payload in payloads:
        for row in payload.get("rows", []):
            qid = row.get("candidate_id")
            if not isinstance(qid, str):
                continue
            source = row.get("question", {}).get("source", {})
            checksum = (source.get("source_checksum") or row.get("source_checksum")
                        or payload.get("source_checksum"))
            # A combined transcription file can mix PDF sources. Its top-level
            # checksum applies only to IDs whose embedded prefix agrees.
            id_parts = qid.split(":")
            if checksum and len(id_parts) > 1 and not checksum.startswith(id_parts[1]):
                checksum = source.get("source_checksum") or row.get("source_checksum")
            locators[qid] = {
                "source_checksum": checksum,
                "source_name": row.get("source_name") or payload.get("source_name"),
                "page": source.get("page", row.get("page")),
                "bbox": source.get("bbox"),
            }
    return locators


def _question_visual_scope(payloads: list[dict]) -> dict[str, list[str]]:
    result = {}
    for payload in payloads:
        for row in payload.get("rows", []):
            qid = row.get("candidate_id")
            if isinstance(qid, str):
                result[qid] = visual_dependency_reasons(row.get("question", {}), row.get("issues"))
    return result


def _corpus_source_locators(corpus: dict | None) -> dict[str, dict]:
    if corpus is None:
        return {}
    result = {}
    for book in corpus.get("books", []):
        for kind in ("chunks", "context_chunks", "evidence_atoms"):
            for item in book["index"].get(kind, []):
                result[item["id"]] = {
                    "source_checksum": book["source_checksum"],
                    "source_name": book.get("source_name"),
                    "page": item.get("page"),
                    "bbox": item.get("bbox"),
                    "section_id": item.get("section_id"),
                    "review_status": item.get("review_status"),
                }
    return result


def _corpus_source_map(corpus: dict) -> dict[str, str]:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü çoklu tarih corpus'u gerekli")
    result: dict[str, str] = {}
    for book in corpus.get("books", []):
        index = book["index"]
        if book.get("source_checksum") != index.get("source_checksum"):
            raise ValueError("Kitap ve indeks kaynak checksum'ı eşleşmiyor")
        for kind in ("chunks", "context_chunks", "evidence_atoms"):
            for item in index.get(kind, []):
                source_id, source_text = item.get("id"), item.get("text")
                if not isinstance(source_id, str) or not isinstance(source_text, str):
                    raise TypeError("Corpus kaynak kimliği veya metni geçersiz")
                if source_id in result and result[source_id] != source_text:
                    raise ValueError("Aynı kaynak kimliği farklı metinlere bağlanmış")
                result[source_id] = source_text
    return result


def audit(drafts: list[dict], transcriptions: dict, candidate_sources: list[dict] | None = None,
          corpus: dict | None = None, question_pdf_checksums: set[str] | None = None) -> dict:
    legacy_questions = _question_map(transcriptions)
    current_candidates = _candidate_question_map(candidate_sources or [])
    # A newly parsed PDF supersedes older transcriptions for that document
    # namespace. Old question IDs absent from the current clean set cannot
    # slip into QLoRA merely because a prior transcription still exists.
    refreshed_namespaces = {qid.split(":", 1)[0] for qid in current_candidates}
    questions = {qid: text for qid, text in legacy_questions.items()
                 if qid.split(":", 1)[0] not in refreshed_namespaces}
    questions.update(current_candidates)
    corpus_sources = _corpus_source_map(corpus) if corpus is not None else None
    locators = _question_locators([transcriptions, *(candidate_sources or [])])
    visual_scope = _question_visual_scope([transcriptions, *(candidate_sources or [])])
    source_locators = _corpus_source_locators(corpus)
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    group_provenance: dict[str, list[str]] = defaultdict(list)
    for source_no, payload in enumerate(drafts):
        if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözümlü kaynak erişimli taslak kabul edilmez")
        for record in payload.get("records", []):
            qid = record.get("question_id")
            stage = CASE_ALIASES.get(record.get("case", record.get("stage")), record.get("case", record.get("stage")))
            if not isinstance(qid, str) or stage not in CASES:
                continue
            # Identical files can repeat a group; genuinely different revisions
            # cannot be silently combined into one training example.
            if stage in groups[qid]:
                if groups[qid][stage] != record:
                    groups[qid][stage] = None
            else:
                groups[qid][stage] = record
            group_provenance[qid].append(f"draft:{source_no}")

    crop_groups: dict[tuple, list[str]] = defaultdict(list)
    for qid in groups:
        locator = locators.get(qid, {})
        bbox = locator.get("bbox")
        if locator.get("source_checksum") and locator.get("page") and isinstance(bbox, list) and len(bbox) == 4:
            crop_key = (locator["source_checksum"], locator["page"],
                        tuple(round(float(value), 2) for value in bbox))
            crop_groups[crop_key].append(qid)
    duplicate_of = {}
    for qids in crop_groups.values():
        if len(qids) > 1:
            canonical = min(qids)
            duplicate_of.update({qid: canonical for qid in qids if qid != canonical})

    reviews = []
    for qid, stages in sorted(groups.items()):
        issues: list[str] = []
        question = questions.get(qid, "")
        question_locator = locators.get(qid, {})
        if qid in duplicate_of:
            issues.append("duplicate_question_crop")
        if question_pdf_checksums is not None:
            if question_locator.get("source_checksum") not in question_pdf_checksums:
                issues.append("question_pdf_unavailable_for_crop_review")
            if not question_locator.get("bbox"):
                issues.append("question_crop_coordinates_missing")
        if not question:
            issues.append("question_transcription_missing")
        elif len(question) > 1100:
            issues.append("spoken_question_too_long")
        if visual_scope.get(qid) or visual_cue_in_text(question):
            issues.append("visual_question_out_of_scope")
        if NON_HISTORY_RE.search(question):
            issues.append("question_domain_not_history")
        if set(stages) != set(CASES) or any(value is None for value in stages.values()):
            issues.append("six_complete_unique_stages_required")
        records = [stages[case] for case in CASES if stages.get(case) is not None]
        quotes: list[str] = []
        source_ids: set[str] = set()
        for record in records:
            response = str(record.get("guide_response", record.get("coach_response", ""))).strip()
            if not response:
                issues.append("empty_coach_response")
            if any(phrase in response.casefold() for phrase in NON_PEDAGOGICAL_PHRASES):
                issues.append("non_pedagogical_template")
            if record.get("early_answer_disclosed") is True or record.get("answer_revealed") is True:
                issues.append("declared_early_answer_leak")
            case = CASE_ALIASES.get(record.get("case", record.get("stage")), record.get("case", record.get("stage")))
            if case in EARLY_ANSWER_CASES and ANSWER_LEAK_RE.search(response):
                issues.append("detected_early_answer_leak")
            source_evidence = record.get("source_evidence", [])
            evidence = record.get("evidence_quotes") or [item.get("excerpt", item.get("quote", "")) for item in source_evidence]
            min_evidence = 0 if case in CASES[:2] else 1
            if not min_evidence <= len(evidence) <= 2:
                issues.append("invalid_evidence_count")
            record_source_ids = record.get("source_ids") or [item.get("source_id") for item in source_evidence]
            if len(record_source_ids) != len(evidence) or any(not isinstance(value, str) or not value.strip() for value in record_source_ids):
                issues.append("invalid_source_binding")
            else:
                source_ids.update(record_source_ids)
                if corpus_sources is not None:
                    for source_id, quote in zip(record_source_ids, evidence):
                        if source_id not in corpus_sources:
                            issues.append("source_id_missing_from_corpus")
                        elif _clean(str(quote)) not in _clean(corpus_sources[source_id]):
                            issues.append("quote_missing_from_corpus_source")
            if source_evidence and (len(source_evidence) != len(evidence) or any(
                _clean(str(item.get("excerpt", item.get("quote", "")))) != _clean(str(quote))
                for item, quote in zip(source_evidence, evidence)
            )):
                issues.append("source_quote_mismatch")
            for quote in evidence:
                if not isinstance(quote, str) or not quote.strip() or len(quote) > 520:
                    issues.append("invalid_evidence_quote")
                else:
                    quotes.append(_clean(quote))
        question_terms = _terms(question)
        evidence_terms = _terms(" ".join(quotes))
        overlap = sorted(question_terms & evidence_terms)
        # Overlap helps prioritize review; it cannot prove a historical relation.
        if len(overlap) < 2:
            issues.append("low_lexical_overlap")
        if any(OCR_BREAK_RE.search(value) for value in quotes):
            issues.append("possible_source_ocr_break")
        blocking = set(issues) - {"low_lexical_overlap", "possible_source_ocr_break"}
        status = "rejected" if blocking else "semantic_review_required"
        reviews.append({
            "question_id": qid,
            "status": status,
            "mechanically_valid": not blocking,
            "training_eligible": False,
            "issues": sorted(set(issues)),
            "question_text": question,
            "question_locator": question_locator,
            "duplicate_of": duplicate_of.get(qid),
            "source_ids": sorted(source_ids),
            "source_locators": {source_id: source_locators.get(source_id)
                                for source_id in sorted(source_ids)},
            "evidence_quotes": list(dict.fromkeys(quotes)),
            "stage_responses": [
                {"stage": stage,
                 "coach_response": str(record.get("guide_response", record.get("coach_response", ""))).strip(),
                 "source_ids": record.get("source_ids") or [
                     item.get("source_id") for item in record.get("source_evidence", [])
                 ]}
                for stage, record in ((case, stages.get(case)) for case in CASES)
                if record is not None
            ],
            "question_term_count": len(question_terms),
            "evidence_term_count": len(evidence_terms),
            "overlap_terms": overlap[:24],
            "provenance": sorted(set(group_provenance[qid])),
        })
    return {
        "schema": "teacher-coaching-group-quality-audit-v2",
        "answer_keys_included": False,
        "worked_explanations_included": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "corpus_source_checked": corpus_sources is not None,
        "question_pdf_checked": question_pdf_checksums is not None,
        "notice": "Private review queue. Lexical overlap is not source support. PDF crop and semantic relation must be checked before training.",
        "question_groups": len(reviews),
        "status_counts": dict(Counter(row["status"] for row in reviews)),
        "reviews": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, action="append", required=True)
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--question-candidates", type=Path, action="append", default=[])
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--question-pdf", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = audit([load(path) for path in args.draft], load(args.transcriptions),
                   [load(path) for path in args.question_candidates],
                   load(args.corpus) if args.corpus else None,
                   {hashlib.sha256(path.read_bytes()).hexdigest() for path in args.question_pdf}
                   if args.question_pdf else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "reviews"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
