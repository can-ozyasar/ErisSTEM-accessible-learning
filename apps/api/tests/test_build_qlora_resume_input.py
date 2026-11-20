import hashlib
import importlib.util
import json
from pathlib import Path


def module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "build_qlora_resume_input.py"
    spec = importlib.util.spec_from_file_location("build_qlora_resume_input", path)
    value = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(value)
    return value


def test_resume_bundle_preserves_input_and_rejects_checkpoint_tampering(tmp_path):
    runner = module()
    source = tmp_path / "source"
    source.mkdir()
    train, dev = source / "train.jsonl", source / "dev.jsonl"
    train.write_text('{"group_id":"train"}\n', encoding="utf-8")
    dev.write_text('{"group_id":"dev"}\n', encoding="utf-8")
    contract = {"epochs": 3, "seed": 42}
    manifest = {"schema": "eristem-tutor-qlora-experiment-input-v1", "training_contract": contract,
                "answer_keys_included": False, "sealed_test_uploaded": False, "student_data_included": False,
                "files": {"train.jsonl": runner.sha256(train), "dev.jsonl": runner.sha256(dev)}}
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    verified = tmp_path / "verified"
    verified.mkdir()
    checkpoint = verified / "checkpoint-10"
    checkpoint.mkdir()
    checkpoint_files = {}
    for name in ("trainer_state.json", "optimizer.pt", "scheduler.pt", "adapter_config.json", "adapter_model.safetensors"):
        path = checkpoint / name
        path.write_text(name, encoding="utf-8")
        checkpoint_files[name] = path
    resume = {"schema": "eristem-tutor-qlora-resume-checkpoint-v1", "checkpoint_name": "checkpoint-10",
              "input_manifest_sha256": runner.sha256(source / "manifest.json"),
              "training_contract_sha256": runner.contract_checksum(contract),
              "files": [{"path": name, "sha256": runner.sha256(path), "bytes": path.stat().st_size}
                        for name, path in checkpoint_files.items()]}
    (verified / "resume_checkpoint_manifest.json").write_text(json.dumps(resume), encoding="utf-8")

    result = runner.build(source, verified, tmp_path / "out")

    assert result["checkpoint"] == "checkpoint-10"
    assert (tmp_path / "out" / "checkpoint-10" / "trainer_state.json").read_text() == "trainer_state.json"
    checkpoint_files["optimizer.pt"].write_text("tampered", encoding="utf-8")
    try:
        runner.build(source, verified, tmp_path / "out-2")
    except ValueError as error:
        assert "checksum" in str(error)
    else:
        raise AssertionError("tampered checkpoint must be rejected")
