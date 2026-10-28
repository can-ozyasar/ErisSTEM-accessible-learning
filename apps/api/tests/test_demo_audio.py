import hashlib
import json

from app.demo_audio import MODEL_SHA256, resolve_demo_audio, resolve_demo_interface


def digest(value):
    return hashlib.sha256(value).hexdigest()


def test_demo_audio_requires_exact_source_text_and_audio(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_TTS_DEMO_ROOT", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    (tmp_path / "audio.wav").write_bytes(wav)
    index = {"schema_version": "v5-demo-installed-v1", "model_sha256": MODEL_SHA256,
             "source_sha256": {"history": digest(b"source")},
             "items": [{"kind": "history", "id": "p40-r1", "spoken_text_sha256": digest(b"merhaba"),
                        "filename": "audio.wav", "bytes": len(wav), "audio_sha256": digest(wav)}]}
    (tmp_path / "index.json").write_text(json.dumps(index))
    assert resolve_demo_audio("history", "p40-r1", "merhaba", source) == wav
    assert resolve_demo_audio("history", "p40-r2", "merhaba", source) is None
    assert resolve_demo_audio("history", "p40-r1", "başka", source) is None
    (tmp_path / "audio.wav").write_bytes(wav[:-1] + b"x")
    assert resolve_demo_audio("history", "p40-r1", "merhaba", source) is None
    source.write_bytes(b"different source")
    assert resolve_demo_audio("history", "p40-r1", "merhaba", source) is None


def test_demo_audio_never_reads_outside_private_root(monkeypatch, tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    monkeypatch.setenv("LOCAL_TTS_DEMO_ROOT", str(root))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    outside = tmp_path / "other.wav"
    outside.write_bytes(b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32)
    index = {"schema_version": "v5-demo-installed-v1", "model_sha256": MODEL_SHA256,
             "source_sha256": {"history": digest(b"source")},
             "items": [{"kind": "history", "id": "x", "spoken_text_sha256": digest(b"hello"),
                        "filename": "../other.wav", "bytes": outside.stat().st_size, "audio_sha256": digest(outside.read_bytes())}]}
    (root / "index.json").write_text(json.dumps(index))
    assert resolve_demo_audio("history", "x", "hello", source) is None


def test_interface_audio_matches_only_exact_approved_phrase_in_extra_root(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCAL_TTS_DEMO_ROOT", raising=False)
    monkeypatch.setenv("LOCAL_TTS_DEMO_EXTRA_ROOT", str(tmp_path))
    text = "Önceki alan, düğme"
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    (tmp_path / "audio.wav").write_bytes(wav)
    text_hash = digest(text.encode())
    index = {"schema_version": "v5-demo-installed-v1", "model_sha256": MODEL_SHA256,
             "source_sha256": {}, "items": [{"kind": "interface", "id": text_hash,
             "spoken_text_sha256": text_hash, "filename": "audio.wav", "bytes": len(wav),
             "audio_sha256": digest(wav)}]}
    (tmp_path / "index.json").write_text(json.dumps(index))
    assert resolve_demo_interface(text) == wav
    assert resolve_demo_interface("Başka bir metin") is None
    index["model_sha256"] = "0" * 64
    (tmp_path / "index.json").write_text(json.dumps(index))
    assert resolve_demo_interface(text) is None
