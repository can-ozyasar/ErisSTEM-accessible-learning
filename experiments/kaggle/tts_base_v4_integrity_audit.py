"""Compare pinned base and V4 weights privately without revealing blind labels."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CONTROL = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-finetune-control-v1")
BASE_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
TRAINED_SHA = "274bfe98e45280aab2687f456bb94a86d0adfa3c220b9f0137a7c32f22648493"
OUTPUT = Path("/kaggle/working/eristem-tts-base-v4-integrity")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or not CONTROL.exists():
        raise RuntimeError("private_kaggle_and_control_required")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "huggingface_hub", "safetensors"], check=True)
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    base = Path(hf_hub_download("ResembleAI/chatterbox", filename="t3_mtl23ls_v3.safetensors", revision=BASE_REVISION))
    matches = [p for p in Path("/kaggle/input").rglob("t3_mtl23ls_v3.safetensors") if p.parent.name == "eristem-private-chatterbox-v3-finetune-v4"]
    if len(matches) != 1:
        raise RuntimeError("missing_trained_weight")
    trained = matches[0]
    base_sha, trained_sha = sha256(base), sha256(trained)
    if trained_sha != TRAINED_SHA:
        raise RuntimeError("trained_weight_checksum_mismatch")
    with safe_open(str(base), framework="pt", device="cpu") as b, safe_open(str(trained), framework="pt", device="cpu") as t:
        keys = sorted(b.keys())
        if keys != sorted(t.keys()):
            raise RuntimeError("weight_tensor_names_mismatch")
        compared = 0
        changed = 0
        maximum_difference = 0.0
        for key in keys:
            # Examine up to eight representative tensors, including large T3
            # layers, without loading a whole 2 GB model into memory.
            bt, tt = b.get_tensor(key), t.get_tensor(key)
            if bt.shape != tt.shape:
                raise RuntimeError("weight_tensor_shape_mismatch")
            if bt.numel() < 1024:
                continue
            difference = (bt.float() - tt.float()).abs()
            compared += 1
            if bool(torch.any(difference > 0)):
                changed += 1
            maximum_difference = max(maximum_difference, float(difference.max()))
            if compared >= 8:
                break
    report = {"schema_version": "tts-base-v4-integrity-v1", "base_revision": BASE_REVISION, "base_sha256": base_sha, "trained_sha256": trained_sha, "file_hashes_differ": base_sha != trained_sha, "compared_tensor_count": compared, "changed_tensor_count": changed, "sample_max_absolute_weight_difference": maximum_difference, "blind_assignments_revealed": False}
    if not report["file_hashes_differ"] or compared == 0 or changed == 0:
        raise RuntimeError("base_and_trained_comparison_not_distinct")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "run_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
