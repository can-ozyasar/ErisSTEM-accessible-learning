"""Çıkarılmış metin katmanını öğretmen denetimli belge taslağına dönüştürür."""

from __future__ import annotations

import hashlib
import re

from .pdf_text_layer import ExtractedDocument


def looks_like_fragmented_math(text: str) -> bool:
    """Route broken math glyph fragments away from the normal prose editor."""
    compact = "".join(text.split())
    tokens = text.split()
    numeric_tokens = sum(bool(re.fullmatch(r"[-−+]?\d+(?:[.,]\d+)?", token)) for token in tokens)
    letters = sum(character.isalpha() for character in compact)
    formula_marks = set("=<>√^_$/\\{}[]()×÷·+-−")
    return (
        bool(set(compact) & formula_marks) and numeric_tokens >= 2 and letters <= 2
    ) or (len(tokens) >= 3 and numeric_tokens >= 3 and letters == 0)


def draft_from_text_layer(
    result: ExtractedDocument, title: str, selected_pages: str = "all"
) -> dict:
    """İş kapsamını belge kimliğine dahil ederek farklı pilotları ayırır."""
    scope_suffix = (
        ""
        if selected_pages == "all"
        else f"-{hashlib.sha256(selected_pages.encode()).hexdigest()[:12]}"
    )
    return {
        "id": f"source-{result.source_checksum[:16]}{scope_suffix}",
        "title": title,
        "license_notice": "Yerel yetkili kaynak taslağıdır; öğretmen onayı olmadan yayımlanmaz.",
        "published_revision": 0,
        "blocks": [
            {
                "id": block.id,
                "kind": "formula-display" if looks_like_fragmented_math(block.text) else block.kind,
                "reading_order": block.reading_order,
                "source": {
                    "page": block.source.page,
                    "bbox": block.source.bbox,
                    "source_checksum": block.source.source_checksum,
                    "extraction_step": block.source.extraction_step,
                },
                "validation": {
                    "schema_passed": True,
                    "render_score": 1.0,
                    "source_agreement": 1.0,
                    "confidence": 0.0 if looks_like_fragmented_math(block.text) else 0.85,
                    "reasons": (
                        ["Bozuk matematiksel PDF parçası; görsel formül tanıma ve öğretmen denetimi gerekli."]
                        if looks_like_fragmented_math(block.text)
                        else ["Metin katmanı çıkarımı; öğretmen denetimi gerekli."]
                    ),
                },
                "text": None if looks_like_fragmented_math(block.text) else block.text,
                "status": "review_required",
                "revision": 1,
            }
            for block in result.blocks
        ],
    }
