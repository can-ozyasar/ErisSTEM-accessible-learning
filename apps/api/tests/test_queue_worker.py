import hashlib
from pathlib import Path

import pymupdf

from app.job_store import JobStore, make_session_factory
from app.pipeline.queue_worker import process_one


def create_pdf(path: Path) -> None:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Kaynak metni")
    document.save(path)
    document.close()


def test_worker_processes_claimed_job(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "kitap.pdf"
    create_pdf(pdf_path)
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    store = JobStore(make_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}"))
    job, _ = store.enqueue(checksum, "kitap.pdf", "text-layer-v1")

    assert process_one(store, source_root, tmp_path / "derived") is True
    assert (tmp_path / "derived" / f"{checksum}.text-layer.json").exists()
    assert store.list_recent()[0].id == job.id
    assert store.list_recent()[0].status == "succeeded"


def test_worker_fails_when_checksum_does_not_match(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    create_pdf(source_root / "kitap.pdf")
    store = JobStore(make_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}"))
    store.enqueue("0" * 64, "kitap.pdf", "text-layer-v1")

    assert process_one(store, source_root, tmp_path / "derived") is True
    assert store.list_recent()[0].status == "failed"
    assert store.list_recent()[0].last_error_code == "source_checksum_mismatch"
