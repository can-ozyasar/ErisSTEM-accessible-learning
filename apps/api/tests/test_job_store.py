from pathlib import Path

from app.job_store import JobStore, make_session_factory


def test_enqueue_is_idempotent(tmp_path: Path):
    store = JobStore(make_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}"))
    checksum = "a" * 64

    first, was_created = store.enqueue(checksum, "matematik/kitap.pdf", "text-layer-v1")
    second, created_again = store.enqueue(checksum, "matematik/kitap.pdf", "text-layer-v1")

    assert was_created is True
    assert created_again is False
    assert first.id == second.id
    assert len(store.list_recent()) == 1


def test_claim_and_finish_transition(tmp_path: Path):
    store = JobStore(make_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}"))
    job, _ = store.enqueue("b" * 64, "matematik/kitap.pdf", "text-layer-v1")

    claimed = store.claim_next()
    store.finish(job.id)

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.attempts == 1
    assert store.list_recent()[0].status == "succeeded"
