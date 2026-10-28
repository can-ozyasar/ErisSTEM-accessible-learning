"""Source-bound, answer-key-isolated coaching for approved history questions."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

STAGES = ("soru_analizi", "hatirlayani_ortaya_cikar", "kanitla_bag_kur", "sik_elemesi", "ogrenci_yaniti", "gerekceli_aciklama")
# A local model may phrase the disclosure in several ways.  This is a safety
# backstop; the answer label is still never included in its prompt.
ANSWER_LABEL = re.compile(
    r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|şık\s*[abcde]\b|\b[abcde]\s*(?:şıkkı|şık|seçeneği)\b)",
    re.IGNORECASE,
)


class CoachReply(BaseModel):
    stage: str
    error_type: str
    student_prompt: str = Field(min_length=1, max_length=600)
    short_spoken_text: str = Field(min_length=1, max_length=240)
    source_ids: list[str] = Field(default_factory=list, max_length=3)
    abstain_reason: str | None = Field(default=None, max_length=240)
    can_reveal_explanation: bool = False
    timings_ms: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class CoachContext:
    question_id: str
    question_text: str
    choice_text: str | None
    section_title: str
    source_ids: list[str]
    evidence: str
    error_type: str


def next_stage(previous: str | None, submit_answer: bool) -> str:
    if previous is None:
        return STAGES[0]
    if previous in {"sik_elemesi", "ogrenci_yaniti"} and submit_answer:
        return "gerekceli_aciklama"
    try:
        return STAGES[min(STAGES.index(previous) + 1, len(STAGES) - 2)]
    except ValueError:
        return STAGES[0]


def _sentence(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return "Soruyu ve kaynağı birlikte inceleyelim."
    match = re.match(r"^(.{1,220}?[.!?])(?:\s|$)", value)
    return (match.group(1) if match else value[:220]).strip()


def _fallback(stage: str, context: CoachContext, submitted_choice: str | None,
              answer_label: str | None) -> str:
    if stage == "soru_analizi":
        return "Birlikte bakalım: soru senden hangi bilgiyi bulmanı istiyor? Kökün en önemli sözcüğü hangisi?"
    if stage == "hatirlayani_ortaya_cikar":
        prompts = {"tarih": "Olayın adını hatırlamaya çalış. Bu olayın yanındaki tarih hangi döneme ait olabilir?",
                   "yer": "Önce olayın geçtiği yeri gözünde canlandır. Deniz kıyısı mı, iç kesim mi?",
                   "kronoloji": "İki olayı sıraya koymayı dene. Hangisi ötekinden önce yaşanmış olabilir?",
                   "neden_sonuc": "Önce ne değişmiş olabilir, sonra bunun sonucu ne olmuş olabilir?",
                   "kisi": "Kişinin yaptığı işi hatırlıyor musun? Bu iş sana kimi hatırlatıyor?",
                   "kaynak_yorumu": "Metnin kesin söylediği şey ile senin eklediğin yorum aynı mı?",
                   "asiri_genelleme": "Seçenekte ‘her zaman’ ya da ‘tamamı’ gibi çok geniş bir söz var mı?"}
        return prompts[context.error_type]
    if stage == "kanitla_bag_kur":
        return "Kaynakta bu soruya yardım eden bir cümle var. O cümledeki hangi sözcük seçeneğini destekliyor ya da zayıflatıyor?"
    if stage == "sik_elemesi":
        if context.choice_text:
            return "Seçtiğin şıktaki ifadeyi kaynakla karşılaştır. Hangi kelime ya da tarih onu destekliyor veya zayıflatıyor?"
        return "Şıkları sırayla ele. Kaynakla uyuşmayan ilk ifadeyi ve nedenini söyleyebilir misin?"
    if stage == "ogrenci_yaniti":
        return "Bir şık seçip kısa gerekçeni yaz. Hazır olduğunda yanıtını birlikte kontrol edelim."
    if not answer_label:
        return "Yanıt anahtarı bu soru için kaynakla ayrıca doğrulanmamış. Kaynaktaki kanıtla gerekçeni birlikte karşılaştıralım."
    if submitted_choice == answer_label:
        return "Seçimin kaynak anahtarıyla uyuşuyor. Gerekçeni, MEB kitabındaki kanıtla bir cümlede bağlayalım."
    return "Burada iki bilgi birbirine karışmış olabilir. Kaynaktaki belirleyici ifadeye yeniden bak; şimdi hangi seçeneği zayıflattığını kendi sözünle anlat."


def _prompt(stage: str, context: CoachContext, learner_message: str) -> str:
    """Never include an answer label, other choices, or source coordinates in the model prompt."""
    return "\n".join((
        "Sen 9. sınıf tarih soru koçusun.",
        "Yalnız Türkçe, sade, en fazla iki cümlelik bir ipucu üret.",
        "Doğru cevabı, doğru şıkkı, cevap anahtarını veya kesin çözümü söyleme.",
        "Kaynakta olmayan bilgi ekleme. Kaynak yetersizse bunu açıkça söyle.",
        f"Aşama: {stage}",
        f"Soru: {context.question_text}",
        f"Öğrencinin seçtiği ifade: {context.choice_text or 'yok'}",
        f"MEB kanıtı: {context.evidence}",
        f"Öğrenci mesajı: {learner_message}",
    ))


def _llm_hint(stage: str, context: CoachContext, learner_message: str) -> tuple[str | None, dict[str, int]]:
    endpoint = os.getenv("LOCAL_TUTOR_LLM_URL", "").strip()
    if not endpoint:
        return None, {"llm": 0, "first_token": 0}
    payload = {"prompt": _prompt(stage, context, learner_message), "max_tokens": 96,
               "temperature": 0.2, "response_format": "text"}
    started = time.monotonic()
    try:
        request = Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=8) as response:  # nosec B310 -- local operator configured endpoint
            decoded = json.loads(response.read().decode("utf-8"))
        text = decoded.get("text") if isinstance(decoded, dict) else None
        if not isinstance(text, str) or not text.strip() or ANSWER_LABEL.search(text):
            return None, {"llm": int((time.monotonic() - started) * 1000), "first_token": 0}
        elapsed = int((time.monotonic() - started) * 1000)
        first_token = decoded.get("first_token_ms") if isinstance(decoded, dict) else None
        return text.strip()[:600], {"llm": elapsed, "first_token": first_token if isinstance(first_token, int) else 0}
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None, {"llm": int((time.monotonic() - started) * 1000), "first_token": 0}


def coach(context: CoachContext, previous_stage: str | None, learner_message: str,
          submit_answer: bool, submitted_choice: str | None, answer_label: str | None) -> CoachReply:
    stage = next_stage(previous_stage, submit_answer)
    started = time.monotonic()
    if not context.source_ids:
        text = "Bu soru için öğretmen onaylı MEB kanıtı henüz yok. Soru kökünün senden ne istediğini kendi sözlerinle anlatır mısın?"
        return CoachReply(stage=stage, error_type=context.error_type, student_prompt=text, short_spoken_text=_sentence(text),
                          abstain_reason="approved_source_unavailable",
                          timings_ms={"total": int((time.monotonic() - started) * 1000)})
    model_text, model_timings = _llm_hint(stage, context, learner_message)
    if model_text and ANSWER_LABEL.search(model_text):
        model_text = None
    text = model_text or _fallback(stage, context, submitted_choice, answer_label if stage == "gerekceli_aciklama" else None)
    return CoachReply(stage=stage, error_type=context.error_type, student_prompt=text, short_spoken_text=_sentence(text),
                      source_ids=context.source_ids, can_reveal_explanation=stage == "gerekceli_aciklama",
                      timings_ms={**model_timings, "total": int((time.monotonic() - started) * 1000)})
