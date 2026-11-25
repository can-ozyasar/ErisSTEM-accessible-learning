from types import SimpleNamespace

import pymupdf
import pytest

from app.pipeline import audit_exam_pack_evidence_pdf as subject


def test_audit_flags_quote_missing_from_pdf_crop(tmp_path, monkeypatch):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Tarih bilimi kaynak kullanir")
    doc.save(tmp_path / "source.pdf")
    doc.close()
    source = SimpleNamespace(id="source", relative_path="source.pdf")
    common = dict(source_id="source", source_checksum="a" * 64, page=1, bbox=(60, 60, 400, 130))
    evidence = [SimpleNamespace(**common, quote="Tarih bilimi kaynak kullanir"),
                SimpleNamespace(**common, quote="Olmayan kelimeler kaynakta bulunmaz")]
    pack = SimpleNamespace(pack_id="test", sources=[source], questions=[SimpleNamespace(id="q1", evidence=evidence)])
    monkeypatch.setattr(subject.AytHistoryExamPack, "model_validate", lambda _: pack)
    monkeypatch.setattr(subject, "verify_pack_sources", lambda *_: None)
    result = subject.audit({}, tmp_path)
    assert [row["requires_review"] for row in result["evidence"]] == [False, True]
    assert result["requires_review_count"] == 1


def test_invalid_threshold_rejected(tmp_path):
    with pytest.raises(ValueError, match="eşik"):
        subject.audit({}, tmp_path, threshold=0)
