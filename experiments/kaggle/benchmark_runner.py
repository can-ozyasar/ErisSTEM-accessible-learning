"""Kaggle T4 notebook'unda çalıştırılacak private benchmark başlangıç noktası."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


INPUT = Path("/kaggle/input/eristem-private-meb")
OUTPUT = Path("/kaggle/working/eristem-results")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    run(["nvidia-smi"])
    # Kurulum sürümleri sonuç dosyasına yazılır; notebook çıktısı private kalmalıdır.
    run(["python", "-m", "pip", "install", "--quiet", "docling"])
    result = {
        "execution_target": "kaggle-t4",
        "input_is_private": True,
        "candidates": {
            "docling": "installed; run page-region extraction adapter next",
            "paddleocr_vl": "install only after pinned benchmark adapter is selected",
            "qwen3_vl_4b": "not enabled; training gate requires failed baseline metrics",
        },
    }
    (OUTPUT / "environment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
