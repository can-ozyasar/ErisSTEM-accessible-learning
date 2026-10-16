"""Safe, auditable Kaggle private Dataset and Notebook operations for ErişSTEM.

No command uploads or starts a Notebook by default. A remote mutation needs an
``--apply`` flag. Credentials are read only by Kaggle clients from the local
user credential store; this script never reads, prints, or writes a token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$")
SUMMARY_FILENAMES = (
    "run_metadata.json",
    "run_records.json",
    "structural_report.json",
    "region_records.json",
    "native_agreement_report.json",
    "formula_evaluation_report.json",
    "layout_probe_summary.json",
)
SYMBOL_PREDICTIONS_FILENAME = "symbol_predictions.json"
FORMULA_PREDICTIONS_FILENAME = "formula_predictions.json"
TTS_CANDIDATE_TRANSCRIPTS_FILENAME = "candidate_transcripts.json"
TTS_AUDIO_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_TTS_AUDIO_FILES = 200
MAX_TTS_TRANSCRIPT_CHARS = 8_000


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_root() -> Path:
    return (repo_root() / "data" / "private").resolve()


def private_directory(value: Path) -> Path:
    path = value.resolve()
    root = private_root()
    if not path.is_relative_to(root) or not path.is_dir():
        raise ValueError("Dataset kaynağı yalnız data/private altındaki bir klasör olabilir")
    return path


def private_path(value: Path) -> Path:
    """Accept a non-existing path only when it remains below data/private."""
    path = value.resolve()
    if not path.is_relative_to(private_root()):
        raise ValueError("İşlem yolu yalnız data/private altında olabilir")
    return path


def validate_handle(handle: str) -> str:
    if not HANDLE_PATTERN.fullmatch(handle):
        raise ValueError("Kaggle handle 'kullanici/dataset' biçiminde olmalı")
    return handle


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_manifest(source: Path) -> list[dict[str, str | int]]:
    root = private_directory(source)
    return [
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def write_record(action: str, handle: str, source: Path, *, applied: bool, version_notes: str) -> Path:
    directory = private_root() / "kaggle-operation-records"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "schema_version": "kaggle-operation-record-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "action": action,
        "dataset_handle": validate_handle(handle),
        "source_relative_path": str(private_directory(source).relative_to(private_root())),
        "applied": applied,
        "version_notes": version_notes,
        "files": dataset_manifest(source),
    }
    destination = directory / f"{timestamp}-{action}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def write_notebook_record(
    action: str,
    kernel: str,
    dataset: str,
    package: Path,
    *,
    applied: bool,
    details: dict[str, object] | None = None,
) -> Path:
    """Record orchestration metadata without reading raw document outputs."""
    directory = private_root() / "kaggle-operation-records"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    package = private_directory(package)
    record = {
        "schema_version": "kaggle-notebook-operation-record-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "action": action,
        "kernel": validate_handle(kernel),
        "dataset_handle": validate_handle(dataset),
        "package_relative_path": str(package.relative_to(private_root())),
        "applied": applied,
        "files": dataset_manifest(package),
        "details": details or {},
    }
    destination = directory / f"{timestamp}-{action}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def kagglehub_client():
    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("kagglehub kurulu değil; güvenli yerel venv içinde yükleyin") from exc
    return kagglehub


def verify() -> dict[str, str]:
    user = kagglehub_client().whoami().get("username")
    if not isinstance(user, str) or not user:
        raise RuntimeError("Kaggle kimlik doğrulaması kullanıcı adı döndürmedi")
    return {"authenticated_user": user}


def upload_dataset(source: Path, handle: str, version_notes: str) -> None:
    kagglehub_client().dataset_upload(validate_handle(handle), str(private_directory(source)), version_notes=version_notes)


def runner_path(value: Path) -> Path:
    """Permit only checked-in Kaggle runner source, never an arbitrary local script."""
    path = value.resolve()
    allowed_root = (repo_root() / "experiments" / "kaggle").resolve()
    if not path.is_relative_to(allowed_root) or not path.is_file() or path.suffix != ".py":
        raise ValueError("Notebook runner yalnız experiments/kaggle altındaki bir .py dosyası olabilir")
    return path


def kernel_package_directory(kernel: str) -> Path:
    owner, slug = validate_handle(kernel).split("/", maxsplit=1)
    return private_root() / "kaggle-notebooks" / owner / slug


def notebook_title_slug(title: str) -> str:
    """Use a deterministic ASCII title so Kaggle cannot silently change the kernel ID."""
    if not re.fullmatch(r"[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*", title):
        raise ValueError("Notebook başlığı yalnız ASCII harf/rakam, boşluk ve tire içermeli")
    return re.sub(r"[ -]+", "-", title).lower()


def prepare_notebook_package(
    kernel: str,
    dataset: str,
    runner: Path,
    title: str,
    *,
    enable_internet: bool,
    source_replacements: tuple[tuple[str, str], ...] = (),
) -> Path:
    """Create a private Kaggle script package, refusing to overwrite a package."""
    kernel, dataset = validate_handle(kernel), validate_handle(dataset)
    _, slug = kernel.split("/", maxsplit=1)
    if notebook_title_slug(title) != slug:
        raise ValueError("Notebook başlığının Kaggle slug'ı --kernel slug'ı ile aynı olmalı")
    source = runner_path(runner)
    rendered = source.read_text(encoding="utf-8")
    for old, new in source_replacements:
        if not old or rendered.count(old) != 1:
            raise ValueError("Notebook kaynak dönüşümü benzersiz değil")
        rendered = rendered.replace(old, new, 1)
    if dataset not in rendered:
        raise ValueError("Runner içindeki private Dataset yolu --dataset ile eşleşmiyor")
    package = kernel_package_directory(kernel)
    if package.exists():
        raise FileExistsError("Notebook paketi zaten var; önce içeriği inceleyip bilinçli olarak kaldırın")
    package.mkdir(parents=True)
    (package / "run.py").write_text(rendered, encoding="utf-8")
    metadata = {
        "id": kernel,
        "title": title,
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true",
        "enable_internet": "true" if enable_internet else "false",
        "dataset_sources": [dataset],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (package / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return package


def load_kernel_metadata(package: Path, kernel: str, dataset: str) -> dict[str, object]:
    package = private_directory(package)
    metadata_path = package / "kernel-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Notebook metadata dosyası okunamadı") from exc
    if not isinstance(metadata, dict):
        raise TypeError("Notebook metadata nesne olmalı")
    if metadata.get("id") != validate_handle(kernel) or metadata.get("is_private") != "true":
        raise ValueError("Notebook handle veya private ayarı doğrulanamadı")
    if metadata.get("dataset_sources") != [validate_handle(dataset)]:
        raise ValueError("Notebook Dataset kaynağı doğrulanamadı")
    code_file = metadata.get("code_file")
    if not isinstance(code_file, str) or not (package / code_file).is_file():
        raise ValueError("Notebook code_file pakette bulunamadı")
    return metadata


def kaggle_cli() -> str:
    local = Path(sys.executable).with_name("kaggle")
    if local.is_file():
        return str(local)
    executable = shutil.which("kaggle")
    if not executable:
        raise RuntimeError("Kaggle CLI kurulu değil; apps/api/.venv içinde kaggle paketini yükleyin")
    return executable


def run_cli(arguments: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [kaggle_cli(), *arguments], check=True, text=True, capture_output=capture_output
    )


def push_notebook(package: Path, kernel: str, dataset: str, timeout: int, accelerator: str) -> None:
    load_kernel_metadata(package, kernel, dataset)
    run_cli(
        [
            "kernels",
            "push",
            "--path",
            str(private_directory(package)),
            "--timeout",
            str(timeout),
            "--accelerator",
            accelerator,
        ]
    )


def notebook_status(kernel: str) -> str:
    result = run_cli(["kernels", "status", validate_handle(kernel)], capture_output=True)
    return result.stdout.strip()


def output_directory(kernel: str) -> Path:
    owner, slug = validate_handle(kernel).split("/", maxsplit=1)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = private_root() / "kaggle-notebook-outputs" / owner / slug / timestamp
    destination.mkdir(parents=True)
    return destination


def output_filename_pattern(filename: str) -> str:
    """Match one allowlisted output name whether Kaggle preserves its run directory or not."""
    return rf"^(?:.*/)?{re.escape(filename)}$"


def output_filenames_pattern(filenames: tuple[str, ...]) -> str:
    """Match only allowlisted report names in one Kaggle download request."""
    if not filenames:
        raise ValueError("En az bir izinli çıktı dosyası gerekli")
    return rf"^(?:.*/)?(?:{'|'.join(re.escape(filename) for filename in filenames)})$"


def download_summaries(kernel: str) -> tuple[Path, list[dict[str, object]]]:
    """Download only explicit content-free report filenames to a fresh private folder."""
    kernel = validate_handle(kernel)
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(),
            "kernels",
            "output",
            kernel,
            "--path",
            str(destination),
            "--force",
            "--quiet",
            "--file-pattern",
            output_filenames_pattern(SUMMARY_FILENAMES),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    downloaded = [path for path in destination.rglob("*") if path.is_file()]
    # Kaggle CLI materialises a technical kernel log next to matched files.
    # It is never an accepted report, nor is it recorded in the manifest.
    _, kernel_slug = kernel.split("/", maxsplit=1)
    transient_log = f"{kernel_slug}.log"
    unexpected = [
        path.name
        for path in downloaded
        if path.name not in {*SUMMARY_FILENAMES, transient_log}
    ]
    if unexpected:
        raise RuntimeError("İndirme allowlist dışı dosya üretti: " + ", ".join(sorted(unexpected)))
    accepted = [path for path in downloaded if path.name in SUMMARY_FILENAMES]
    accepted_names = {path.name for path in accepted}
    results = [
        {"filename": filename, "downloaded": result.returncode == 0 and filename in accepted_names}
        for filename in SUMMARY_FILENAMES
    ]
    manifest = [
        {"path": str(path.relative_to(destination)), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(accepted)
    ]
    (destination / "download_manifest.json").write_text(
        json.dumps({"kernel": kernel, "files": manifest, "attempts": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination, results


def tts_audio_expectations(run_records_path: Path) -> tuple[str, dict[str, str]]:
    """Read only generated audio IDs and hashes from a private synthesis report."""
    path = private_path(run_records_path)
    if not path.is_file():
        raise ValueError("Private TTS synthesis kayıt raporu bulunamadı")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        candidate, records = payload["candidate"], payload["records"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Private TTS synthesis kayıt raporu okunamadı") from exc
    if (
        payload.get("schema_version") != "tts-synthesis-run-v1"
        or not isinstance(candidate, str)
        or not 1 <= len(candidate) <= 100
        or not isinstance(records, list)
        or not 1 <= len(records) <= MAX_TTS_AUDIO_FILES
    ):
        raise ValueError("Private TTS synthesis kayıt şeması geçersiz")
    expectations: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("Private TTS synthesis kaydı geçersiz")
        item_id, status, audio_hash = record.get("id"), record.get("status"), record.get("audio_sha256")
        if (
            not isinstance(item_id, str)
            or not TTS_AUDIO_ID_PATTERN.fullmatch(item_id)
            or status != "generated"
            or not isinstance(audio_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", audio_hash)
            or item_id in expectations
        ):
            raise ValueError("Private TTS synthesis kaydı geçersiz")
        expectations[item_id] = audio_hash
    return candidate, expectations


def download_tts_audio(kernel: str, run_records_path: Path) -> Path:
    """Download exactly the generated private WAVs and verify each sealed hash."""
    kernel = validate_handle(kernel)
    candidate, expected_hashes = tts_audio_expectations(run_records_path)
    expected_filenames = tuple(f"{item_id}.wav" for item_id in expected_hashes)
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(),
            "kernels",
            "output",
            kernel,
            "--path",
            str(destination),
            "--force",
            "--quiet",
            "--file-pattern",
            output_filenames_pattern(expected_filenames),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    _, kernel_slug = kernel.split("/", maxsplit=1)
    transient_log = f"{kernel_slug}.log"
    allowed_names = {*expected_filenames, transient_log}
    downloaded = [path for path in destination.rglob("*") if path.is_file()]
    unexpected = [path.name for path in downloaded if path.name not in allowed_names]
    files_by_name: dict[str, list[Path]] = {name: [] for name in expected_filenames}
    for path in downloaded:
        if path.name in files_by_name:
            files_by_name[path.name].append(path)
    if result.returncode != 0 or unexpected or any(len(paths) != 1 for paths in files_by_name.values()):
        raise RuntimeError("Yalnız doğrulanmış private TTS WAV dosyaları indirilemedi")
    verified_files = []
    for item_id, expected_hash in expected_hashes.items():
        path = files_by_name[f"{item_id}.wav"][0]
        if sha256(path) != expected_hash:
            raise RuntimeError("Private TTS WAV checksum uyuşmuyor")
        verified_files.append(path)
    manifest = {
        "schema_version": "kaggle-tts-audio-download-v1",
        "kernel": kernel,
        "candidate": candidate,
        "run_records_relative_path": str(private_path(run_records_path).relative_to(private_root())),
        "files": [
            {
                "id": path.stem,
                "path": str(path.relative_to(destination)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(verified_files)
        ],
    }
    (destination / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def tts_gold_ids(gold_path: Path) -> set[str]:
    """Read only private Gold identifiers to bound a candidate transcript download."""
    path = private_path(gold_path)
    if not path.is_file():
        raise ValueError("Private TTS Gold dosyası bulunamadı")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["items"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Private TTS Gold dosyası okunamadı") from exc
    if payload.get("schema_version") != "tts-gold-v1" or not isinstance(items, list) or not items:
        raise ValueError("Private TTS Gold şeması geçersiz")
    ids = {
        item.get("id")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and TTS_AUDIO_ID_PATTERN.fullmatch(item["id"])
    }
    if len(ids) != len(items):
        raise ValueError("Private TTS Gold kimlikleri geçersiz")
    return ids


def validate_tts_candidate_transcripts(path: Path, expected_ids: set[str], expected_candidate: str) -> None:
    """Keep untrusted private ASR text out unless every field has the expected shape."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        results = payload["results"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Private TTS aday transkripti okunamadı") from exc
    if (
        set(payload) != {"schema_version", "candidate", "results"}
        or payload.get("schema_version") != "tts-candidate-v1"
        or payload.get("candidate") != expected_candidate
        or not isinstance(results, list)
        or len(results) > len(expected_ids)
    ):
        raise ValueError("Private TTS aday transkript şeması geçersiz")
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict) or set(result) != {"id", "observed_spoken_text"}:
            raise ValueError("Private TTS aday transkript kaydı geçersiz")
        item_id, observed = result.get("id"), result.get("observed_spoken_text")
        if (
            not isinstance(item_id, str)
            or item_id not in expected_ids
            or item_id in seen
            or not isinstance(observed, str)
            or not observed.strip()
            or len(observed) > MAX_TTS_TRANSCRIPT_CHARS
        ):
            raise ValueError("Private TTS aday transkript kaydı geçersiz")
        seen.add(item_id)


