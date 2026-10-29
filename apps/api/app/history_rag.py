"""Offline, review-gated retrieval from the local MEB history textbook.

Candidates are deliberately narrow: lesson prose in a numbered TOC section.
Coordinates and the source hash make every approval invalid after a PDF edit.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

import pymupdf

from .history_source import BOOK

INDEX_PATH = Path(os.getenv("HISTORY_RAG_INDEX", "/private/derived/history-rag-v1.json"))
SECTION = re.compile(r"^(\d)\.(\d)\.\s+(.+?)\s*\.{3,}\s*(\d{1,3})\s*$")
TOKENS = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
STOP = {"ve", "veya", "ile", "bir", "bu", "da", "de", "için", "olan", "olarak",
        "tarih", "tarihi", "tarihin", "hangi", "aşağıdaki", "göre", "ise", "en", "ne"}
EXCLUDE = re.compile(
    r"^(?:Kaynak\s+[A-ZÇĞİÖŞÜ]\b|Görsel\s+\d|Tablo\s+\d|Öğrencinin|Numarası|"
    r"Aşağıda|Aşağıdaki|Yukarıda|Yandaki|Verilen|İnceleyiniz|Uygulayalım|"
    r"Değerlendirelim|Keşfedelim|Ölçme|Zenginleştirme|Öz Değerlendirme|"
    r"\d+[.)]\s|[A-E][.)]\s|•|\.{3,})", re.IGNORECASE)
ACTIVITY = re.compile(
    r"(?:aşağıdaki|yukarıdaki|yandaki|verilen|verilenleri|incelediğiniz|"
    r"sınıf arkadaşlarınız|tablonun ilgili|karekodda|cevaplayınız|yazınız|"
    r"işaretleyiniz|hazırlayınız|karşılaştırınız|tartışınız|etkinliği yapınız)", re.IGNORECASE)


def fold(value: str) -> str:
    return value.translate(str.maketrans("Iİ", "ıi")).casefold()


def terms(value: str) -> list[str]:
    return [word for word in TOKENS.findall(fold(value)) if len(word) > 2 and word not in STOP]


def sections(pdf) -> list[dict]:
    toc = pdf[6].get_text().splitlines()
    result = []
    for line in toc:
        match = SECTION.match(re.sub(r"\s+", " ", line).strip())
        if match:
            result.append({"id": f"{match[1]}.{match[2]}", "title": match[3].strip(),
                           "start": int(match[4])})
    if len(result) < 10:
        raise ValueError("MEB içindekiler bölüm başlangıçları doğrulanamadı")
    for index, item in enumerate(result):
        item["end"] = result[index + 1]["start"] - 1 if index + 1 < len(result) else 243
        item["end"] = min(item["end"], {"1": 60, "2": 154, "3": 243}[item["id"][0]])
    return result


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xad", "").replace("\xa0", " ")).strip()


def _candidate(text: str, bbox: list[float], page_height: float) -> bool:
    if bbox[1] < 43 or bbox[3] > page_height - 42:
        return False
    if not 105 <= len(text) <= 2000 or len(terms(text)) < 12:
        return False
    if EXCLUDE.match(text) or text.startswith(("“", '"', "(")):
        return False
    if ACTIVITY.search(text):
        return False
    if text.count("?") or text.count("_") > 2 or text.count("...") > 1:
        return False
    return len(re.findall(r"\b(?:Kaynak|Görsel|Tablo)\s+[A-Z0-9]", text)) <= 1


# These indicators are review aids, not a classifier or proof of factuality.
# Leave existing source identities and teacher decisions intact.
_REVIEW_INSTRUCTION = re.compile(
    r"(?:\b(?:[IVX]+|\d+)\.\s*Adım\s*:|"
    r"rol\s+oynama\s+etkinliğ|uygulama\s+adımlarını|"
    r"(?:soruları|soruyu)\s+cevap\s*layınız|"
    r"sırala\s*yınız|(?:canlandırmaları|izleyenler\s+grubuna).{0,80}sağlatılır)",
    re.IGNORECASE,
)
_REVIEW_CAPTION = re.compile(
    r"(?:\bArkeoloji.{0,30}Müzesi\b|\bMuseum\b|"
    r"\b(?:mezardan\s+çıkarılan|modeli?\s*\(yaklaşık))", re.IGNORECASE
)


def chunk_quality(text: str) -> dict:
    """Explainable PDF quality metadata. It is a review aid, never approval."""
    warnings = candidate_review_warnings(text)
    ocr = bool(_OCR_FRAGMENT.search(text)) if "_OCR_FRAGMENT" in globals() else False
    caption = bool(_CAPTIONISH.search(text)) if "_CAPTIONISH" in globals() else False
    return {"text_quality": "review_required" if warnings or ocr or caption else "clean",
            "visual_or_caption_risk": caption or "gorsel_aciklama_olabilir" in warnings,
            "instruction_risk": "etkinlik_yonergesi_olabilir" in warnings,
            "ocr_fragment_risk": ocr, "warnings": warnings, "word_count": len(terms(text))}


def candidate_review_warnings(text: str) -> list[str]:
    """Flag likely non-lesson material for manual review, without filtering it."""
    warnings = []
    if _REVIEW_INSTRUCTION.search(text):
        warnings.append("etkinlik_yonergesi_olabilir")
    if _REVIEW_CAPTION.search(text):
        warnings.append("gorsel_aciklama_olabilir")
    return warnings


def build_index(source: Path = BOOK) -> dict:
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    chunks = []
    with pymupdf.open(source) as pdf:
        chapter = sections(pdf)
        for section in chapter:
            for page_number in range(section["start"], min(section["end"], pdf.page_count) + 1):
                page = pdf[page_number - 1]
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    text = _clean(" ".join("".join(span["text"] for span in line["spans"])
                                           for line in block["lines"]))
                    box = [round(float(n), 2) for n in block["bbox"]]
                    if not _candidate(text, box, page.rect.height):
                        continue
                    key = f"{checksum}:{page_number}:{box}:{text}"
                    chunks.append({"id": hashlib.sha256(key.encode()).hexdigest()[:20],
                                   "section_id": section["id"], "section_title": section["title"],
                                   "page": page_number, "bbox": box, "text": text,
                                   "review_status": "candidate", "quality": chunk_quality(text)})
    return {"schema": 1, "source_checksum": checksum, "source_name": source.name,
            "sections": chapter, "chunks": chunks}


def write_index(source: Path = BOOK, destination: Path = INDEX_PATH) -> dict:
    index = build_index(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination)
    return index


def deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    """Collapse exact duplicates while rejecting ambiguous identities."""
    unique: dict[str, dict] = {}
    for item in chunks:
        chunk_id = item["id"]
        if chunk_id in unique and unique[chunk_id] != item:
            raise ValueError("RAG dizininde çakışan parça kimliği var")
        unique.setdefault(chunk_id, item)
    return list(unique.values())


def load_index(source: Path = BOOK, destination: Path = INDEX_PATH) -> dict:
    if not destination.is_file() or not source.is_file():
        raise FileNotFoundError("RAG dizini oluşturulmadı")
    index = json.loads(destination.read_text(encoding="utf-8"))
    if index.get("schema") != 1 or index.get("source_checksum") != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError("RAG dizini kaynak PDF sürümüyle eşleşmiyor")
    index["chunks"] = deduplicate_chunks(index["chunks"])
    return index


def matching_sections(index: dict, topic: str | None) -> list[str]:
    if not topic or len(topic) > 180 or (topic == topic.upper() and len(topic) < 60):
        return []
    result = []
    for part in re.split(r"[,;]", topic):
        heading = fold(part).strip(" .")
        if not heading:
            continue
        exact = [section["id"] for section in index["sections"]
                 if fold(section["title"]).strip(" .") == heading]
        if exact:
            result.extend(exact)
            continue
        part_terms = set(terms(part))
        ranked = []
        for section in index["sections"]:
            section_terms = set(terms(section["title"]))
            common = len(part_terms & section_terms)
            coverage = common / max(1, min(len(part_terms), len(section_terms)))
            if common >= 2 and coverage >= 0.5:
                ranked.append((coverage, common, section["id"]))
        if ranked:
            best = max(ranked)
            result.extend(item[2] for item in ranked if item[:2] == best[:2])
    return list(dict.fromkeys(result))


def rank_chunks(chunks: list[dict], query: str, limit: int = 3) -> list[dict]:
    """BM25 ranking over an explicitly supplied, already-authorized corpus."""
    if not chunks or limit < 1:
        return []
    query_terms = set(terms(query))
    documents = [Counter(terms(item["text"])) for item in chunks]
    frequencies = Counter(word for doc in documents for word in doc)
    average = sum(sum(doc.values()) for doc in documents) / len(documents)
    ranked = []
    for item, doc in zip(chunks, documents):
        length = sum(doc.values())
        score = 0.0
        for word in query_terms & doc.keys():
            idf = math.log(1 + (len(chunks) - frequencies[word] + 0.5) / (frequencies[word] + 0.5))
            score += idf * doc[word] * 2.2 / (doc[word] + 1.2 * (0.25 + 0.75 * length / average))
        if score > 0:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["page"], pair[1]["id"]))
    return [{**item, "score": round(score, 3)} for score, item in ranked[:limit]]


def retrieve(index: dict, approved_ids: set[str], topic: str | None, query: str,
             limit: int = 3) -> list[dict]:
    allowed = set(matching_sections(index, topic))
    corpus = [item for item in index["chunks"] if item["id"] in approved_ids
              and item["section_id"] in allowed]
    return rank_chunks(corpus, query, limit)


if __name__ == "__main__":
    result = write_index()
    print(json.dumps({"sections": len(result["sections"]), "candidates": len(result["chunks"]),
                      "source_checksum": result["source_checksum"]}, ensure_ascii=False))


# Evidence proposal is intentionally separate from production retrieval. It ranks
# unapproved PDF passages for a teacher to inspect; it never changes approval.
_OCR_FRAGMENT = re.compile(r"\b\w{4,}\s+[a-zçğıöşü]{1,2}\b", re.IGNORECASE)
_CAPTIONISH = re.compile(r"(?:museum|müzesi|görsel|fotoğraf|yaklaşık m[ös])", re.IGNORECASE)


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left))


def recommend_evidence(index: dict, question: str, choices: list[str], topic: str | None,
                       limit: int = 12, verified_choice: str | None = None) -> list[dict]:
    """Explainable multi-signal candidates for human evidence review.

    Signals are deliberately lexical and inspectable: question BM25, distinctive
    term coverage, choice coverage, title agreement and PDF text quality. This
    makes the proposal auditable before a teacher authorizes a passage.
    """
    if not question.strip() or limit < 1:
        return []
    query = " ".join([question, *choices])
    ranked = rank_chunks(index["chunks"], query, limit=len(index["chunks"]))
    if not ranked:
        return []
    raw_question = set(terms(question))
    raw_choices = set(terms(" ".join(choices)))
    verified_terms = set(terms(verified_choice or ""))
    # Distractors help find contrast passages, but cannot outweigh a verified
    # answer's terms in the teacher-only evidence selection path.
    signal_terms = raw_question | (verified_terms or raw_choices)
    docs = [set(terms(chunk["text"])) for chunk in index["chunks"]]
    df = Counter(term for doc in docs for term in doc)
    distinctive = {term for term in signal_terms if len(term) >= 5 and df[term] <= max(8, len(docs) // 12)}
    allowed_sections = set(matching_sections(index, topic))
    maximum = max(item["score"] for item in ranked) or 1.0
    candidates: list[dict] = []
    for item in ranked:
        text_terms = set(terms(item["text"]))
        bm25 = item["score"] / maximum
        entity = _overlap(distinctive, text_terms)
        question_coverage = _overlap(raw_question, text_terms)
        choice_coverage = _overlap(raw_choices, text_terms)
        verified_coverage = _overlap(verified_terms, text_terms) if verified_terms else 0.0
        title_terms = set(terms(item["section_title"]))
        title = _overlap(set(terms(topic or "")), title_terms)
        warnings = candidate_review_warnings(item["text"])
        ocr = bool(_OCR_FRAGMENT.search(item["text"]))
        caption = bool(_CAPTIONISH.search(item["text"]))
        quality_penalty = (0.12 if ocr else 0.0) + (0.20 if caption else 0.0) + (0.25 if warnings else 0.0)
        score = (0.34 * bm25 + 0.24 * entity + 0.15 * question_coverage +
                 0.05 * choice_coverage + 0.10 * title + 0.22 * verified_coverage)
        if item["section_id"] in allowed_sections:
            score += 0.06
        score -= quality_penalty
        reasons = []
        if entity: reasons.append("ayırt edici soru/şık terimi")
        if question_coverage >= 0.18: reasons.append("soru kökü kapsamı")
        if verified_coverage: reasons.append("doğrulanmış çözüm terimi (yalnız öğretmen seçimi)")
        elif choice_coverage >= 0.10: reasons.append("şık kapsamı")
        if title or item["section_id"] in allowed_sections: reasons.append("konu başlığı uyumu")
        if ocr: reasons.append("PDF metninde bölünmüş sözcük riski")
        if caption: reasons.append("görsel açıklaması riski")
        if warnings: reasons.extend(warnings)
        candidates.append({**item, "evidence_score": round(max(0.0, score), 4),
                           "signals": {"bm25": round(bm25, 4), "entity_coverage": round(entity, 4),
                                       "question_coverage": round(question_coverage, 4),
                                       "choice_coverage": round(choice_coverage, 4),
                                       "verified_choice_coverage": round(verified_coverage, 4),
                                       "title_coverage": round(title, 4), "quality_penalty": quality_penalty},
                           "reasons": reasons,
                           "review_recommendation": "review" if score >= 0.18 and not caption and not warnings else "do_not_use_yet"})
    candidates.sort(key=lambda item: (-item["evidence_score"], item["page"], item["id"]))
    # MMR-style de-duplication: prefer complementary passages, not copies of one paragraph.
    selected: list[dict] = []
    for item in candidates:
        source_terms = set(terms(item["text"]))
        redundant = max((_overlap(source_terms, set(terms(previous["text"]))) for previous in selected), default=0.0)
        if redundant > 0.82 and len(selected) < limit:
            continue
        selected.append(item)
        if len(selected) == limit:
            break
    return selected
