"""Create a content-free manifest for OGM's private AYT history source copy."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

SCHEMA = "ogm-ayt-history-source-manifest-v1"
TEXT_ARRAY = "var textForPages ="
TOPICS = (
    "Tarih ve Zaman", "İnsanlığın İlk Dönemleri", "Orta Çağ'da Dünya",
    "İlk ve Orta Çağlarda Türk Dünyası", "İslam Medeniyetinin Doğuşu",
    "Türklerin İslamiyet'i Kabulü ve İlk Türk İslam Devletleri",
    "Yerleşme ve Devletleşme Sürecinde Selçuklu Türkiyesi",
    "Beylikten Devlete Osmanlı Siyaseti (1302-1453)",
    "Devletleşme Sürecinde Savaşçılar ve Askerler", "Beylikten Devlete Osmanlı Medeniyeti",
    "Dünya Gücü Osmanlı (1453-1595)", "Sultan ve Osmanlı Merkez Teşkilatı",
    "Klasik Çağda Osmanlı Toplum Düzeni", "Değişen Dünya Dengeleri Karşısında Osmanlı Siyaseti (1595-1774)",
    "Değişim Çağında Avrupa ve Osmanlı", "Devrimler Çağında Değişen Devlet Toplum İlişkileri",
    "Uluslararası İlişkilerde Denge Stratejisi (1774-1914)", "XIX ve XX. Yüzyılda Değişen Sosyoekonomik Hayat",
    "20. Yüzyıl Başlarında Osmanlı Devleti ve Dünya", "Millî Mücadele", "Atatürkçülük ve Türk İnkılabı",
    "İki Savaş Arasındaki Dönemde Türkiye ve Dünya", "II. Dünya Savaşı Sürecinde Türkiye ve Dünya",
    "II. Dünya Savaşı Sonrasında Türkiye ve Dünya", "Toplumsal Devrim Çağında Dünya ve Türkiye",
    "21. Yüzyılın Eşiğinde Türkiye ve Dünya",
)


def parse_pages(raw: str) -> list[str]:
    """Parse the data array, never execute downloaded JavaScript."""
    start = raw.find(TEXT_ARRAY)
    if start < 0:
        raise ValueError("OGM arama indeksi textForPages dizisini içermiyor")
    payload = raw[start + len(TEXT_ARRAY):].lstrip()
    try:
        pages, _ = json.JSONDecoder().raw_decode(payload)
    except json.JSONDecodeError as error:
        raise ValueError("OGM arama indeksi güvenli JSON dizi biçiminde değil") from error
    if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
        raise ValueError("OGM arama indeksi metin sayfaları içermiyor")
    return pages


def _topic(page: str) -> str | None:
    normalized = " ".join(page.replace("’", "'").replace("İ", "i").casefold().split())
    if "cevap anahtari" in normalized or "görsel kaynakça" in normalized:
        return None
    matches = [topic for topic in TOPICS if " ".join(topic.replace("’", "'").replace("İ", "i").casefold().split()) in normalized]
    return max(matches, key=len) if matches else None


def build(source: Path) -> dict:
    raw_bytes = source.read_bytes()
    raw = raw_bytes.decode("utf-8-sig")
    pages = parse_pages(raw)
    topics = [_topic(page) for page in pages]
    nonempty = sum(bool(page.strip()) for page in pages)
    return {
        "schema": SCHEMA, "source_checksum": hashlib.sha256(raw_bytes).hexdigest(),
        "page_count": len(pages), "nonempty_page_count": nonempty,
        "topic_candidate_count": sum(topic is not None for topic in topics),
        "topic_candidate_counts": dict(sorted(Counter(topic for topic in topics if topic).items())),
        "source_url": "https://ogmmateryal.eba.gov.tr/panel/upload/etkilesimli/kitap/konu-pekistirme/ayt/tarih/index.html",
        "content_exported": False, "answer_key_exported": False, "student_data_accessed": False,
        "notice": "Private source manifest only. The downloaded text index, questions, solutions and answer key remain outside Git, Kaggle input and student runtime.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