def download_tts_candidate_transcripts(kernel: str, gold_path: Path, expected_candidate: str) -> Path:
    """Download one schema-checked private ASR transcript candidate for local scoring."""
    kernel = validate_handle(kernel)
    expected_ids = tts_gold_ids(gold_path)
    if not isinstance(expected_candidate, str) or not 1 <= len(expected_candidate) <= 100:
        raise ValueError("Beklenen TTS aday adı geçersiz")
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(),
            "kernels",
            "output",
            kernel,
            "--path",
            str(destination),
            "--force",
            "--quiet",
            "--file-pattern",
            output_filename_pattern(TTS_CANDIDATE_TRANSCRIPTS_FILENAME),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    transcripts = [path for path in destination.rglob(TTS_CANDIDATE_TRANSCRIPTS_FILENAME) if path.is_file()]
    _, kernel_slug = kernel.split("/", maxsplit=1)
    transient_log = f"{kernel_slug}.log"
    unexpected = [
        path.name
        for path in destination.rglob("*")
        if path.is_file() and path.name not in {TTS_CANDIDATE_TRANSCRIPTS_FILENAME, transient_log}
    ]
    if result.returncode != 0 or len(transcripts) != 1 or unexpected:
        raise RuntimeError("Yalnız izinli private TTS aday transkripti indirilemedi")
    transcript_path = transcripts[0]
    validate_tts_candidate_transcripts(transcript_path, expected_ids, expected_candidate)
    manifest = {
        "schema_version": "kaggle-tts-candidate-transcript-download-v1",
        "kernel": kernel,
        "gold_relative_path": str(private_path(gold_path).relative_to(private_root())),
        "candidate": expected_candidate,
        "file": {
            "path": str(transcript_path.relative_to(destination)),
            "sha256": sha256(transcript_path),
            "bytes": transcript_path.stat().st_size,
        },
    }
    (destination / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return transcript_path


def symbol_input_ids(input_manifest: Path) -> set[str]:
    """Read IDs only from the sealed candidate manifest; never read local Gold."""
    path = private_path(input_manifest)
    if not path.is_file():
        raise ValueError("Symbol input manifesti private dosya olarak bulunamadı")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assets = payload["assets"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Symbol input manifesti okunamadı") from exc
    if payload.get("schema_version") != "symbol-cell-benchmark-input-v1" or not isinstance(assets, list):
        raise ValueError("Symbol input şeması geçersiz")
    ids = {item.get("id") for item in assets if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if not ids or len(ids) != len(assets) or "expected" in payload:
        raise ValueError("Symbol input manifesti aday benchmark sınırını karşılamıyor")
    return ids


def validate_symbol_predictions(path: Path, expected_ids: set[str]) -> None:
    """Reject arbitrary notebook output before it enters the private evaluation path."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        predictions = payload["predictions"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Symbol prediction dosyası okunamadı") from exc
    if (
        set(payload) != {"schema_version", "candidate", "predictions"}
        or payload.get("schema_version") != "symbol-cell-predictions-v1"
        or not isinstance(payload.get("candidate"), str)
        or not 1 <= len(payload["candidate"]) <= 80
        or not isinstance(predictions, list)
    ):
        raise ValueError("Symbol prediction şeması geçersiz")
    seen: set[str] = set()
    for item in predictions:
        if not isinstance(item, dict) or set(item) != {"id", "prediction", "status"}:
            raise ValueError("Symbol prediction alanları geçersiz")
        asset_id, prediction, status = item.get("id"), item.get("prediction"), item.get("status")
        if (
            not isinstance(asset_id, str)
            or asset_id not in expected_ids
            or asset_id in seen
            or not isinstance(prediction, str)
            or len(prediction) > 128
            or status not in {"completed", "no-text", "failed"}
        ):
            raise ValueError("Symbol prediction kaydı geçersiz")
        seen.add(asset_id)
    if seen != expected_ids:
        raise ValueError("Symbol prediction kayıtları aday input hücreleriyle eşleşmiyor")


def download_symbol_predictions(kernel: str, input_manifest: Path) -> Path:
    """Download exactly one schema-checked private prediction file for local scoring."""
    expected_ids = symbol_input_ids(input_manifest)
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(),
            "kernels",
            "output",
            validate_handle(kernel),
            "--path",
            str(destination),
            "--force",
            "--quiet",
            "--file-pattern",
            output_filename_pattern(SYMBOL_PREDICTIONS_FILENAME),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    prediction_files = [path for path in destination.rglob(SYMBOL_PREDICTIONS_FILENAME) if path.is_file()]
    # Kaggle CLI always materialises its technical kernel log beside a matched
    # output. It is not accepted as benchmark input or included in the manifest.
    _, kernel_slug = validate_handle(kernel).split("/", maxsplit=1)
    transient_log = f"{kernel_slug}.log"
    unexpected = [
        path.name
        for path in destination.rglob("*")
        if path.is_file() and path.name not in {SYMBOL_PREDICTIONS_FILENAME, transient_log}
    ]
    if result.returncode != 0 or len(prediction_files) != 1 or unexpected:
        raise RuntimeError("Yalnız izinli symbol prediction dosyası indirilemedi")
    predictions = prediction_files[0]
    validate_symbol_predictions(predictions, expected_ids)
    manifest = {
        "schema_version": "kaggle-symbol-prediction-download-v1",
        "kernel": validate_handle(kernel),
        "input_manifest_relative_path": str(private_path(input_manifest).relative_to(private_root())),
        "files": [{"path": str(predictions.relative_to(destination)), "sha256": sha256(predictions), "bytes": predictions.stat().st_size}],
    }
    (destination / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return predictions


def formula_input_ids(input_manifest: Path) -> set[str]:
    """Read formula region IDs without ever loading the separate Gold file."""
    path = private_path(input_manifest)
    if not path.is_file():
        raise ValueError("Formül input manifesti private dosya olarak bulunamadı")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        regions = payload["regions"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Formül input manifesti okunamadı") from exc
    if payload.get("schema_version") != "formula-region-benchmark-input-v1" or not isinstance(regions, list):
        raise ValueError("Formül input şeması geçersiz")
    ids = {item.get("id") for item in regions if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if not ids or len(ids) != len(regions) or "expected" in payload:
        raise ValueError("Formül input manifesti aday benchmark sınırını karşılamıyor")
    return ids


def validate_formula_predictions(path: Path, expected_ids: set[str]) -> None:
    """Accept only bounded OCR output from the registered private formula run."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        predictions = payload["predictions"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Formül prediction dosyası okunamadı") from exc
    if (
        set(payload) != {"schema_version", "candidate", "predictions"}
        or payload.get("schema_version") != "formula-region-predictions-v1"
        or not isinstance(payload.get("candidate"), str)
        or not 1 <= len(payload["candidate"]) <= 80
        or not isinstance(predictions, list)
    ):
        raise ValueError("Formül prediction şeması geçersiz")
    seen: set[str] = set()
    for item in predictions:
        if not isinstance(item, dict) or set(item) != {"id", "visible_notation", "confidence", "status"}:
            raise ValueError("Formül prediction alanları geçersiz")
        region_id, notation, confidence, status = (
            item.get("id"), item.get("visible_notation"), item.get("confidence"), item.get("status")
        )
        if (
            not isinstance(region_id, str)
            or region_id not in expected_ids
            or region_id in seen
            or not isinstance(notation, str)
            or len(notation) > 1000
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
            or status not in {"completed", "no-formula", "failed"}
        ):
            raise ValueError("Formül prediction kaydı geçersiz")
        seen.add(region_id)
    if seen != expected_ids:
        raise ValueError("Formül prediction kayıtları aday input bölgeleriyle eşleşmiyor")


def quarantine_oversize_formula_predictions(path: Path, expected_ids: set[str]) -> tuple[Path, list[str]]:
    """Replace only overlong model strings with failed records before import.

    Formula OCR occasionally hallucinates a page-sized sequence for a bad crop.
    It must not prevent valid independent rows from reaching teacher review, nor
    must that unbounded string enter the application database.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"schema_version", "candidate", "predictions"} or payload.get("schema_version") != "formula-region-predictions-v1":
        raise ValueError("Formül prediction şeması geçersiz")
    cleaned, quarantined, seen = [], [], set()
    for item in payload.get("predictions", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] not in expected_ids or item["id"] in seen:
            raise ValueError("Formül prediction kayıtları aday input bölgeleriyle eşleşmiyor")
        seen.add(item["id"])
        notation = item.get("visible_notation")
        if isinstance(notation, str) and len(notation) > 1000:
            quarantined.append(item["id"])
            cleaned.append({"id": item["id"], "visible_notation": "", "confidence": 0.0, "status": "failed"})
        else:
            cleaned.append(item)
    if seen != expected_ids:
        raise ValueError("Formül prediction kayıtları aday input bölgeleriyle eşleşmiyor")
    safe_path = path.with_name("formula_predictions.safe.json")
    safe_path.write_text(json.dumps({"schema_version": payload["schema_version"], "candidate": payload["candidate"], "predictions": cleaned}, ensure_ascii=False), encoding="utf-8")
    validate_formula_predictions(safe_path, expected_ids)
    return safe_path, quarantined


def download_formula_predictions(kernel: str, input_manifest: Path) -> Path:
    """Download precisely one validated private formula OCR result file."""
    expected_ids = formula_input_ids(input_manifest)
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(), "kernels", "output", validate_handle(kernel), "--path", str(destination),
            "--force", "--quiet", "--file-pattern", output_filename_pattern(FORMULA_PREDICTIONS_FILENAME),
        ], text=True, capture_output=True, check=False,
    )
    prediction_files = [path for path in destination.rglob(FORMULA_PREDICTIONS_FILENAME) if path.is_file()]
    _, kernel_slug = validate_handle(kernel).split("/", maxsplit=1)
    transient_log = f"{kernel_slug}.log"
    unexpected = [
        path.name for path in destination.rglob("*")
        if path.is_file() and path.name not in {FORMULA_PREDICTIONS_FILENAME, transient_log}
    ]
    if result.returncode != 0 or len(prediction_files) != 1 or unexpected:
        raise RuntimeError("Yalnız izinli formül prediction dosyası indirilemedi")
    predictions, quarantined = quarantine_oversize_formula_predictions(prediction_files[0], expected_ids)
    manifest = {
        "schema_version": "kaggle-formula-prediction-download-v1",
        "kernel": validate_handle(kernel),
        "input_manifest_relative_path": str(private_path(input_manifest).relative_to(private_root())),
        "files": [{"path": str(predictions.relative_to(destination)), "sha256": sha256(predictions), "bytes": predictions.stat().st_size}],
        "quarantined_prediction_ids": quarantined,
    }
    (destination / "download_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM safe Kaggle private Dataset and Notebook operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Yalnız Kaggle kimlik doğrulamasını denetler")
    for name in ("prepare-dataset", "upload-dataset"):
        command = commands.add_parser(name)
        command.add_argument("--source-dir", type=Path, required=True)
        command.add_argument("--handle", required=True)
        command.add_argument("--version-notes", required=True)
        if name == "upload-dataset":
            command.add_argument("--apply", action="store_true", help="Uzak Dataset sürümü oluşturmayı açıkça onaylar")
    package = commands.add_parser("prepare-notebook", help="Private Kaggle script paketini yalnız yerelde oluşturur")
    package.add_argument("--kernel", required=True)
    package.add_argument("--dataset", required=True)
    package.add_argument("--runner", type=Path, required=True)
    package.add_argument("--title", required=True)
    package.add_argument("--internet", action="store_true", help="Yalnız model/paket indirmesi gerektiğinde etkinleştir")
    push = commands.add_parser("push-notebook", help="Private paketi Kaggle'a gönderir ve koşumu başlatır")
    push.add_argument("--package-dir", type=Path, required=True)
    push.add_argument("--kernel", required=True)
    push.add_argument("--dataset", required=True)
    push.add_argument("--timeout", type=int, default=3600)
    push.add_argument("--accelerator", default="NvidiaTeslaT4")
    push.add_argument("--apply", action="store_true", help="Uzak private Notebook oluşturma/güncelleme ve koşumu açıkça onaylar")
    status = commands.add_parser("notebook-status", help="Notebook durumunu yalnız-okunur sorgular")
    status.add_argument("--kernel", required=True)
    output = commands.add_parser("download-summaries", help="Yalnız izinli içeriksiz özet JSON'larını indirir")
    output.add_argument("--kernel", required=True)
    predictions = commands.add_parser(
        "download-symbol-predictions", help="Yalnız şema-doğrulanmış private sembol tahminlerini indirir"
    )
    predictions.add_argument("--kernel", required=True)
    predictions.add_argument("--input-manifest", type=Path, required=True)
    formula_predictions = commands.add_parser(
        "download-formula-predictions", help="Yalnız şema-doğrulanmış private formül OCR sonuçlarını indirir"
    )
    formula_predictions.add_argument("--kernel", required=True)
    formula_predictions.add_argument("--input-manifest", type=Path, required=True)
    audio = commands.add_parser(
        "download-tts-audio", help="Yalnız synthesis raporunda checksum'ı bulunan private TTS WAV'lerini indirir"
    )
    audio.add_argument("--kernel", required=True)
    audio.add_argument("--run-records", type=Path, required=True)
    transcripts = commands.add_parser(
        "download-tts-candidate-transcripts",
        help="Yalnız Gold kimlikleriyle şema-doğrulanmış private TTS aday transkriptini indirir",
    )
    transcripts.add_argument("--kernel", required=True)
    transcripts.add_argument("--gold", type=Path, required=True)
    transcripts.add_argument("--expected-candidate", required=True)
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify(), ensure_ascii=False))
        return 0
    if args.command == "notebook-status":
        print(json.dumps({"kernel": validate_handle(args.kernel), "status": notebook_status(args.kernel)}, ensure_ascii=False))
        return 0
    if args.command == "prepare-notebook":
        package = prepare_notebook_package(args.kernel, args.dataset, args.runner, args.title, enable_internet=args.internet)
        record = write_notebook_record("prepare-notebook", args.kernel, args.dataset, package, applied=False)
        print(json.dumps({"status": "prepared-not-pushed", "package": str(package), "record": str(record)}, ensure_ascii=False))
        return 0
    if args.command == "push-notebook":
        package = private_directory(args.package_dir)
        load_kernel_metadata(package, args.kernel, args.dataset)
        if not args.apply:
            record = write_notebook_record("push-notebook", args.kernel, args.dataset, package, applied=False, details={"timeout": args.timeout, "accelerator": args.accelerator})
            print(json.dumps({"status": "dry-run-not-pushed", "record": str(record)}, ensure_ascii=False))
            return 0
        push_notebook(package, args.kernel, args.dataset, args.timeout, args.accelerator)
        record = write_notebook_record("push-notebook", args.kernel, args.dataset, package, applied=True, details={"timeout": args.timeout, "accelerator": args.accelerator})
        print(json.dumps({"status": "pushed-and-started", "record": str(record)}, ensure_ascii=False))
        return 0
    if args.command == "download-summaries":
        destination, attempts = download_summaries(args.kernel)
        print(json.dumps({"status": "download-complete", "output": str(destination), "attempts": attempts}, ensure_ascii=False))
        return 0
    if args.command == "download-symbol-predictions":
        prediction_path = download_symbol_predictions(args.kernel, args.input_manifest)
        print(json.dumps({"status": "download-complete", "predictions": str(prediction_path)}, ensure_ascii=False))
        return 0
    if args.command == "download-formula-predictions":
        prediction_path = download_formula_predictions(args.kernel, args.input_manifest)
        print(json.dumps({"status": "download-complete", "predictions": str(prediction_path)}, ensure_ascii=False))
        return 0
    if args.command == "download-tts-audio":
        destination = download_tts_audio(args.kernel, args.run_records)
        print(json.dumps({"status": "download-complete", "output": str(destination)}, ensure_ascii=False))
        return 0
    if args.command == "download-tts-candidate-transcripts":
        transcript_path = download_tts_candidate_transcripts(args.kernel, args.gold, args.expected_candidate)
        print(json.dumps({"status": "download-complete", "transcripts": str(transcript_path)}, ensure_ascii=False))
        return 0
    source, handle = private_directory(args.source_dir), validate_handle(args.handle)
    if args.command == "prepare-dataset":
        record = write_record("prepare-dataset", handle, source, applied=False, version_notes=args.version_notes)
        print(json.dumps({"status": "prepared-not-uploaded", "record": str(record)}, ensure_ascii=False))
        return 0
    if not args.apply:
        record = write_record("upload-dataset", handle, source, applied=False, version_notes=args.version_notes)
        print(json.dumps({"status": "dry-run-not-uploaded", "record": str(record)}, ensure_ascii=False))
        return 0
    upload_dataset(source, handle, args.version_notes)
    record = write_record("upload-dataset", handle, source, applied=True, version_notes=args.version_notes)
    print(json.dumps({"status": "uploaded", "record": str(record)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
