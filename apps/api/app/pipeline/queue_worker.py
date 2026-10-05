"""Kuyruktan bir işi alıp yerel PDF metin katmanını güvenle işleyen worker."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..job_store import DocumentStore, JobStore, make_session_factory
from .materialize import draft_from_text_layer
from .pdf_text_layer import PdfSafetyError, extract_text_layer
from .worker import write_text_layer


def process_one(
    store: JobStore, source_root: Path, output_dir: Path, documents: DocumentStore | None = None
) -> bool:
    job = store.claim_next()
    if job is None:
        return False
    try:
        result = extract_text_layer(source_root / job.source_relative_path, source_root)
        if result.source_checksum != job.source_checksum:
            store.fail(job.id, "source_checksum_mismatch")
            return True
        write_text_layer(result, output_dir)
        if documents is not None:
            documents.create_draft(draft_from_text_layer(result, "İçe aktarılan kaynak taslağı"))
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
    args = parser.parse_args()
    sessions = make_session_factory()
    processed = process_one(
        JobStore(sessions), args.source_root, args.output_dir, DocumentStore(sessions)
    )
    print("processed" if processed else "idle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
