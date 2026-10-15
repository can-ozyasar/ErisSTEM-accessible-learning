"""Kuyruktan bir işi alıp yerel PDF metin katmanını güvenle işleyen worker."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..job_store import DocumentStore, JobStore, make_session_factory
from .materialize import draft_from_text_layer
from .pdf_text_layer import PdfSafetyError, extract_text_layer
from .review_previews import write_review_previews
from .worker import write_text_layer


def process_one(
    store: JobStore, source_root: Path, output_dir: Path, documents: DocumentStore | None = None
) -> bool:
    job = store.claim_next()
    if job is None:
        return False
    try:
        pages = (
            None
            if job.selected_pages == "all"
            else {int(value) for value in job.selected_pages.split(",")}
        )
        result = extract_text_layer(source_root / job.source_relative_path, source_root, pages)
        if result.source_checksum != job.source_checksum:
            store.fail(job.id, "source_checksum_mismatch")
            return True
        write_text_layer(result, output_dir)
        if documents is not None:
            # A teacher can distinguish several imported books without having to
            # inspect their checksums.  The file never leaves the private source
            # root; only its harmless display name is used in the draft title.
            title = Path(job.source_relative_path).stem.replace("-", " ").replace("_", " ").strip()
            draft = draft_from_text_layer(
                result, title or "İçe aktarılan kaynak taslağı", job.selected_pages
            )
            documents.create_draft(draft)
            write_review_previews(
                source_root / job.source_relative_path,
                source_root,
                output_dir,
                draft["id"],
                pages or set(range(1, result.page_count + 1)),
            )
        store.finish(job.id)
    except PdfSafetyError:
        store.fail(job.id, "pdf_safety_error")
    except OSError:
        store.fail(job.id, "storage_error")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM kuyruk worker'ı")
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/derived"))
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    sessions = make_session_factory()
    store, documents = JobStore(sessions), DocumentStore(sessions)
    while True:
        processed = process_one(store, args.source_root, args.output_dir, documents)
        print("processed" if processed else "idle")
        if args.once:
            break
        if not processed:
            time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
