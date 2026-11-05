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
NUMBERED_SUMMARY_SECTION = re.compile(r"^(\d{1,3})\.\s+(.+?)\s*\.{3,}\s*(\d{1,3})\s*$")
SECTION_WITH_SUBPAGE = re.compile(r"^(\d)\.(\d)\.\d+\.\s+.+?\.{3,}\s*(\d{1,3})\s*$")
SECTION_WITHOUT_PAGE = re.compile(r"^(\d)\.(\d)\.\s+(.+?)\s*$")
# Some current MEB TOCs prefix this with ``1. Ünite`` and suffix it with
# ``Soruları``.  The dotted leader/page number keeps this deliberately tied
# to a TOC row rather than prose in the opening pages.
ASSESSMENT = re.compile(
    r"^(?=.*\bölçme\b)(?=.*\bdeğerlendirme\b).*?\.{3,}\s*(\d{1,3})\s*$", re.IGNORECASE
)
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


def _word_toc_sections(pdf) -> list[dict]:
    """Recover TOC rows whose title and page number are separate PDF blocks.

    Certain MEB exports place the right-aligned page number in another text
    block.  Reading blocks alone then yields a valid heading with no page
    number.  This geometry-based recovery only accepts top-level ``1.2.``
    forms plus a same-row, in-range page number, so lesson headings later in
    the PDF cannot be mistaken for a TOC row.
    """
    recovered = []
    for page_number in range(min(15, pdf.page_count)):
        words = pdf[page_number].get_text("words")
        for x0, y0, _x1, _y1, word, *_ in words:
            match = re.fullmatch(r"(\d)\.(\d)\.", word)
            if not match:
                continue
            row = sorted((item for item in words if abs(item[1] - y0) <= 1.5 and item[0] >= x0 - 1),
                         key=lambda item: item[0])
            start = next((index for index, item in enumerate(row) if item[4] == word and abs(item[0] - x0) <= 1), None)
            if start is None:
                continue
            numeric = [index for index, item in enumerate(row[start + 1:], start + 1)
                       if item[4].isdigit() and 1 <= int(item[4]) <= pdf.page_count]
            if not numeric:
                continue
            page_index = numeric[-1]
            title_words = [item[4] for item in row[start + 1:page_index]
                           if not re.fullmatch(r"\.{3,}", item[4])]
            title = _clean(" ".join(title_words))
            if len(title) < 4:
                continue
            recovered.append({"id": f"{match[1]}.{match[2]}", "title": title,
                              "start": int(row[page_index][4])})
    return recovered


