"""Yetkili operatörün yerel PDF kaynağını checksum ile kuyruğa eklemesi."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from ..job_store import JobStore, make_session_factory
from .pdf_text_layer import PdfSafetyError, _read_and_validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Yerel MEB PDF kaynağını kuyruğa ekler")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pipeline-version", default="text-layer-v1")
    parser.add_argument("--pages", required=True, help="Virgülle ayrılmış seçili PDF sayfaları")
    args = parser.parse_args()
    try:
        path, content = _read_and_validate(args.input, args.source_root)
    except PdfSafetyError as exc:
        parser.error(str(exc))
    relative_path = path.relative_to(args.source_root.resolve()).as_posix()
    job, created = JobStore(make_session_factory()).enqueue(
        hashlib.sha256(content).hexdigest(), relative_path, args.pipeline_version, args.pages
    )
    print(f"{job.id} {'created' if created else 'existing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
