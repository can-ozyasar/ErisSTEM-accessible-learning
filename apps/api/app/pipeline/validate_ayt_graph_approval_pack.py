"""Validate the private AYT graph crop pack without approving any item."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def validate(manifest: dict, pack_root: Path) -> dict:
    if manifest.get("schema") != "ayt-graph-teacher-approval-pack-v1":
        raise ValueError("Graf onay paketi şeması geçersiz")
    reviews = manifest.get("reviews")
    if not isinstance(reviews, list) or manifest.get("review_count") != len(reviews):
        raise ValueError("Onay paketi kayıt sayısı eşleşmiyor")
    seen = set()
    for row in reviews:
        key = (row.get("source_checksum"), row.get("chunk_id"))
        if key in seen or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_checksum", ""))):
            raise ValueError("Kaynak checksum veya parça kimliği yineleniyor")
        seen.add(key)
        if not isinstance(row.get("page"), int) or row["page"] < 1:
            raise ValueError("PDF sayfası geçersiz")
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(item, (int, float)) for item in bbox):
            raise ValueError("PDF koordinatı geçersiz")
        crop = row.get("crop", "")
        if not crop.startswith("crops/") or not (pack_root / crop).is_file():
            raise ValueError("PDF crop dosyası eksik")
    return {"schema": "ayt-graph-teacher-approval-pack-validation-v1",
            "review_count": len(reviews), "unique_source_count": len({row["source_checksum"] for row in reviews}),
            "security_passed": True, "runtime_enabled": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.manifest.read_text(encoding="utf-8")), args.pack_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