def sections(pdf) -> list[dict]:
    # The 9th-grade pilot kept a page cap for its three units.  That made a
    # later textbook silently impossible to index.  Parse the whole front
    # matter instead: real TOC entries carry dotted leaders and a page number,
    # while lesson headings do not.
    toc = []
    for page_number in range(min(15, pdf.page_count)):
        # ``get_text()`` can return visually separate TOC blocks in tagged-PDF
        # order (1, 3, 2).  Blocks retain their own line/page-number pairing;
        # sorting them by geometry restores the reading sequence and works for
        # both one-column and multi-column MEB layouts.
        blocks = [block for block in pdf[page_number].get_text("blocks") if len(block) >= 5]
        for block in sorted(blocks, key=lambda item: (item[1], item[0])):
            toc.extend(block[4].splitlines())
    # Long 11th-grade section names sometimes wrap before their dotted leader
    # and page number. Join only a root row with its prose continuation; never
    # join it to a numbered child heading.
    joined_toc = []
    for raw_line in toc:
        normalized_line = re.sub(r"\s+", " ", raw_line).strip()
        previous = joined_toc[-1] if joined_toc else ""
        previous_compact = re.sub(r"^(\d)\.\s+(\d)\.", r"\1.\2.", previous)
        root_without_page = (SECTION_WITHOUT_PAGE.match(previous_compact)
                             if not re.search(r"\d{1,3}\s*$", previous_compact) else None)
        if (root_without_page and normalized_line
                and not re.match(r"^\d\.\d\.\d+\.", normalized_line)):
            combined = f"{previous} {normalized_line}"
            compact = re.sub(r"\s+", " ", combined).strip()
            if SECTION.match(re.sub(r"^(\d)\.\s+(\d)\.", r"\1.\2.", compact)):
                joined_toc[-1] = compact
                continue
        joined_toc.append(raw_line)
    toc = joined_toc
    result = []
    pending_sections: dict[str, str] = {}
    assessment_pages = []
    for line in toc:
        normalized = re.sub(r"\s+", " ", line).strip()
        # A few rows encode ``5. 1.`` rather than ``5.1.``.  Normalize only
        # the section prefix, preserving title dates such as ``20. Yüzyıl``.
        normalized = re.sub(r"^(\d)\.\s+(\d)\.", r"\1.\2.", normalized)
        match = SECTION.match(normalized)
        if match:
            result.append({"id": f"{match[1]}.{match[2]}", "title": match[3].strip(),
                           "start": int(match[4])})
            pending_sections.pop(f"{match[1]}.{match[2]}", None)
        else:
            # Wrapped headings occasionally put the page number only on the
            # first child row.  We retain the root title temporarily, then
            # use that child's printed start page.  No page means no section.
            root = SECTION_WITHOUT_PAGE.match(normalized)
            if root and not re.match(r"^\d\.\d\.\d+\.", normalized):
                pending_sections[f"{root[1]}.{root[2]}"] = root[3].rstrip(". ")
            child = SECTION_WITH_SUBPAGE.match(normalized)
            if child:
                section_id = f"{child[1]}.{child[2]}"
                if section_id in pending_sections:
                    result.append({"id": section_id, "title": pending_sections.pop(section_id),
                                   "start": int(child[3])})
        assessment = ASSESSMENT.match(normalized)
        if assessment:
            assessment_pages.append(int(assessment[1]))
    # Geometry recovery augments ordinary text parsing for rows whose page
    # number was split into a separate PDF block.
    result.extend(_word_toc_sections(pdf))
    # MEBİ konu özetleri use a flat, numbered table of contents (``1. Başlık``)
    # rather than the textbook's hierarchical ``1.2. Başlık`` form.  These
    # rows retain dotted leaders and an in-range page number, so accepting
    # them here remains tied to the front-matter TOC rather than lesson prose.
    summary_candidates = []
    for line in toc:
        normalized = re.sub(r"\s+", " ", line).strip()
        match = NUMBERED_SUMMARY_SECTION.match(normalized)
        if match and not re.match(r"^\d+\.", match[2]):
            summary_candidates.append({"id": f"summary.{match[1]}", "title": match[2].strip(),
                                       "start": int(match[3])})
    # On some tagged summary PDFs a row's number is emitted as a separate
    # line, while the title and its page number remain in the same visual
    # block.  Reassemble that *single block* only; joining neighbouring lines
    # would risk inventing a section boundary in ordinary textbook prose.
    for page_number in range(min(15, pdf.page_count)):
        for block in pdf[page_number].get_text("blocks"):
            if len(block) < 5:
                continue
            normalized = re.sub(r"\s+", " ", block[4]).strip()
            match = NUMBERED_SUMMARY_SECTION.match(normalized)
            if match and not re.match(r"^\d+\.", match[2]):
                summary_candidates.append({"id": f"summary.{match[1]}", "title": match[2].strip(),
                                           "start": int(match[3])})
    # A textbook can have isolated flat entries such as ``1. Ünite Ölçme``.
    # A true MEBİ summary has a long flat TOC.  Require that structural signal
    # before treating the pattern as a separate source format.
    if len({item["id"] for item in summary_candidates}) >= 10:
        result.extend(summary_candidates)
    summary_sections = [item for item in result if item["id"].startswith("summary.")]
    if summary_sections:
        # The printed page number in this source starts after its front matter.
        # Locate the first real heading (rather than assuming an offset) and
        # convert all TOC page numbers to physical PDF pages.  Without this,
        # the first topic would silently index the table of contents itself.
        first_summary = min(summary_sections, key=lambda item: item["start"])
        needle = fold(first_summary["title"])
        physical_start = next(
            (page_number + 1 for page_number in range(min(10, pdf.page_count), pdf.page_count)
             if needle in fold(pdf[page_number].get_text())),
            None,
        )
        if physical_start is None:
            raise ValueError("Konu özeti sayfa eşlemesi doğrulanamadı")
        offset = physical_start - first_summary["start"]
        for item in summary_sections:
            item["start"] += offset
    if len(result) < 3:
        # Last-resort recovery for a short or unusually formatted textbook.
        # A valid book can have fewer than ten sections, so the former pilot
        # threshold would throw away good entries from small future sources.
        result = []
        for page_number in range(min(15, pdf.page_count)):
            lines = [_clean(line) for line in pdf[page_number].get_text().splitlines()]
            for index, line in enumerate(lines):
                match = re.match(r"^(\d)\.(\d)\.\s+(.+?)\s*\.{2,}\s*(\d{1,3})$", line)
                if match:
                    result.append({"id": f"{match[1]}.{match[2]}", "title": match[3].strip(),
                                   "start": int(match[4])})
        if len(result) < 3:
            raise ValueError("MEB içindekiler bölüm başlangıçları doğrulanamadı")
    # Text-layer rows are preferred over geometry recovery when both exist;
    # geometry is strictly a repair path for rows whose page number was split
    # into a separate PDF block.
    unique: dict[str, dict] = {}
    for item in result:
        unique.setdefault(item["id"], item)
    result = sorted(unique.values(), key=lambda item: item["start"])
    for index, item in enumerate(result):
        next_section = result[index + 1]["start"] - 1 if index + 1 < len(result) else pdf.page_count
        next_assessment = next((page - 1 for page in assessment_pages if page > item["start"]), None)
        # Assessment pages are excluded from candidate extraction even when a
        # unit has no following numbered subsection.  If the TOC lacks an
        # assessment entry, retain the conservative next-section/document end.
        item["end"] = min(next_section, next_assessment) if next_assessment else next_section
    return result


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xad", "").replace("\xa0", " ")).strip()


