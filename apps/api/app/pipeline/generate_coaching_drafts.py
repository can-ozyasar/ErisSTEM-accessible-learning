#!/usr/bin/env python3
"""Adım 1: RAG → çeşitli koçluk draft'ı üretim ve kalite kontrol.

Her bekleyen soru için:
  1. history-rag-v1.json'dan BM25 ile en iyi 2 kanıt chunk'ı çek
  2. 6 koçluk aşaması × 3 varyasyon = 18 taslak üret
  3. Kalite kontrolü: erken ifşa, uzunluk, çeşitlilik
  4. İnceleme dosyası yaz: data/private/coaching-draft-queue-v1.json

Öğretmen bu dosyayı UI'da açıp onaylayacak.
Onay sonrası: export_tutor_qlora_pilot.py ile Kaggle'a gönderilecek.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

RAG_INDEX = Path("data/derived/history-rag-v1.json")
REVIEW_QUEUE = Path("data/private/history-tutor-review-v2/queue.json")
OUTPUT = Path("data/private/coaching-draft-queue-v1.json")

CASES = (
    "soruyu_anlama",
    "hatirlayani_ortaya_cikar",
    "kanitla_bag_kur",
    "siki_sina",
    "yanlis_cevabi_duzelt",
    "dogruyu_pekistir",
)
EARLY_ANSWER_CASES = set(CASES[:4])

ANSWER_LABEL = re.compile(
    r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|şık\s*[abcde]\b|\b[abcde]\s*(?:şıkkı|şık|seçeneği)\b|"
    r"ilk\s+seçenek|son\s+seçenek|üstteki\s+seçenek|alttaki\s+seçenek|"
    r"yanıt\s*:\s*[abcde]|doğru\s+seçenek)",
    re.IGNORECASE,
)

STOP = {
    "ve", "veya", "ile", "bir", "bu", "da", "de", "için", "olan", "olarak",
    "tarih", "tarihi", "tarihin", "hangi", "aşağıdaki", "göre", "ise", "en",
    "ne", "mi", "mı", "mu", "mü", "ya", "ki", "bu", "şu", "o", "ama",
}

# ---------------------------------------------------------------------------
# BM25 basit implementasyon (harici kütüphane gerektirmez)
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zçğıöşü0-9]+", text.casefold().translate(
        str.maketrans("Iİ", "ıi")
    ))
    return [t for t in tokens if len(t) > 2 and t not in STOP]


def bm25_score(query_terms: list[str], doc_terms: list[str],
               doc_freq: Counter, n_docs: int,
               k1: float = 1.5, b: float = 0.75, avgdl: float = 50.0) -> float:
    tf_map = Counter(doc_terms)
    dl = len(doc_terms)
    score = 0.0
    for term in set(query_terms):
        if term not in tf_map:
            continue
        tf = tf_map[term]
        df = doc_freq.get(term, 0)
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * dl / avgdl)
        score += idf * numerator / denominator
    return score


def build_bm25_index(chunks: list[dict]) -> tuple[list[list[str]], Counter, float]:
    tokenized = [tokenize(c["text"]) for c in chunks]
    doc_freq: Counter = Counter()
    for terms in tokenized:
        for term in set(terms):
            doc_freq[term] += 1
    avgdl = sum(len(t) for t in tokenized) / max(len(tokenized), 1)
    return tokenized, doc_freq, avgdl


def retrieve_top_k(query: str, chunks: list[dict],
                   tokenized: list[list[str]], doc_freq: Counter,
                   avgdl: float, k: int = 2) -> list[dict]:
    q_terms = tokenize(query)
    n = len(chunks)
    scored = [
        (bm25_score(q_terms, tokenized[i], doc_freq, n, avgdl=avgdl), i)
        for i in range(n)
    ]
    scored.sort(reverse=True)
    return [chunks[i] for _, i in scored[:k] if _ > 0]


# ---------------------------------------------------------------------------
# Koçluk draft üretimi — 3 varyasyon × 6 aşama = 18 taslak
# ---------------------------------------------------------------------------

LEARNER_STATES = {
    "soruyu_anlama": [
        "Sorunun ne istediğini anlamıyorum.",
        "Bu sorudan ne çıkarmam gerektiğini bilmiyorum.",
        "Kök cümleyi anlayamadım.",
    ],
    "hatirlayani_ortaya_cikar": [
        "Konuyu duydum ama ayrıntılar karıştı.",
        "Bu konuyla ilgili bir şey hatırlamıyorum.",
        "Bilgi var ama yerine oturtamıyorum.",
    ],
    "kanitla_bag_kur": [
        "Kaynağı okudum ama soruyla bağlantısını kuramıyorum.",
        "Metni anladım sanırım ama cevaba nasıl götürdüğünü göremiyorum.",
        "Kaynak ile seçenekler arasındaki ilişkiyi bulamıyorum.",
    ],
    "siki_sina": [
        "Bu seçenek doğru gibi geldi ama emin değilim.",
        "İki seçenek arasında kaldım.",
        "Seçeneği işaretledim ama tam olarak neden doğru bilmiyorum.",
    ],
    "yanlis_cevabi_duzelt": [
        "Bu seçeneği işaretledim; neden yanlış olduğunu anlamadım.",
        "Yanlış cevabı seçtim, nereden hata yaptım bilmiyorum.",
        "Bu seçeneğin yanlış olduğunu söyledin, neden?",
    ],
    "dogruyu_pekistir": [
        "Bu seçeneği seçtim ama nedenini tam anlatamıyorum.",
        "Doğru buldum ama kaynakla bağlantısını açıklayamıyorum.",
        "Cevabı biliyorum ama gerekçesi net değil.",
    ],
}

# 3 varyasyon × 6 aşama koçluk soru kalıpları (hata türüne bağlı)
COACHING_TEMPLATES = {
    "soruyu_anlama": [
        # varyasyon 0: odak sözcüğü
        "Soru kökünde senden ne bulmanı isteyen sözcük hangisi?",
        # varyasyon 1: soru tipi
        "Bu soru bir kişi mi, bir tarih mi, yoksa bir neden mi soruyor?",
        # varyasyon 2: daraltma
        "Kökü bir kez daha oku: soru hangi bilgiyi arıyor?",
    ],
    "hatirlayani_ortaya_cikar": [
        "Kaynaktaki {quote} bilgisi sana bu konuyla ilgili neyi hatırlatıyor?",
        "Bu dönemle ilgili ne hatırlıyorsun? {quote} ifadesine bakarak düşün.",
        "{quote} — bu bilgiyle konuyu aklında canlandırabilir misin?",
    ],
    "kanitla_bag_kur": [
        "Kaynaktaki {quote} ile seçenekteki ifade aynı şeyi mi söylüyor?",
        "{quote} — bu bilgi sorudaki hangi kavramı açıklıyor?",
        "Kaynaktan {quote} alıyoruz; bu, seçeneklerden hangisiyle uyuşuyor?",
    ],
    "siki_sina": [
        "Seçenekteki belirleyici sözcüğü kaynakla yan yana düşün; uyuşuyor mu?",
        "Seçtiğin ifadeyi kaynaktan {quote} ile karşılaştır; fark görüyor musun?",
        "Kaynaktaki bilgiye göre bu seçeneği neden uygun ya da uygunsuz buluyorsun?",
    ],
    "yanlis_cevabi_duzelt": [
        "Seçtiğin ifadeyle kaynaktaki {quote} arasında ne fark var?",
        "Kaynak {quote} diyor; senin seçimin bununla uyuşuyor mu?",
        "{quote} — bu bilgi seçimini değiştirmenizi sağlıyor mu?",
    ],
    "dogruyu_pekistir": [
        "Seçtiğin şıkkı kaynakla kontrol et: {quote} bunu nasıl destekliyor?",
        "Neden bu seçenek daha uygun? Kaynaktaki {quote} ile açıkla.",
        "{quote} — bu bilgi seçimini nasıl pekiştiriyor? Kendi cümlenle anlat.",
    ],
}


# Türkçe PDF satır sonu kırıkları: 'erimesiy le' → 'erimesiyle'
_TR_SUFFIXES = re.compile(
    r"([a-zçğıöşü]{3,}) "
    r"(le|la|lı|li|lu|lü|dan|den|tan|ten|da|de|ta|te"
    r"|yı|yi|yu|yü|nın|nin|nun|nün|ın|in|un|ün"
    r"|daki|deki|taki|teki|ya|ye|yı|yi|e|a)\b"
)


def fix_word_breaks(text: str) -> str:
    """PDF word-break artifact'larını onar."""
    return _TR_SUFFIXES.sub(r"\1\2", text)


