"""Source-bound, answer-key-isolated coaching for approved history questions."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

STAGES = (
    "soru_analizi", "hatirlayani_ortaya_cikar", "kanitla_bag_kur",
    "sik_elemesi", "ogrenci_yaniti", "gerekceli_aciklama",
)
# This is a backstop. The answer key and the other option texts never enter the
# local model prompt in the first place.
ANSWER_LABEL = re.compile(
    r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|şık\s*[abcde]\b|\b[abcde]\s*(?:şıkkı|şık|seçeneği)\b|"
    r"ilk\s+seçenek|son\s+seçenek|üstteki\s+seçenek|alttaki\s+seçenek)",
    re.IGNORECASE,
)


class CoachReply(BaseModel):
    stage: str
    error_type: str
    student_prompt: str = Field(min_length=1, max_length=600)
    short_spoken_text: str = Field(min_length=1, max_length=240)
    source_ids: list[str] = Field(default_factory=list, max_length=4)
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
    repeat_attempts: int = 0
    evidence_by_role: dict[str, str] = field(default_factory=dict)


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


def _short_evidence(value: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _fallback(stage: str, context: CoachContext, submitted_choice: str | None,
              answer_label: str | None, answer_choice_text: str | None) -> str:
    # After two attempts at the same option, give a concise source correction,
    # then ask the learner to articulate the conflict. The label remains hidden.
    if context.repeat_attempts >= 2 and stage != "gerekceli_aciklama":
        return f"Kaynaktaki ‘{_short_evidence(context.evidence, 150)}’ bilgisine yeniden bak. Bu bilgi seçtiğin ifadeyle uyuşuyor mu?"

    if stage == "soru_analizi":
        prompts = {
            "tarih": "Soru bir olayın zamanını mı, yoksa tarihle ilgili başka bir bilgiyi mi soruyor? Kökte bunu gösteren sözcük hangisi?",
            "yer": "Soru olayın nerede geçtiğini mi soruyor? Kökte yerle ilgili ipucu veren sözcük hangisi?",
            "kronoloji": "Soru olayları hangi sıraya koymanı istiyor? Önce ve sonra sözcüklerini kökte bulabiliyor musun?",
            "neden_sonuc": "Soru bir neden mi, yoksa ortaya çıkan sonucu mu arıyor? Kökün hangi sözü bunu söylüyor?",
            "kisi": "Soru bir kişinin yaptığı işi mi soruyor? Kökten hangi görevi araman gerektiğini çıkarırsın?",
            "kaynak_yorumu": "Soru metnin açıkça söylediğini mi, yoksa metinden çıkarılabilecek yorumu mu soruyor?",
            "asiri_genelleme": "Soru seçenekteki geniş bir yargıyı mı sınatıyor? ‘Her zaman’ ya da ‘tamamı’ gibi bir söz görüyor musun?",
            "genel": "Soru senden hangi bilgiyi bulmanı istiyor? Kökün en önemli sözcüğü hangisi?",
        }
        return prompts[context.error_type]
    if stage == "hatirlayani_ortaya_cikar":
        relation = context.evidence_by_role.get("relation") or context.evidence_by_role.get("context")
        if relation:
            return f"Kaynakta ‘{_short_evidence(relation, 150)}’ bilgisi var. Buradaki bağlantı sana neyi hatırlatıyor?"
        prompts = {
            "tarih": "Olayın adını hatırlamaya çalış. Bu olayın yanındaki tarih hangi döneme ait olabilir?",
            "yer": "Önce olayın geçtiği yeri gözünde canlandır. Kaynakta hangi yer adı geçiyor?",
            "kronoloji": "İki olayı sıraya koymayı dene. Hangisi ötekinden önce yaşanmış olabilir?",
            "neden_sonuc": "Önce ne değişmiş olabilir, sonra bunun sonucu ne olmuş olabilir?",
            "kisi": "Kişinin yaptığı işi hatırlıyor musun? Bu iş sana kimi hatırlatıyor?",
            "kaynak_yorumu": "Metnin kesin söylediği şey ile senin eklediğin yorum aynı mı?",
            "asiri_genelleme": "Seçenekte ‘her zaman’ ya da ‘tamamı’ gibi çok geniş bir söz var mı?",
            "genel": "Konuyla ilgili aklında kalan ilk bilgiyi söyle. Bu bilgi soru kökündeki sözcükle nasıl bağlanabilir?",
        }
        return prompts[context.error_type]
    if stage == "kanitla_bag_kur":
        relation = context.evidence_by_role.get("relation")
        if relation:
            return f"İki kanıtı birlikte düşün: ‘{_short_evidence(context.evidence, 105)}’ ve ‘{_short_evidence(relation, 105)}’. Aralarındaki bağ ne olabilir?"
        return "Kaynakta bu soruya yardım eden bir cümle var. O cümledeki hangi sözcük seçeneğini destekliyor ya da zayıflatıyor?"
    if stage == "sik_elemesi":
        contrast = context.evidence_by_role.get("contrast")
        if contrast:
            return f"Seçtiğin ifadeyi ‘{_short_evidence(contrast, 150)}’ bilgisiyle karşılaştır. Hangi ayrıntı şıkkı zayıflatıyor?"
        if context.choice_text:
            return "Seçtiğin şıktaki ifadeyi kaynakla karşılaştır. Hangi kelime ya da tarih onu destekliyor veya zayıflatıyor?"
        return "Şıkları sırayla ele. Kaynakla uyuşmayan ilk ifadeyi ve nedenini söyleyebilir misin?"
    if stage == "ogrenci_yaniti":
        return "Bir şık seçip kısa gerekçeni yaz. Hazır olduğunda yanıtını birlikte kontrol edelim."

    # The final explanation is server-side only: it may use the verified answer
    # text after submission, but is never placed in a model prompt.
    evidence = _short_evidence(context.evidence)
    if not answer_label:
        return "Yanıt anahtarı bu soru için kaynakla ayrıca doğrulanmamış. Kaynaktaki kanıtla gerekçeni birlikte karşılaştıralım."
    if submitted_choice == answer_label:
        return f"Evet, seçimin kaynak anahtarıyla uyuşuyor. Kaynakta ‘{evidence}’ deniyor. Bunu kendi cümlenle nasıl açıklarsın?"
    if answer_choice_text:
        return f"Seçtiğin ifadeyle kaynaktaki ‘{evidence}’ bilgisi uyuşmuyor. Bu yüzden “{answer_choice_text}” daha uygun. Aradaki farkı kendi cümlenle anlatır mısın?"
    return f"Seçtiğin ifadeyle kaynaktaki ‘{evidence}’ bilgisi uyuşmuyor. Kaynağa göre hangi seçeneğin daha uygun olduğunu kendi sözünle anlatır mısın?"


def _prompt(stage: str, context: CoachContext, learner_message: str) -> str:
    """Never include answer label, other options, source coordinates, or answer text."""
    return "\n".join((
        "Sen AYT tarih soru koçusun. Öğrenci 11-12. sınıf tarih ve İnkılap Tarihi konularında çalışıyor.",
        "Yalnız Türkçe, sade ve tek soru cümlesi üret.",
        "Doğru cevabı, doğru şıkkı, cevap anahtarını, kesin çözümü veya sayısal cevabı söyleme.",
        "Kaynakta olmayan bilgi ekleme. Kaynak yetersizse bunu soru biçiminde belirt.",
        f"Aşama: {stage}",
        f"Soru: {context.question_text}",
        f"Öğrencinin seçtiği ifade: {context.choice_text or 'yok'}",
        f"MEB kanıtı: {context.evidence}",
        f"Öğrenci mesajı: {learner_message}",
    ))


def _safe_early_question(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact.endswith("?") and compact.count("?") == 1 and not ANSWER_LABEL.search(compact)


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
        if not isinstance(text, str) or not _safe_early_question(text):
            return None, {"llm": int((time.monotonic() - started) * 1000), "first_token": 0}
        elapsed = int((time.monotonic() - started) * 1000)
        first_token = decoded.get("first_token_ms") if isinstance(decoded, dict) else None
        return text.strip()[:600], {"llm": elapsed, "first_token": first_token if isinstance(first_token, int) else 0}
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None, {"llm": int((time.monotonic() - started) * 1000), "first_token": 0}


def coach(context: CoachContext, previous_stage: str | None, learner_message: str,
          submit_answer: bool, submitted_choice: str | None, answer_label: str | None,
          answer_choice_text: str | None = None) -> CoachReply:
    stage = next_stage(previous_stage, submit_answer)
    started = time.monotonic()
    if not context.source_ids:
        text = "Bu soru için öğretmen onaylı MEB kanıtı henüz yok. Soru kökünün senden ne istediğini kendi sözlerinle anlatır mısın?"
        return CoachReply(stage=stage, error_type=context.error_type, student_prompt=text, short_spoken_text=_sentence(text),
                          abstain_reason="approved_source_unavailable",
                          timings_ms={"total": int((time.monotonic() - started) * 1000)})

    # Serving starts deterministic. A locally evaluated adapter can be enabled
    # only explicitly; all non-final adapter output must still be one safe question.
    use_llm = os.getenv("LOCAL_TUTOR_LLM_SERVE", "").casefold() in {"1", "true", "yes"}
    model_text, model_timings = (_llm_hint(stage, context, learner_message)
                                 if use_llm and stage != "gerekceli_aciklama"
                                 else (None, {"llm": 0, "first_token": 0}))
    if model_text and not _safe_early_question(model_text):
        model_text = None
    text = model_text or _fallback(
        stage, context, submitted_choice,
        answer_label if stage == "gerekceli_aciklama" else None,
        answer_choice_text if stage == "gerekceli_aciklama" else None,
    )
    return CoachReply(stage=stage, error_type=context.error_type, student_prompt=text, short_spoken_text=_sentence(text),
                      source_ids=context.source_ids, can_reveal_explanation=stage == "gerekceli_aciklama",
                      timings_ms={**model_timings, "total": int((time.monotonic() - started) * 1000)})