def _candidate(text: str, bbox: list[float], page_height: float) -> bool:
    if bbox[1] < 43 or bbox[3] > page_height - 42:
        return False
    if not 105 <= len(text) <= 2000 or len(terms(text)) < 12:
        return False
    # Textbook source quotations can carry the only direct wording for a
    # historical relation. They enter the manual-review queue below; they are
    # never automatically treated as student evidence.
    if EXCLUDE.match(text) or text.startswith("("):
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
    # Whitespace alone cannot identify OCR corruption reliably in Turkish:
    # legitimate suffixes and word starts create the same pattern.  Keep OCR
    # diagnosis for line-aware audits; do not penalize source eligibility here.
    ocr = False
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


_EXPLANATORY = re.compile(
    r"(?:sağladı|etkiledi|gelişti|oluşturdu|ortaya çıktı|yaygınlaştı|kuruldu|değişti|sonucunda|nedeniyle)", re.IGNORECASE
)


def block_layout(lines: list[str]) -> dict:
    """Stable PDF-layout features used by the document-type policy.

    The values describe structure, never historical correctness; retaining them
    makes a later model or a different textbook policy auditable.
    """
    clean = [line.strip() for line in lines if line.strip()]
    word_counts = [len(terms(line)) for line in clean]
    return {"line_count": len(clean),
            "mean_terms_per_line": round(sum(word_counts) / max(1, len(word_counts)), 2),
            "short_line_ratio": round(sum(count <= 10 for count in word_counts) / max(1, len(word_counts)), 2),
            "has_ellipsis_line": any(re.fullmatch(r"[.()… ]+", line) for line in clean),
            "first_line_is_title": bool(clean and not re.search(r"[.!?;:]", clean[0]) and len(terms(clean[0])) <= 8),
            "terminal_line_ratio": round(sum(line.endswith((".", "!", "?")) for line in clean) / max(1, len(clean)), 2)}


def source_review_recommendation(text: str, layout: dict | None = None) -> dict:
    """Conservative cross-book pre-review based on document type and quality.

    `do_not_use` is deliberately reserved for high-precision document types.
    Ambiguous prose stays visible to the teacher rather than being silently lost.
    """
    quality = chunk_quality(text)
    layout = layout or {}
    poetic_layout = (layout.get("line_count", 0) >= 4 and layout.get("mean_terms_per_line", 99) <= 10
                     and layout.get("short_line_ratio", 0) >= .75
                     and layout.get("has_ellipsis_line"))
    if poetic_layout:
        return {"decision": "do_not_use", "confidence": "high",
                "explanation": "Kısa dizeler, başlık ve satır düzeni edebî alıntı biçimine uyuyor; doğrudan ders kanıtı değildir.",
                "reasons": ["edebi_alinti_yapisi"], "features": layout}
    if quality["visual_or_caption_risk"]:
        return {"decision": "do_not_use", "confidence": "high",
                "explanation": "Görsel veya eser açıklaması olabilir; soru kanıtı olarak tek başına kullanılmaz.",
                "reasons": ["gorsel_aciklamasi"], "features": layout}
    if quality["instruction_risk"]:
        return {"decision": "do_not_use", "confidence": "high",
                "explanation": "Etkinlik yönergesi olabilir; ders bilgisini doğrudan kanıtlamaz.",
                "reasons": ["etkinlik_yonergesi"], "features": layout}
    if quality["ocr_fragment_risk"]:
        return {"decision": "manual_review", "confidence": "low",
                "explanation": "PDF metninde bölünmüş sözcük riski var; PDF kırpımıyla anlamı doğrulanmadan kullanmayın.",
                "reasons": ["ocr_bozulmasi"], "features": layout}
    if text.startswith(("“", '"')):
        return {"decision": "manual_review", "confidence": "medium",
                "explanation": "Ders kitabındaki kaynak alıntısı olabilir; bağlamı ve PDF kırpımı doğrulanmadan ders kanıtı sayılmaz.",
                "reasons": ["kaynak_alintisi_baglam_kontrolu"], "source_type": "quoted_source",
                "features": layout}
    if _EXPLANATORY.search(text) and quality["word_count"] >= 6:
        return {"decision": "review_for_approval", "confidence": "medium",
                "explanation": "Neden-sonuç veya tarihsel açıklama içeriyor gibi görünüyor; PDF ile aynıysa ders kanıtı olarak uygun olabilir.",
                "reasons": ["ders_bilgisi_adayi"], "features": layout}
    return {"decision": "manual_review", "confidence": "low",
            "explanation": "Metin ders bilgisi olabilir; ancak tek başına doğrudan kanıt olup olmadığı PDF bağlamında net değil.",
            "reasons": ["baglam_kontrolu_gerekli"], "features": layout}

