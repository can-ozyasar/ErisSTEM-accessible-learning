"""Feature-gated HTTP boundary for the approved AYT graph tutor."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .auth import Role, require_roles
from .ayt_knowledge_graph import QuestionItem, TutorDialogueState
from .ayt_local_runtime import build_local_orchestrator


class AytTutorTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: QuestionItem
    state: TutorDialogueState | None = None
    learner_message: str = Field(default="", max_length=500)


class AytTutorReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: TutorDialogueState
    text: str = Field(min_length=1, max_length=600)
    audio_ids: list[str] = Field(default_factory=list, max_length=8)
    timings_ms: dict[str, int] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def _configured_runtime(graph_path: str, cache_root: str, voice_version: str,
                        llm_endpoint: str, expected_checksum: str):
    return build_local_orchestrator(Path(graph_path), cache_root=Path(cache_root),
                                    voice_version=voice_version,
                                    llm_endpoint=llm_endpoint or None,
                                    expected_checksum=expected_checksum or None)


def ayt_tutor_router() -> APIRouter:
    router = APIRouter(prefix="/v1/ayt-tutor", tags=["ayt-tutor"])
    student = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))

    def runtime():
        graph_path = os.getenv("AYT_APPROVED_GRAPH_PATH", "").strip()
        cache_root = os.getenv("AYT_TTS_CACHE_ROOT", "").strip()
        if not graph_path or not cache_root:
            raise HTTPException(503, "AYT onaylı grafi veya ses önbelleği yapılandırılmamış")
        try:
            return _configured_runtime(
                graph_path, cache_root,
                os.getenv("AYT_TTS_VOICE_VERSION", "tts-v5").strip() or "tts-v5",
                os.getenv("LOCAL_TUTOR_LLM_URL", "").strip(),
                os.getenv("AYT_GRAPH_CHECKSUM", "").strip(),
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(503, "AYT yerel koç runtime'ı hazır değil") from error

    @router.post("/turn", response_model=AytTutorReply)
    def turn(request: AytTutorTurn, _: Role = student):
        # A client cannot smuggle a private answer-key reference into the
        # source-bound runtime object.
        if request.question.answer_key_ref is not None:
            raise HTTPException(422, "Cevap anahtarı runtime sorusuna gönderilemez")
        service = runtime()
        try:
            state, text, audio_paths = service.start(
                request.question, request.state, request.learner_message,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return AytTutorReply(state=state, text=text,
                             audio_ids=[path.stem for path in audio_paths],
                             timings_ms=getattr(service, "last_timings", {}))

    @router.get("/audio/{audio_id}")
    def audio(audio_id: str, _: Role = student):
        if not re.fullmatch(r"[0-9a-f]{64}", audio_id):
            raise HTTPException(404, "Ses bulunamadı")
        root = os.getenv("AYT_TTS_CACHE_ROOT", "").strip()
        if not root:
            raise HTTPException(503, "AYT ses önbelleği yapılandırılmamış")
        path = (Path(root) / f"{audio_id}.wav").resolve()
        try:
            if Path(root).resolve() not in path.parents or not path.is_file():
                raise HTTPException(404, "Ses bulunamadı")
            body = path.read_bytes()
        except OSError as error:
            raise HTTPException(404, "Ses bulunamadı") from error
        return Response(body, media_type="audio/wav", headers={"Cache-Control": "private, max-age=31536000"})

    return router
