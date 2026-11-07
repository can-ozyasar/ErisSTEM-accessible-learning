"""Adapters that connect the approved AYT graph to local model services.

The graph/tutor core deliberately depends on small protocols.  This module
provides the production adapters without adding a hosted API dependency:
Qwen3 is reached through the private Docker endpoint and the existing local
Turkish TTS boundary writes a WAV to the cache path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .ayt_knowledge_graph import KnowledgeGraph, LocalLLM, SocraticTutorOrchestrator, TTSSynthesizer
from .local_tts import LocalTtsUnavailable, synthesize_history_text


class LocalLLMUnavailable(RuntimeError):
    """The configured local model service cannot produce a response."""


class LocalHTTPLLM(LocalLLM):
    """Bounded adapter for the private ``tutor-llm`` HTTP service."""

    def __init__(self, endpoint: str | None = None, *, timeout: float | None = None):
        self.endpoint = (endpoint or os.getenv("LOCAL_TUTOR_LLM_URL", "")).strip()
        if not self.endpoint.startswith("http://"):
            raise ValueError("Yerel LLM uç noktası http:// ile başlamalı")
        self.timeout = timeout if timeout is not None else float(os.getenv("LOCAL_TUTOR_LLM_TIMEOUT_SECONDS", "8"))
        if not 1 <= self.timeout <= 120:
            raise ValueError("Yerel LLM zaman aşımı 1 ile 120 saniye arasında olmalı")
        self.last_first_token_ms = 0

    def generate(self, system_prompt: str, user_prompt: str, *, max_tokens: int) -> str:
        if not 1 <= max_tokens <= 96:
            raise ValueError("max_tokens 1 ile 96 arasında olmalı")
        # The model container accepts one bounded prompt and has no source
        # mounts.  Delimit the two parts so system rules remain unambiguous.
        # tutor-llm deliberately caps requests at 6000 chars.  Keep the
        # beginning of each bounded section so a malformed long question
        # cannot turn into a remote retry or a service-side 422.
        system = " ".join(system_prompt.split())[:1800]
        user = " ".join(user_prompt.split())[:4000]
        prompt = f"[SİSTEM]\n{system}\n[/SİSTEM]\n[KULLANICI]\n{user}\n[/KULLANICI]"
        payload = {"prompt": prompt, "max_tokens": max_tokens, "temperature": 0.2,
                   "response_format": "text"}
        request = Request(self.endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json", "Accept": "application/json"},
                          method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:  # nosec B310: operator-configured local endpoint
                body = response.read(64 * 1024)
            decoded = json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            raise LocalLLMUnavailable("yerel_llm_kullanılamıyor") from error
        text = decoded.get("text") if isinstance(decoded, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LocalLLMUnavailable("yerel_llm_geçersiz_yanıt")
        self.last_first_token_ms = int(decoded.get("first_token_ms", 0) or 0)
        return text.strip()


class LocalHistoryTTS(TTSSynthesizer):
    """Write one verified local-TTS WAV to the path supplied by AudioCache."""

    def synthesize(self, text: str, *, output_path: Path) -> None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(synthesize_history_text(text))
        except (LocalTtsUnavailable, OSError) as error:
            raise RuntimeError("yerel_tts_kullanılamıyor") from error


def load_approved_graph(path: Path, *, expected_checksum: str | None = None) -> KnowledgeGraph:
    """Load a graph only when it contains an approved runtime surface."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Research graphs intentionally reuse the strict graph schema so they
        # can be evaluated, but they must never become student runtime data
        # merely by being pointed to through an environment variable.
        if payload.get("research_only") is True or payload.get("runtime_enabled") is False:
            raise RuntimeError("araştırma_grafi_runtime_açılamaz")
        graph = KnowledgeGraph.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError("geçerli_ayt_grafi_yüklenemedi") from error
    if expected_checksum and graph.corpus_checksum != expected_checksum:
        raise RuntimeError("ayt_graf_checksum_eşleşmiyor")
    if not graph.approved_nodes() or not graph.approved_edges():
        raise RuntimeError("onaylı_ayt_grafi_yok")
    return graph


def build_local_orchestrator(graph_path: Path, *, cache_root: Path,
                             voice_version: str, llm_endpoint: str | None = None,
                             expected_checksum: str | None = None) -> SocraticTutorOrchestrator:
    """Build the local tutor or fail closed before any student request."""
    from .ayt_knowledge_graph import AudioCache, WeightedGraphSearch

    graph = load_approved_graph(graph_path, expected_checksum=expected_checksum)
    return SocraticTutorOrchestrator(
        WeightedGraphSearch(graph), LocalHTTPLLM(llm_endpoint),
        AudioCache(cache_root, voice_version), LocalHistoryTTS(),
    )
