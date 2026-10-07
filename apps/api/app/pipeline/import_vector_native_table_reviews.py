"""Import selected vector/native table candidates into the private teacher queue."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ..job_store import DocumentStore, TableReviewStore, make_session_factory
from .materialize import draft_from_text_layer
from .pdf_region_vector_table import extract_region_vector_tables
from .pdf_text_layer import PdfSafetyError, extract_text_layer
from .review_previews import write_review_previews
from .table_review_inbox import to_review_inbox


def import_vector_native_table_reviews(
    source_pdf: Path,
    source_root: Path,
    regions_manifest: Path,
    derived_root: Path,
    documents: DocumentStore,
    tables: TableReviewStore,
) -> dict[str, object]:
    """Build source previews and add only source-bound vector/native review items.

    Existing documents and table reviews are never replaced. That makes a retry
    safe after a process interruption and protects completed teacher reviews.
    """
    results = extract_region_vector_tables(source_pdf, source_root, regions_manifest)
    reviewable = [result for result in results if result.draft is not None and result.status.startswith("candidate-")]
    if not reviewable:
        return {"document_id": None, "reviewable": 0, "created": 0, "existing": 0, "results": [asdict(result) for result in results]}
    pages = {result.draft["source"]["page"] for result in reviewable}
    extracted = extract_text_layer(source_pdf, source_root, pages)
    draft = draft_from_text_layer(extracted, "Kaynak bağlı tablo denetim taslağı", ",".join(map(str, sorted(pages))))
    document_id = draft["id"]
    if documents.get(document_id) is None:
        documents.create_draft(draft)
    write_review_previews(source_pdf, source_root, derived_root, document_id, pages)
    inbox = to_review_inbox([asdict(result) for result in results], document_id)
    created = existing = 0
    for payload in inbox:
        record = tables.get(payload["id"])
        if record is not None:
            existing += 1
            continue
        tables.create(payload)
        documents.add_audit(
            document_id,
            "admin",
            "vector_native_table_imported",
            payload["id"],
            f"page={payload['source']['page']}; region={payload['source']['region_id']}",
        )
        created += 1
    return {
        "document_id": document_id,
        "reviewable": len(inbox),
        "created": created,
        "existing": existing,
        "results": [
            {"region_id": result.region_id, "status": result.status, "grid_rows": result.grid_rows, "grid_columns": result.grid_columns, "bound_word_count": result.bound_word_count}
            for result in results
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import private vector/native table candidates into teacher review")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--derived-root", type=Path, default=Path("data/derived"))
    args = parser.parse_args()
    try:
        sessions = make_session_factory()
        result = import_vector_native_table_reviews(
            args.input, args.source_root, args.regions, args.derived_root,
            DocumentStore(sessions), TableReviewStore(sessions),
        )
    except (OSError, ValueError, PdfSafetyError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
