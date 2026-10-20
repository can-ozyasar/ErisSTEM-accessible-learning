"""Local, source-coordinate history-book reader.

The PDF text layer is evidence, not an image-description model.  Visual
regions deliberately expose their caption separately from their description.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .history_speech import history_spoken_text
from .local_tts import LocalTtsUnavailable, synthesize_history_text

BOOK = Path("/private/meb/tarih-9sinif-ders-kitabi_20261006.pdf")
TITLE = "Tarih 9. Sınıf Ders Kitabı (MEB, 2026)"
SOURCE_URL = "https://tymm.meb.gov.tr/kitap/43/tarih-9.sinif-ders-kitabi"

def _local_development_only():
    # The existing X-Role development header is not authentication.  Until
    # OIDC and source licensing are configured, these routes must stay local.
    if os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(503, "Tarih kaynağı üretim erişimine açılmadı")


router = APIRouter(prefix="/v1/history", tags=["history"],
                   dependencies=[Depends(_local_development_only)])


def _pdf():
    if not BOOK.is_file():
        raise HTTPException(503, "Resmî tarih kitabı sunucuda bulunamadı")
    return pymupdf.open(BOOK)


def _box(value):
    return [round(float(number), 2) for number in value]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xad", "")).strip()


def _join_lines(lines: list[str]) -> str:
    result = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if result.endswith("\xad") or (result.endswith("-") and line[:1].islower()):
            result = result[:-1] + line
        else:
            result += (" " if result else "") + line
    return _clean(result)


def _union(rects):
    return _box((min(r[0] for r in rects), min(r[1] for r in rects),
                 max(r[2] for r in rects), max(r[3] for r in rects)))


def _kind(text: str) -> str:
    if re.match(r"^Kaynak\s+[A-ZÇĞİÖŞÜ]$", text):
        return "source_label"
    if re.match(r"^\d+[.)]\s", text) or text.startswith("•"):
        return "question_or_instruction"
    if "Tarihsel bilginin üretim sürecine ilişkin tespitleriniz" in text:
        return "worksheet_label"
    if len(text) < 80 and (text.isupper() or "Ünite" in text):
        return "heading"
    if re.match(r"^.{2,35},\s*\d{4},\s*s\.", text):
        return "citation"
    return "paragraph"


def _text_regions(page):
    regions = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        groups = []
        current = []
        previous = None
        for line in block["lines"]:
            label = "".join(span["text"] for span in line["spans"])
            if not _clean(label):
                continue
            box = line["bbox"]
            # A PDF text block can cross columns or wrap around an image.
            split = previous and (abs(box[0] - previous[0]) > 65 or
                                  box[1] - previous[3] > 24 or
                                  bool(re.match(r"^\d+[.)]\s", label)) and bool(current))
            if split and current:
                groups.append(current)
                current = []
            current.append((box, label))
            previous = box
        if current:
            groups.append(current)
        block_regions = []
        for group in groups:
            text = _join_lines([line for _, line in group])
            if not text:
                continue
            box = _union([box for box, _ in group])
            # Page furniture is not part of lesson narration.
            if box[1] > page.rect.height - 48 or box[3] < 40:
                continue
            region = {"kind": _kind(text), "bbox": box, "text": text,
                            "spoken_text": text, "description": None,
                            "description_status": "not_applicable", "caption_id": None}
            regions.append(region)
            block_regions.append((region, group))
        # A wrapped paragraph may cross from beside a picture to full width.
        # Keep both hit boxes, but read the complete paragraph from either one.
        for index in range(len(block_regions) - 1):
            first, first_lines = block_regions[index]
            second, _ = block_regions[index + 1]
            tail = first_lines[-1][1].rstrip()
            if first["kind"] == second["kind"] == "paragraph" and tail.endswith(("\xad", "-")):
                joined = _join_lines([tail, second["text"]])
                joined = first["text"][:-len(_clean(tail))] + joined if len(_clean(tail)) < len(first["text"]) else joined
                first["spoken_text"] = second["spoken_text"] = joined
    return regions


def _horizontal_overlap(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0]))


def _visual_regions(page, text_regions):
    visuals = []
    images = [block for block in page.get_text("dict")["blocks"] if block["type"] == 1]
    for image in images:
        box = _box(image["bbox"])
        if (box[2] - box[0]) < 42 or (box[3] - box[1]) < 42:
            continue  # tiny icons/QRs need separate link handling, not "pictures"
        candidates = []
        for region in text_regions:
            other = region["bbox"]
            overlap = _horizontal_overlap(box, other)
            if overlap < min(box[2] - box[0], other[2] - other[0]) * 0.4:
                continue
            distance = other[1] - box[3]
            if -5 <= distance <= 35 and len(region["text"]) < 500:
                candidates.append((distance, region))
        caption = min(candidates, key=lambda item: item[0])[1] if candidates else None
        visuals.append({"kind": "visual", "bbox": box, "text": "",
                        "spoken_text": caption["text"] if caption else "",
                        "description": None, "description_status": "needs_review",
                        "caption_id": None, "_caption": caption})
    return visuals


@lru_cache(maxsize=128)
def _page_data(page_number: int):
    with _pdf() as pdf:
        if page_number < 1 or page_number > pdf.page_count:
            raise HTTPException(404, "Sayfa bulunamadı")
        page = pdf[page_number - 1]
        regions = _text_regions(page)
        regions.extend(_visual_regions(page, regions))
        for link in page.get_links():
            uri = link.get("uri")
            if not uri or not uri.startswith(("https://", "http://")):
                continue
            regions.append({"kind": "external_link", "bbox": _box(link["from"]),
                            "text": uri, "spoken_text": "Dış bağlantı: " + uri,
                            "description": None, "description_status": "not_applicable",
                            "caption_id": None})
        for visual in (item for item in regions if item["kind"] == "visual"):
            for link in (item for item in regions if item["kind"] == "external_link"):
                a, b = visual["bbox"], link["bbox"]
                overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
                if overlap > (a[2] - a[0]) * (a[3] - a[1]) * 0.7:
                    visual["kind"] = "qr_code"
                    visual["spoken_text"] = "Karekod. Bağlantı ayrıca seçilebilir."
                    visual["description_status"] = "not_applicable"
                    break
        regions.sort(key=lambda region: (region["bbox"][1], region["bbox"][0]))
        for index, region in enumerate(regions, 1):
            region["id"] = f"p{page_number}-r{index}"
            region["reading_order"] = index
        for region in regions:
            if region["kind"] in {"visual", "qr_code"}:
                caption = region.pop("_caption")
            if region["kind"] == "visual":
                if caption:
                    region["caption_id"] = caption["id"]
                    region["spoken_text"] = "Görsel. Alt yazı: " + caption["text"]
                else:
                    region["spoken_text"] = "Görsel. Doğrulanmış betimleme henüz yok."
            if region["kind"] in {"visual", "qr_code", "paragraph"}:
                nearby = [item for item in regions if item["kind"] == "source_label"
                          and -10 <= region["bbox"][1] - item["bbox"][3] <= 30
                          and min(abs(region["bbox"][0] - item["bbox"][0]),
                                  abs(region["bbox"][2] - item["bbox"][0])) <= 35]
                region["source_label_id"] = min(nearby, key=lambda item: abs(region["bbox"][1] - item["bbox"][3]))["id"] if nearby else None
            region["spoken_text"] = history_spoken_text(region["spoken_text"])
        return {"page": page_number, "width": round(page.rect.width, 2),
                "height": round(page.rect.height, 2), "regions": regions}


@router.get("/book")
def book_metadata():
    with _pdf() as pdf:
        return {"title": TITLE, "page_count": pdf.page_count,
                "source_url": SOURCE_URL, "book_type": "textbook",
                "notice": "MEB kitabından yerel çalışma kopyası. Otomatik görsel betimlemesi doğrulanmadan sunulmaz."}


@router.get("/pages/{page_number}")
def page_regions(page_number: int):
    return _page_data(page_number)


@router.get("/pages/{page_number}/regions/{region_id}/audio")
def region_audio(page_number: int, region_id: str):
    """Read only source-derived text; never synthesize a client-supplied string."""
    region = next((item for item in _page_data(page_number)["regions"]
                   if item["id"] == region_id), None)
    if region is None or not region["spoken_text"] or region["kind"] == "external_link":
        raise HTTPException(404, "Okunabilir kaynak bölümü bulunamadı")
    try:
        audio = synthesize_history_text(region["spoken_text"])
    except LocalTtsUnavailable:
        raise HTTPException(503, "Yerel Türkçe ses motoru kullanılamıyor") from None
    return Response(audio, media_type="audio/wav",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/pages/{page_number}/image")
def page_image(page_number: int):
    with _pdf() as pdf:
        if page_number < 1 or page_number > pdf.page_count:
            raise HTTPException(404, "Sayfa bulunamadı")
        pixmap = pdf[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(1.35, 1.35), alpha=False)
        return Response(pixmap.tobytes("png"), media_type="image/png",
                        headers={"Cache-Control": "private, max-age=3600"})
