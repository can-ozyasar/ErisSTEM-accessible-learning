"""Generate a source-matched private Piper baseline for history listening."""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from urllib.request import Request, urlopen

import kaggle_ops

MANIFEST = Path("data/private/eristem_history_tts_eval_v1/tts-history-eval-v1.json")
OUTPUT = Path("data/private/tts_history_piper_v1")
ENDPOINT = "http://127.0.0.1:5173/api/v1/student/interface-speech"


def main() -> None:
    source = kaggle_ops.private_path(kaggle_ops.repo_root() / MANIFEST)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "tts-history-eval-v1" or payload.get("evaluation_only") is not True:
        raise ValueError("Tarih ses değerlendirme girdisi geçersiz")
    destination = kaggle_ops.private_path(kaggle_ops.repo_root() / OUTPUT)
    if destination.exists():
        raise FileExistsError("Piper baseline zaten var; var olan sonuçlar korunuyor")
    destination.mkdir(parents=True)
    records = []
    for item in payload["items"]:
        request = Request(
            ENDPOINT,
            data=json.dumps({"text": item["expected_spoken_text"]}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Role": "student", "Accept": "audio/wav"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:  # nosec B310: fixed loopback endpoint
            body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024 or body[:4] != b"RIFF" or body[8:12] != b"WAVE":
            raise ValueError("Yerel TTS güvenli WAV üretmedi")
        with wave.open(io.BytesIO(body), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        path = destination / f"{item['id']}.wav"
        path.write_bytes(body)
        records.append({"id": item["id"], "kind": item["kind"], "status": "generated",
                        "duration_seconds": duration, "audio_sha256": kaggle_ops.sha256(path)})
    (destination / "run_records.json").write_text(json.dumps({
        "schema_version": "tts-synthesis-run-v1",
        "candidate": "piper-tr_TR-dfki-medium-local-v1",
        "input_schema": "tts-history-eval-v1",
        "input_sha256": kaggle_ops.sha256(source),
        "items_total": len(records), "items_generated": len(records), "items_failed": 0,
        "student_publication": "blocked_pending_human_listening",
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate": "piper-tr_TR-dfki-medium-local-v1",
                      "generated": len(records), "private_output": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
