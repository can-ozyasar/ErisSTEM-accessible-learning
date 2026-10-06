"""Private Gold kümede belge çıkarıcılarını karşılaştıran, modelden bağımsız benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .pdf_text_layer import extract_text_layer


def normalized(value: str) -> str:
    return " ".join(value.lower().split())


def levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, start=1):
        current = [index]
        for other_index, other in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[other_index] + 1,
                    previous[other_index - 1] + (char != other),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(expected: str, actual: str) -> float:
    expected, actual = normalized(expected), normalized(actual)
    return levenshtein(expected, actual) / max(len(expected), 1)


def token_f1(expected: str, actual: str) -> float:
    expected_tokens, actual_tokens = (
        set(normalized(expected).split()),
        set(normalized(actual).split()),
    )
    if not expected_tokens and not actual_tokens:
        return 1.0
    overlap = len(expected_tokens & actual_tokens)
    return 2 * overlap / max(len(expected_tokens) + len(actual_tokens), 1)


@dataclass(frozen=True)
class Candidate:
    name: str
    available: bool
    version: str
    extract: Callable[[Path, Path, set[int]], dict[int, str]] | None = None


def native_candidate() -> Candidate:
    def extract(path: Path, root: Path, pages: set[int]) -> dict[int, str]:
        result = extract_text_layer(path, root, pages)
        return {
            page: " ".join(block.text for block in result.blocks if block.source.page == page)
            for page in pages
        }

    return Candidate("native-text-layer", True, "pymupdf", extract)


def optional_candidate(name: str, package: str) -> Candidate:
    return Candidate(name, importlib.util.find_spec(package) is not None, "not-run")


def run(manifest: dict, source: Path, source_root: Path, candidates: list[Candidate]) -> dict:
    pages = {item["page"] for item in manifest["items"]}
    output = {
        "dataset_checksum": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest(),
        "hardware": platform.platform(),
        "candidates": [],
    }
    for candidate in candidates:
        record: dict = {
            "name": candidate.name,
            "available": candidate.available,
            "version": candidate.version,
        }
        if not candidate.available or candidate.extract is None:
            record["status"] = "unavailable"
        else:
            predictions = candidate.extract(source, source_root, pages)
            scored = []
            for item in manifest["items"]:
                expected = item.get("expected", "")
                if not expected:
                    continue
                actual = predictions.get(item["page"], "")
                metric = (
                    token_f1(expected, actual)
                    if item["kind"] == "formula"
                    else 1 - character_error_rate(expected, actual)
                )
                scored.append(metric)
            record.update(
                status="measured" if scored else "blocked_missing_gold_annotations",
                score=sum(scored) / len(scored) if scored else None,
                samples=len(scored),
            )
        output["candidates"].append(record)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM private extractor benchmark")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = run(
        manifest,
        args.input,
        args.source_root,
        [
            native_candidate(),
            optional_candidate("docling", "docling"),
            optional_candidate("paddleocr-vl", "paddleocr"),
        ],
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
