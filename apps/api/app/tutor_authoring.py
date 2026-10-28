"""Teacher-style draft and independent rubric agent for reviewed coach cases."""
from __future__ import annotations

import re

from .tutor_coach import ANSWER_LABEL
from .tutor_dataset import CASES, ERROR_TYPES

YEAR = re.compile(
    r"\b(?:MÖ\s*\d{1,4}|MÖ\s*[IVXLCDM]+\.?\s*yüzyıl|\d{3,4}(?:\s*yılında)?|[IVXLCDM]+\.?\s*yüzyıl)\b"
)
PLACE = re.compile(r"\b(?:Anadolu|Mezopotamya|Mısır|Yunan|Roma|Asya|Avrupa|Akdeniz|Karadeniz)\b", re.IGNORECASE)
CAUSE = re.compile(r"\b(?:neden|sonuç|etki|sebep|dolayı|sağlad|değiştir)\w*", re.IGNORECASE)


def infer_error_type(question_text: str, selected_choice: str | None = None) -> str:
    text = f"{question_text} {selected_choice or ''}"
    if YEAR.search(text): return "tarih"
    if PLACE.search(text): return "yer"
    if CAUSE.search(text): return "neden_sonuc"
    if re.search(r"önce|sonra|sıra|kronolojik", text, re.IGNORECASE): return "kronoloji"
    if re.search(r"kaynak|belge|kanıt|yorum", text, re.IGNORECASE): return "kaynak_yorumu"
    if re.search(r"her zaman|tamamı|yalnızca|kesinlikle", text, re.IGNORECASE): return "asiri_genelleme"
    return "genel"


def learner_state(case: str) -> str:
    return {"soruyu_anlama": "Sorunun ne istediğini ayırt edemiyorum.",
            "hatirlayani_ortaya_cikar": "Konuyu duydum ama ayrıntılar birbirine karıştı.",
            "kanitla_bag_kur": "Kaynağı okudum ama bunun seçeneğe nasıl yardım ettiğini bilmiyorum.",
            "siki_sina": "Bu seçenek doğru gibi geldi ama emin değilim.",
            "yanlis_cevabi_duzelt": "Bu seçeneği işaretledim; neden yanlış olduğunu anlamadım.",
            "dogruyu_pekistir": "Bu seçeneği seçtim ama nedenini tam anlatamıyorum."}[case]


def _prompts(error_type: str, quote: str) -> tuple[str, str]:
    short = quote[:180].rsplit(" ", 1)[0] + "." if len(quote) > 180 else quote
    values = {
        "kisi": ("Kök ya da kaynakta bu kişiyle ilgili hangi görev veya olay geçiyor?", "Kaynaktaki ‘{q}’ sözü sana kimi hatırlatıyor?"),
        "tarih": ("Tarihin yanındaki olayı düşün. Bu tarih sence o olayla uyuşuyor mu?", "Kaynaktaki ‘{q}’ bilgisi tarihle nasıl yan yana geliyor?"),
        "yer": ("Kaynaktaki yer adı ile seçenekteki yer adı aynı mı?", "Kaynaktaki ‘{q}’ sözü olayın nerede geçtiğini nasıl gösteriyor?"),
        "kronoloji": ("İki olayı sıraya koymayı dene. Hangisi ötekinden önce yaşanmış olmalı?", "Kaynaktaki ‘{q}’ bilgisini olayların sırasına nereye yerleştirirsin?"),
        "neden_sonuc": ("Önce ne değişmiş olabilir, sonra bunun sonucu ne olmuş olabilir?", "Kaynaktaki ‘{q}’ sözü neden ile sonucu nasıl bağlıyor?"),
        "kaynak_yorumu": ("Metnin kesin söylediği şey ile senin eklediğin yorum aynı mı?", "Kaynaktaki ‘{q}’ sözü tam olarak neyi kanıtlıyor?"),
        "asiri_genelleme": ("Seçenekte ‘her zaman’ ya da ‘tamamı’ gibi çok geniş bir söz var mı?", "Kaynaktaki ‘{q}’ sözü bu kadar geniş bir yargıyı gerçekten destekliyor mu?"),
        "genel": ("Soru kökündeki hangi söz, aradığın bilgiyi en çok daraltıyor?", "Kaynaktaki ‘{q}’ sözü ile seçenekteki ifade aynı şeyi mi anlatıyor?"),
    }
    recall, evidence = values[error_type]
    return recall, evidence.format(q=short)


def create_drafts(question_text: str, evidence: list[dict], selected_choice: str | None = None) -> list[dict]:
    if not evidence:
        raise ValueError("Taslak üretimi için öğretmence onaylı MEB kanıtı gerekli")
    error_type = infer_error_type(question_text, selected_choice)
    source_ids = [item["id"] for item in evidence[:2]]
    quotes = [item["text"][:520].rsplit(" ", 1)[0] + "." if len(item["text"]) > 520 else item["text"] for item in evidence[:2]]
    correction_quote = quotes[0][:150].rsplit(" ", 1)[0] + "." if len(quotes[0]) > 150 else quotes[0]
    recall, evidence_prompt = _prompts(error_type, quotes[0])
    texts = {
        "soruyu_anlama": "Soru senden neyi bulmanı istiyor: bir kişiyi mi, tarihi mi, yoksa olayların sırasını mı? Kökün hangi sözcüğü sana bunu düşündürüyor?",
        "hatirlayani_ortaya_cikar": recall, "kanitla_bag_kur": evidence_prompt,
        "siki_sina": "Seçenekteki belirleyici sözü kaynakla yan yana düşün. İkisi aynı şeyi mi söylüyor, yoksa küçük bir fark var mı?",
        "yanlis_cevabi_duzelt": f"Seçtiğin ifadeyle kaynakta geçen ‘{correction_quote}’ arasında ne fark var? Bu fark seçimini değiştirir mi?",
        "dogruyu_pekistir": "Seçtiğin şıkkı kaynakla kontrol et. Kaynakta bunu destekleyen hangi bilgi var? Önce kendi cümlenle söyle."}
    return [{"case": case, "error_type": error_type, "source_ids": source_ids, "evidence_quotes": quotes,
             "learner_state": learner_state(case), "coaching_goal": "Öğrencinin bilgiyi kendisinin geri çağırmasını sağlamak.",
             "guide_response": texts[case], "author": "teacher_draft_agent"} for case in CASES]


def review_draft(draft: dict) -> dict:
    text = draft.get("guide_response", "")
    early = draft.get("case") in CASES[:4] and bool(ANSWER_LABEL.search(text))
    flags = []
    if early: flags.append("erken_cevap_ifşası")
    if "hangi kavram" in text.casefold(): flags.append("yapay_ogretmen_dili")
    if len(text) > 420: flags.append("fazla_uzun")
    if "?" not in text: flags.append("geri_cagirma_sorusu_yok")
    if draft.get("error_type") not in ERROR_TYPES: flags.append("hata_turu_gecersiz")
    if not draft.get("source_ids") or not draft.get("evidence_quotes"): flags.append("kaynak_yok")
    evidence = " ".join(draft.get("evidence_quotes", []))
    response_years = set(YEAR.findall(text)); evidence_years = set(YEAR.findall(evidence))
    if response_years - evidence_years: flags.append("kaynak_dışı_tarih")
    return {"agent": "independent_rubric_agent", "passed": not flags, "flags": flags,
            "source_grounded": bool(draft.get("source_ids")) and not (response_years - evidence_years), "natural_turkish": "hangi kavram" not in text.casefold(),
            "age_appropriate": len(text) <= 420, "early_answer_disclosed": early}