def short_quote(text: str, limit: int = 100) -> str:
    text = fix_word_breaks(re.sub(r"\s+", " ", text).strip())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def infer_error_type(question_text: str) -> str:
    text = question_text.lower()
    if re.search(r"\b(?:yıl|tarih|dönem|çağ|yüzyıl|önce|sonra|kaçıncı)\b", text):
        return "tarih"
    if re.search(r"\b(?:nerede|hangi\s+şehir|bölge|ülke|coğraf)\b", text):
        return "yer"
    if re.search(r"\b(?:neden|sonuç|etki|sebep|dolayı)\b", text):
        return "neden_sonuc"
    if re.search(r"\b(?:önce|sonra|sıra|kronoloj)\b", text):
        return "kronoloji"
    if re.search(r"\b(?:kim|kimin|hangi\s+kişi|lider|hükümdar)\b", text):
        return "kisi"
    if re.search(r"\b(?:kaynak|belge|kanıt|yorum|metin)\b", text):
        return "kaynak_yorumu"
    if re.search(r"\b(?:her\s+zaman|tamamı|yalnızca|kesinlikle|hiç)\b", text):
        return "asiri_genelleme"
    return "genel"


def make_draft(case: str, variant: int, question_text: str,
               chunks: list[dict], error_type: str) -> dict:
    """Tek bir koçluk aşaması için 1 taslak üret."""
    templates = COACHING_TEMPLATES[case]
    template = templates[variant % len(templates)]
    learner_states = LEARNER_STATES[case]
    learner_state = learner_states[variant % len(learner_states)]

    # Kanıt alıntısı
    quote = short_quote(chunks[0]["text"]) if chunks else ""
    response = template.format(quote=quote) if "{quote}" in template else template

    source_ids = [c["id"] for c in chunks[:2]]
    evidence_quotes = [short_quote(c["text"], 500) for c in chunks[:2]]

    return {
        "case": case,
        "variant": variant,
        "error_type": error_type,
        "learner_state": learner_state,
        "guide_response": response,
        "source_ids": source_ids,
        "evidence_quotes": evidence_quotes,
        "grounding_mode": "source_evidence" if source_ids else "question_derived_recall",
        "early_answer_disclosed": False,
        "grounded_in_source": bool(source_ids),
        "simple_turkish": True,
        "age_appropriate": True,
        "_auto_quality": _quality_check(response, case, source_ids),
    }


