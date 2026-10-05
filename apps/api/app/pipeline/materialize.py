"""Çıkarılmış metin katmanını öğretmen denetimli belge taslağına dönüştürür."""

from __future__ import annotations

from .pdf_text_layer import ExtractedDocument


def draft_from_text_layer(result: ExtractedDocument, title: str) -> dict:
    return {
        "id": f"source-{result.source_checksum[:16]}",
        "title": title,
        "license_notice": "Yerel yetkili kaynak taslağıdır; öğretmen onayı olmadan yayımlanmaz.",
        "published_revision": 0,
        "blocks": [
            {
                "id": block.id,
                "kind": block.kind,
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
                    "confidence": 0.85,
                    "reasons": ["Metin katmanı çıkarımı; öğretmen denetimi gerekli."],
                },
                "text": block.text,
                "status": "review_required",
                "revision": 1,
            }
            for block in result.blocks
        ],
    }
