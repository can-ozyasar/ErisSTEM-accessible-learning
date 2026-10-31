"""Fetch selected OGM AYT page images into a private checksum-bound cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

SCHEMA = "ogm-ayt-page-download-manifest-v1"
BASE_URL = "https://ogmmateryal.eba.gov.tr/panel/upload/etkilesimli/kitap/konu-pekistirme/ayt/tarih/files/mobile/{page}.jpg"


def parse_pages(value: str) -> list[int]:
    pages = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(item))
    if not pages or any(page < 1 or page > 313 for page in pages):
        raise ValueError("Sayfalar 1 ile 313 arasında olmalı")
    return sorted(set(pages))


def fetch(pages: list[int], output: Path, fetcher=None) -> dict:
    if fetcher is None:
        def fetcher(url: str) -> bytes:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": BASE_URL.format(page=1)})
            failure = None
            for attempt in range(3):
                try:
                    with urlopen(request, timeout=30) as response:
                        return response.read()
                except URLError as error:
                    failure = error
                    if attempt < 2:
                        time.sleep(attempt + 1)
            raise ValueError(f"OGM sayfa görüntüsü indirilemedi: {url}") from failure
    rows = []
    images = output / "pages"
    images.mkdir(parents=True, exist_ok=True)
    for page in pages:
        body = fetcher(BASE_URL.format(page=page))
        if not body.startswith(b"\xff\xd8\xff") or len(body) < 10_000:
            raise ValueError(f"OGM sayfa görüntüsü geçerli JPEG değil: {page}")
        target = images / f"{page:03d}.jpg"
        target.write_bytes(body)
        rows.append({"page": page, "file": f"pages/{target.name}", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
    return {"schema": SCHEMA, "source_url_template": BASE_URL, "page_count": len(rows), "pages": rows,
            "content_exported": False, "answer_key_exported": False, "student_data_accessed": False,
            "notice": "Private source images only. Page images cannot enter Git, Kaggle input, student runtime or model context without later review."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", required=True, help="Örnek: 29-31,40")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = fetch(parse_pages(args.pages), args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