def _quality_check(response: str, case: str, source_ids: list[str]) -> dict:
    """Otomatik kalite kontrolleri."""
    is_early = case in EARLY_ANSWER_CASES
    has_disclosure = bool(ANSWER_LABEL.search(response))
    ends_question = response.strip().endswith("?")
    too_long = len(response) > 300
    too_short = len(response) < 15
    no_source_when_needed = (
        case not in {"soruyu_anlama", "hatirlayani_ortaya_cikar"}
        and not source_ids
    )
    passes = (
        not (is_early and has_disclosure)
        and ends_question
        and not too_long
        and not too_short
        and not no_source_when_needed
    )
    return {
        "passes": passes,
        "early_disclosure_risk": is_early and has_disclosure,
        "ends_with_question": ends_question,
        "length_ok": not too_long and not too_short,
        "source_bound": not no_source_when_needed,
        "char_length": len(response),
    }


# ---------------------------------------------------------------------------
# Çeşitlilik skoru: aynı soru için 6 × 3 taslak ne kadar farklı?
# ---------------------------------------------------------------------------

def diversity_score(drafts: list[dict]) -> float:
    responses = [d["guide_response"] for d in drafts]
    total_pairs = len(responses) * (len(responses) - 1) / 2
    if total_pairs == 0:
        return 1.0
    shared = 0
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            t1 = set(tokenize(responses[i]))
            t2 = set(tokenize(responses[j]))
            overlap = len(t1 & t2) / max(len(t1 | t2), 1)
            if overlap > 0.6:  # %60 kelime örtüşmesi → şablon tekrarı
                shared += 1
    return round(1.0 - shared / total_pairs, 3)


