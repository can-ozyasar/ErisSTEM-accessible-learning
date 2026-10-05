from pathlib import Path

from app.job_store import JobStore, make_session_factory


def test_enqueue_is_idempotent(tmp_path: Path):
    store = JobStore(make_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}"))
    checksum = "a" * 64

    first, was_created = store.enqueue(checksum, "text-layer-v1")
    second, created_again = store.enqueue(checksum, "text-layer-v1")

    assert was_created is True
    assert created_again is False
    assert first.id == second.id
    assert len(store.list_recent()) == 1
