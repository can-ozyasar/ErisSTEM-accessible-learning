"""Deterministic duplicate-aware partitioning of private corpus audit records.

Only source indices, durations and digests are accepted; text/audio are not
needed. Audio or normalized-text duplicates are grouped transitively so none
can cross a training/validation boundary or become their own reference.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{64}$")


def split_records(records: Sequence[dict[str, Any]], *, seed: int, validation_percent: int = 8) -> dict[str, Any]:
    if not records or not 1 <= validation_percent <= 50:
        raise ValueError("invalid_records_or_validation_percent")
    indexed: dict[int, dict[str, Any]] = {}
    for row in records:
        if not isinstance(row, dict):
            raise TypeError("record_must_be_dict")
        index = row.get("source_index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 1 or index in indexed:
            raise ValueError("invalid_or_duplicate_source_index")
        if not all(isinstance(row.get(key), str) and _SHA.fullmatch(row[key]) for key in ("decoded_audio_sha256", "normalized_text_sha256")):
            raise ValueError("invalid_content_digest")
        seconds = row.get("seconds")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("invalid_duration")
        indexed[index] = row

    parent = {index: index for index in indexed}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    for key in ("decoded_audio_sha256", "normalized_text_sha256"):
        first: dict[str, int] = {}
        for index in sorted(indexed):
            digest = indexed[index][key]
            if digest in first:
                union(index, first[digest])
            else:
                first[digest] = index

    groups: dict[int, list[int]] = {}
    for index in sorted(indexed):
        groups.setdefault(find(index), []).append(index)
    train: list[int] = []
    validation: list[int] = []
    group_by_index: dict[int, int] = {}
    for group, members in sorted(groups.items()):
        key = f"{seed}:tts-split:" + ",".join(map(str, members))
        value = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16) % 100
        (validation if value < validation_percent else train).extend(members)
        group_by_index.update({index: group for index in members})
    return {"train": sorted(train), "validation": sorted(validation), "group_by_index": group_by_index}


def select_reference(target_index: int, records: Sequence[dict[str, Any]], split: dict[str, Any], *, seed: int) -> int:
    indexed = {row["source_index"]: row for row in records}
    if target_index not in indexed or target_index not in split["group_by_index"]:
        raise ValueError("target_not_in_split")
    group = split["group_by_index"][target_index]
    candidates = [index for index in split["train"]
                  if index in indexed and indexed[index]["seconds"] >= 6
                  and split["group_by_index"][index] != group]
    if not candidates:
        raise ValueError("no_distinct_training_reference")
    value = int(hashlib.sha256(f"{seed}:tts-reference:{target_index}".encode()).hexdigest()[:16], 16)
    return candidates[value % len(candidates)]
