"""Build a private TTS Gold manifest from already verified canonical blocks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .accessible_content import CanonicalAccessibleBlock, release_decision
from .tts_quality import TtsGoldManifest


class CanonicalContentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    blocks: list[CanonicalAccessibleBlock] = Field(min_length=1)


class CriticalTokenManifest(BaseModel):
    """Small expert-reviewed calibration labels, not a second copy of the lesson."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    tokens_by_block_id: dict[str, list[str]] = Field(default_factory=dict)


def build_tts_gold(
    content: CanonicalContentManifest, critical: CriticalTokenManifest
) -> TtsGoldManifest:
    if content.schema_version != "canonical-accessible-content-v1":
        raise ValueError("invalid canonical content schema")
    if critical.schema_version != "tts-critical-tokens-v1":
        raise ValueError("invalid critical token schema")
    items = []
    for block in content.blocks:
        decision, _ = release_decision(block)
        if decision != "auto-approved":
            continue
        spoken = block.representations.spoken_text
        if not spoken:
            continue
        kind = "text" if block.kind == "heading" else block.kind
        items.append(
            {
                "id": block.id,
                "kind": kind,
                "expected_spoken_text": spoken,
                "critical_tokens": critical.tokens_by_block_id.get(block.id, []),
            }
        )
    if not items:
        raise ValueError("no auto-approved spoken blocks available for TTS Gold")
    return TtsGoldManifest(schema_version="tts-gold-v1", items=items)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build private TTS Gold from canonical accessibility content")
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--critical-tokens", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = CanonicalContentManifest.model_validate_json(args.content.read_text(encoding="utf-8"))
    critical = CriticalTokenManifest.model_validate_json(args.critical_tokens.read_text(encoding="utf-8"))
    result = build_tts_gold(content, critical)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"tts_gold_items": len(result.items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