def build_index(source: Path = BOOK) -> dict:
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    chunks = []
    exclusions: dict[str, int] = {}
    with pymupdf.open(source) as pdf:
        chapter = sections(pdf)
        for section in chapter:
            for page_number in range(section["start"], min(section["end"], pdf.page_count) + 1):
                page = pdf[page_number - 1]
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    raw_lines = ["".join(span["text"] for span in line["spans"])
                                 for line in block["lines"]]
                    text = _clean(" ".join(raw_lines))
                    layout = block_layout(raw_lines)
                    box = [round(float(n), 2) for n in block["bbox"]]
                    if not _candidate(text, box, page.rect.height):
                        continue
                    pre_review = source_review_recommendation(text, layout)
                    # Obvious non-evidence must not consume teacher review time.
                    # Keep only conservative uncertainty and lesson-prose candidates.
                    if pre_review["decision"] == "do_not_use":
                        exclusions[pre_review["reasons"][0]] = exclusions.get(pre_review["reasons"][0], 0) + 1
                        continue
                    key = f"{checksum}:{page_number}:{box}:{text}"
                    chunks.append({"id": hashlib.sha256(key.encode()).hexdigest()[:20],
                                   "section_id": section["id"], "section_title": section["title"],
                                   "page": page_number, "bbox": box, "text": text,
                                   "review_status": "candidate", "quality": chunk_quality(text),
                                   "layout": layout, "pre_review": pre_review})
    return {"schema": 1, "policy_version": "source-type-v3", "source_checksum": checksum, "source_name": source.name,
            "sections": chapter, "chunks": chunks, "exclusions": exclusions}


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


class PreparedBM25:
    """Index one authorized corpus once; reuse its IDF for every question."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.documents = [Counter(terms(item["text"])) for item in chunks]
        self.frequencies = Counter(word for doc in self.documents for word in doc)
        self.lengths = [sum(doc.values()) for doc in self.documents]
        self.average = sum(self.lengths) / len(chunks) if chunks else 0

    def rank(self, query: str, limit: int = 3) -> list[dict]:
        if not self.chunks or limit < 1 or not self.average:
            return []
        query_terms = set(terms(query))
        ranked = []
        for item, doc, length in zip(self.chunks, self.documents, self.lengths):
            score = 0.0
            for word in query_terms & doc.keys():
                idf = math.log(1 + (len(self.chunks) - self.frequencies[word] + 0.5)
                               / (self.frequencies[word] + 0.5))
                score += idf * doc[word] * 2.2 / (
                    doc[word] + 1.2 * (0.25 + 0.75 * length / self.average))
            if score > 0:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["page"], pair[1]["id"]))
        return [{**item, "score": round(score, 3)} for score, item in ranked[:limit]]


def rank_chunks(chunks: list[dict], query: str, limit: int = 3) -> list[dict]:
    """BM25 ranking over an explicitly supplied, already-authorized corpus."""
    return PreparedBM25(chunks).rank(query, limit)


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
_OCR_FRAGMENT = re.compile(r"\b\w{3,}\s+[a-zçğıöşü]{1,2}\w{2,}\b", re.IGNORECASE)
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
