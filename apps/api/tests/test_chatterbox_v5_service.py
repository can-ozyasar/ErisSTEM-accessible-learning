import pytest

from app.chatterbox_v5_service import MAX_CHUNK_CHARS, create_app, split_text


def test_chunks_preserve_words_and_bound_length():
    text = "Tarih dersi. " * 120
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHUNK_CHARS for chunk in chunks)
    assert " ".join(chunks) == " ".join(text.split())


def test_empty_and_unbounded_words_are_rejected():
    with pytest.raises(ValueError, match="invalid_text_length"):
        split_text("   ")
    with pytest.raises(ValueError, match="word_too_long"):
        split_text("x" * (MAX_CHUNK_CHARS + 1))


def test_wrong_model_is_rejected_before_loading_dependencies(tmp_path):
    (tmp_path / "t3_mtl23ls_v3.safetensors").write_bytes(b"wrong model")
    with pytest.raises(RuntimeError, match="checksum_mismatch"):
        create_app(tmp_path, tmp_path / "voice.wav")