# ---------------------------------------------------------------------------
# Ana akış
# ---------------------------------------------------------------------------

def main() -> None:
    print("RAG index yükleniyor...")
    rag = json.loads(RAG_INDEX.read_text(encoding="utf-8"))
    chunks: list[dict] = rag.get("chunks", [])
    print(f"  {len(chunks)} chunk yüklendi")

    tokenized, doc_freq, avgdl = build_bm25_index(chunks)

    print("Review kuyruğu yükleniyor...")
    queue = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
    pending = [c for c in queue.get("cases", []) if c.get("review_status") == "pending"]
    print(f"  {len(pending)} bekleyen soru bulundu")

    output_cases = []
    stats = {"total": len(pending), "passed_auto_check": 0, "failed_auto_check": 0,
             "total_drafts": 0, "avg_diversity": 0.0}

    for case_data in pending:
        qid = case_data["question_id"]
        question_obj = case_data.get("question", {})

        # Soru metnini birleştir (kök + şıklar — ama şık harflerini dışarıda bırak)
        parts = question_obj.get("parts", [])
        stem_parts = [p["text"] for p in parts if p.get("kind") == "stem" and p.get("text")]
        question_text = " ".join(stem_parts) if stem_parts else qid

        error_type = infer_error_type(question_text)
        topic = case_data.get("topic", "")
        query = f"{topic} {question_text}"

        # RAG: top-2 kanıt
        top_chunks = retrieve_top_k(query, chunks, tokenized, doc_freq, avgdl, k=2)

        # 6 aşama × 3 varyasyon = 18 taslak
        all_drafts = []
        for case_name in CASES:
            for variant in range(3):
                # hatirlayani ve kanitla_bag_kur için chunk gerekli
                relevant_chunks = top_chunks if case_name not in {"soruyu_anlama"} else []
                draft = make_draft(case_name, variant, question_text, relevant_chunks, error_type)
                draft["question_id"] = qid
                all_drafts.append(draft)

        passed = [d for d in all_drafts if d["_auto_quality"]["passes"]]
        div_score = diversity_score(all_drafts)

        stats["total_drafts"] += len(all_drafts)
        if passed:
            stats["passed_auto_check"] += 1
        else:
            stats["failed_auto_check"] += 1

        output_cases.append({
            "question_id": qid,
            "question_text_preview": question_text[:200],
            "topic": topic,
            "error_type": error_type,
            "top_chunk_ids": [c["id"] for c in top_chunks],
            "top_chunk_texts": [c["text"][:300] for c in top_chunks],
            "diversity_score": div_score,
            "auto_check_passed": bool(passed),
            "passed_draft_count": len(passed),
            "total_draft_count": len(all_drafts),
            "drafts": all_drafts,
            "review_status": "draft_ready",
            "notice": (
                "Otomatik kalite kontrolünden geçen taslaklar. "
                "Öğretmen incelemesi olmadan Kaggle verisi yapılamaz."
            ),
        })

        status = "✓" if passed else "✗"
        print(f"  [{status}] {qid}: {len(passed)}/{len(all_drafts)} taslak geçti, çeşitlilik={div_score}")

    stats["avg_diversity"] = round(
        sum(c["diversity_score"] for c in output_cases) / max(len(output_cases), 1), 3
    )

    result = {
        "schema": "coaching-draft-queue-v1",
        "source_rag_index": str(RAG_INDEX),
        "source_review_queue": str(REVIEW_QUEUE),
        "generation_note": (
            "Otomatik üretim. Öğretmen onayı olmadan eğitim verisi yapılamaz. "
            "approved=True ve reviewed_by alanları öğretmen incelemesinde doldurulacak."
        ),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "stats": stats,
        "cases": output_cases,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {len(output_cases)} soru, {stats['total_drafts']} taslak → {OUTPUT}")
    print(f"  Oto-kontrol geçen: {stats['passed_auto_check']}/{stats['total']}")
    print(f"  Ortalama çeşitlilik: {stats['avg_diversity']}")
    print("\nSonraki adım:")
    print("  Öğretmen drafts'ları inceleyip onaylayacak.")
    print("  Onaylanan satırlar → export_tutor_qlora_pilot.py → Kaggle")


if __name__ == "__main__":
    main()
