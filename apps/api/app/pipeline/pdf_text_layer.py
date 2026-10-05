"""PDF metin katmanından güvenli, kaynak-koordinatlı ara gösterim çıkarır.

Bu modül OCR veya model çağrısı yapmaz. Metin katmanı yoksa boş sonuç döner;
çağıran iş bunu OCR benchmark/fallback kuyruğuna yönlendirmelidir.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 300


class PdfSafetyError(ValueError):
    """Kaynak, işlem güvenlik sınırını karşılamadığında yükseltilir."""


@dataclass(frozen=True)
class SourceCoordinate:
    page: int
    bbox: tuple[float, float, float, float]
    source_checksum: str
    extraction_step: str = "pdf-text-layer"


@dataclass(frozen=True)
class ExtractedBlock:
    id: str
    kind: str
    reading_order: int
    text: str
    source: SourceCoordinate


@dataclass(frozen=True)
class ExtractedDocument:
    source_checksum: str
    page_count: int
    blocks: list[ExtractedBlock]

    def to_dict(self) -> dict:
        return asdict(self)


def _within_root(path: Path, source_root: Path) -> Path:
    resolved_path = path.resolve(strict=True)
    resolved_root = source_root.resolve(strict=True)
    if not resolved_path.is_relative_to(resolved_root):
        raise PdfSafetyError("Kaynak dosya izinli yerel kaynak dizininin dışında")
    return resolved_path


def _read_and_validate(path: Path, source_root: Path) -> tuple[Path, bytes]:
    safe_path = _within_root(path, source_root)
    if safe_path.suffix.lower() != ".pdf":
        raise PdfSafetyError("Yalnızca PDF uzantılı kaynak işlenebilir")
    size = safe_path.stat().st_size
    if size == 0 or size > MAX_BYTES:
        raise PdfSafetyError(f"PDF boyutu 1 byte ile {MAX_BYTES} byte arasında olmalı")
    content = safe_path.read_bytes()
    if not content.startswith(b"%PDF-"):
        raise PdfSafetyError("Dosyanın magic-byte değeri PDF değil")
    return safe_path, content


def extract_text_layer(path: Path, source_root: Path) -> ExtractedDocument:
    """İzinli bir yerel PDF'den metin bloklarını ve koordinatlarını çıkarır."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        pdf = pymupdf.open(stream=content, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise PdfSafetyError("PDF ayrıştırılamadı") from exc

    with pdf:
        if pdf.is_encrypted:
            raise PdfSafetyError("Şifreli PDF işlenmez; yetkili kullanıcıdan şifresiz kaynak istenir")
        if pdf.page_count < 1 or pdf.page_count > MAX_PAGES:
            raise PdfSafetyError(f"PDF sayfa sayısı 1 ile {MAX_PAGES} arasında olmalı")
        page_count = pdf.page_count
        blocks: list[ExtractedBlock] = []
        order = 0
        for page_index, page in enumerate(pdf, start=1):
            raw_blocks = page.get_text("blocks", sort=True)
            for x0, y0, x1, y1, text, *_ in raw_blocks:
                normalized = " ".join(text.split())
                if not normalized or x0 >= x1 or y0 >= y1:
                    continue
                order += 1
                blocks.append(
                    ExtractedBlock(
                        id=f"p{page_index}-b{order}",
                        kind="paragraph",
                        reading_order=order,
                        text=normalized,
                        source=SourceCoordinate(
                            page=page_index,
                            bbox=(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)),
                            source_checksum=checksum,
                        ),
                    )
                )
    return ExtractedDocument(source_checksum=checksum, page_count=page_count, blocks=blocks)
