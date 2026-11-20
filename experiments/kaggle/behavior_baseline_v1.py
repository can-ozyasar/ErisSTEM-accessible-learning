"""Davranış baseline ölçümü: Qwen3-14B'nin vanilla koçluk yanıtlarını
6 koçluk durumu × N soru üzerinde değerlendirir.

Bu script Kaggle'da GPU ile çalışır. Çıktı:
  /kaggle/working/behavior_baseline_v1.json

Ölçülen metrikler:
  - early_disclosure_rate  : erken cevap ifşası (sıfır olmalı)
  - source_grounding_rate  : yanıt kanıta dayalı mı?
  - abstain_rate           : kanıt yokken susabiliyor mu?
  - question_only_rate     : yanıt soru cümlesiyle bitiyor mu?
  - avg_response_length    : token sayısı p50/p95
  - turkish_rate           : yanıt Türkçe mi?
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

OUT = Path("/kaggle/working/behavior_baseline_v1.json")
MODEL = "Qwen/Qwen3-14B"
REVISION = os.environ.get("TUTOR_MODEL_REVISION", "40c069824f4251a91eefaf281ebe4c544efd3e18")

# Koçluk durumları (6 aşama)
CASES = (
    "soruyu_anlama",
    "hatirlayani_ortaya_cikar",
    "kanitla_bag_kur",
    "siki_sina",
    "yanlis_cevabi_duzelt",
    "dogruyu_pekistir",
)
EARLY_ANSWER_CASES = set(CASES[:4])  # Bu 4'te cevap ifşası yasak

# Erken ifşa tespiti — tutor_coach.py'daki ANSWER_LABEL ile aynı mantık
ANSWER_LABEL = re.compile(
    r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|şık\s*[abcde]\b|\b[abcde]\s*(?:şıkkı|şık|seçeneği)\b|"
    r"ilk\s+seçenek|son\s+seçenek|üstteki\s+seçenek|alttaki\s+seçenek|"
    r"cevap\s+[abcde]\b|doğru\s+seçenek\s+[abcde]|"
    r"yanıt\s*:|\bsonuç\s*:\s*[abcde]\b)",
    re.IGNORECASE,
)

# Açıklama kalıpları — model yanıt veriyor yerine düşündürmeli
EXPLANATION_PATTERN = re.compile(
    r"(?:bu\s+nedenle|dolayısıyla|sonuç\s+olarak|açıklamak\s+gerekirse|"
    r"çünkü\s+kanıt|kanıta\s+göre\s+doğru|doğru\s+yanıt|"
    r"kanıt\s+bunu\s+destekl|bu\s+bilgi\s+doğruluyor)",
    re.IGNORECASE,
)

# Öğretici soru kalıbı (istenen davranış)
QUESTION_ENDING = re.compile(r"\?\s*$")

# 6 aşama × 4 soru tipi = 24 sentetik test vakası
# Gerçek sorular private; bunlar davranış ölçümü için sentetik
EVAL_CASES = [
    # --- soruyu_anlama ---
    {
        "case": "soruyu_anlama", "error_type": "tarih",
        "question": "Osmanlı Devleti'nin çöküş sürecinde hangi antlaşma imzalanmıştır?",
        "learner_state": "Sorunun ne istediğini anlamıyorum.",
        "evidence": "Mondros Ateşkesi, Osmanlı Devleti ile İtilaf Devletleri arasında 30 Ekim 1918'de imzalanmıştır.",
        "expected_behavior": "question_only",
    },
    {
        "case": "soruyu_anlama", "error_type": "neden_sonuc",
        "question": "Sanayi Devrimi'nin toplumsal yapıya etkisi nedir?",
        "learner_state": "Bunun bir nedeni var mı bilmiyorum.",
        "evidence": "Sanayi Devrimi, tarım toplumundan sanayi toplumuna geçişi hızlandırarak şehirleşmeyi artırdı.",
        "expected_behavior": "question_only",
    },
    # --- hatirlayani_ortaya_cikar ---
    {
        "case": "hatirlayani_ortaya_cikar", "error_type": "kisi",
        "question": "Mustafa Kemal'in hangi görevi üstlendiği sorulmaktadır?",
        "learner_state": "Bu kişiyi hatırlamıyorum.",
        "evidence": "Mustafa Kemal, Kurtuluş Savaşı'nda Türk ordusuna komuta etmiştir.",
        "expected_behavior": "question_only",
    },
    {
        "case": "hatirlayani_ortaya_cikar", "error_type": "kronoloji",
        "question": "Fransız Devrimi ile Amerikan Bağımsızlık Savaşı hangi sırayla gerçekleşmiştir?",
        "learner_state": "Hangisi önce oldu bilmiyorum.",
        "evidence": "Amerikan Bağımsızlık Savaşı 1775-1783, Fransız Devrimi ise 1789'da başlamıştır.",
        "expected_behavior": "question_only",
    },
    # --- kanitla_bag_kur ---
    {
        "case": "kanitla_bag_kur", "error_type": "kaynak_yorumu",
        "question": "Verilen kaynağa göre loncaların temel işlevi nedir?",
        "learner_state": "Kaynağı okudum ama bağlantıyı kuramıyorum.",
        "evidence": "Loncalar, orta çağda zanaatkârların mesleki standartlarını koruyan ve ticaret kurallarını belirleyen örgütlenmelerdir.",
        "expected_behavior": "question_only",
    },
    {
        "case": "kanitla_bag_kur", "error_type": "genel",
        "question": "İpek Yolu'nun ticaret üzerindeki etkisi nedir?",
        "learner_state": "Kaynakta bir şey yazıyor ama soruyla nasıl ilgili bilmiyorum.",
        "evidence": "İpek Yolu, Çin'den Avrupa'ya uzanan ve farklı medeniyetlerin ticaret yaptığı önemli bir güzergahtı.",
        "expected_behavior": "question_only",
    },
    # --- siki_sina ---
    {
        "case": "siki_sina", "error_type": "asiri_genelleme",
        "question": "Aşağıdakilerden hangisi tarihsel bir kanıtın özelliğidir?",
        "learner_state": "Bu seçenek doğru gibi geldi ama emin değilim.",
        "evidence": "Birincil kaynaklar, olayın yaşandığı dönemde üretilmiş belgeler veya anlatımlardır.",
        "expected_behavior": "question_only",
    },
    # --- yanlis_cevabi_duzelt ---
    {
        "case": "yanlis_cevabi_duzelt", "error_type": "tarih",
        "question": "Türkiye Cumhuriyeti hangi yılda kurulmuştur?",
        "learner_state": "1920 yılında kuruldu sanırım.",
        "evidence": "Türkiye Cumhuriyeti, 29 Ekim 1923'te ilan edilmiştir.",
        "expected_behavior": "source_correction_question",
    },
    {
        "case": "yanlis_cevabi_duzelt", "error_type": "yer",
        "question": "Çanakkale Savaşı hangi cephede gerçekleşmiştir?",
        "learner_state": "Doğu cephesinde oldu diye düşünüyorum.",
        "evidence": "Çanakkale Savaşı, Birinci Dünya Savaşı sırasında Çanakkale Boğazı'nda gerçekleşmiştir.",
        "expected_behavior": "source_correction_question",
    },
    # --- dogruyu_pekistir ---
    {
        "case": "dogruyu_pekistir", "error_type": "genel",
        "question": "Rönesans döneminde hangi alan gelişme göstermiştir?",
        "learner_state": "Sanat ve edebiyat gelişti diye düşünüyorum.",
        "evidence": "Rönesans, Avrupa'da 14-17. yüzyıllar arasında sanat, bilim ve edebiyat alanlarında büyük bir kültürel yeniden doğuşu temsil eder.",
        "expected_behavior": "confirm_and_deepen",
    },
    # --- abstain (kanıt yok) ---
    {
        "case": "kanitla_bag_kur", "error_type": "genel",
        "question": "Hangi olay nedeniyle çatışma başlamıştır?",
        "learner_state": "Kaynakta bunu bulamadım.",
        "evidence": "",  # Boş kanıt → model susmalı
        "expected_behavior": "abstain",
    },
]

report: dict = {
    "schema": "tutor-behavior-baseline-v1",
    "model": MODEL,
    "revision": REVISION,
    "status": "started",
    "python": platform.python_version(),
    "results": [],
    "metrics": {},
}


def save() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_prompt(case: dict) -> str:
    """Mevcut tutor_coach.py _prompt() ile birebir aynı format."""
    lines = [
        "Sen AYT tarih soru koçusun. Öğrenci 11-12. sınıf tarih ve İnkılap Tarihi konularında çalışıyor.",
        "Yalnız Türkçe, sade ve tek soru cümlesi üret.",
        "Doğru cevabı, doğru şıkkı, cevap anahtarını, kesin çözümü veya sayısal cevabı söyleme.",
        "Kaynakta olmayan bilgi ekleme. Kaynak yetersizse bunu soru biçiminde belirt.",
        f"Aşama: {case['case']}",
        f"Soru: {case['question']}",
        f"Öğrenci: {case['learner_state']}",
    ]
    if case["evidence"]:
        lines.append(f"MEB kanıtı: {case['evidence']}")
    else:
        lines.append("MEB kanıtı: (Bu soru için henüz onaylı kanıt yok.)")
    lines.append("Koç:")
    return "\n".join(lines)


def analyze_response(reply: str, case: dict) -> dict:
    """Yanıtı davranış metriklerine göre değerlendir."""
    is_early_answer_case = case["case"] in EARLY_ANSWER_CASES
    has_early_disclosure = bool(ANSWER_LABEL.search(reply))
    has_explanation = bool(EXPLANATION_PATTERN.search(reply))
    ends_with_question = bool(QUESTION_ENDING.search(reply.strip()))
    no_evidence = not case["evidence"].strip()
    # Yanıt Türkçe mi? (basit heuristik: Türkçe stop words)
    turkish_words = re.findall(r"\b(?:ve|bir|bu|için|olan|ile|da|de|mi|mı|ya|ya da|ama|çünkü|nasıl|hangi|ne|neden)\b", reply, re.IGNORECASE)
    is_turkish = len(turkish_words) >= 2

    return {
        "case": case["case"],
        "error_type": case["error_type"],
        "expected_behavior": case["expected_behavior"],
        "reply_length": len(reply),
        "reply_tokens_approx": len(reply.split()),
        "early_disclosure": has_early_disclosure and is_early_answer_case,
        "explanation_instead_of_question": has_explanation,
        "ends_with_question": ends_with_question,
        "is_turkish": is_turkish,
        "abstained_correctly": no_evidence and ("henüz" in reply.lower() or "bilgi yok" in reply.lower() or "kanıt" in reply.lower()),
        "reply_preview": reply[:200],
    }


def compute_metrics(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}
    early_cases = [r for r in results if r["case"] in EARLY_ANSWER_CASES]
    abstain_cases = [r for r in results if r["expected_behavior"] == "abstain"]
    lengths = sorted(r["reply_tokens_approx"] for r in results)
    p50 = lengths[n // 2]
    p95 = lengths[int(n * 0.95)] if n > 1 else lengths[-1]
    return {
        "total_cases": n,
        "early_disclosure_rate": {
            "value": round(sum(1 for r in early_cases if r["early_disclosure"]) / max(len(early_cases), 1), 3),
            "numerator": sum(1 for r in early_cases if r["early_disclosure"]),
            "denominator": len(early_cases),
            "note": "Sıfır olmalı — erken cevap ifşası yasak",
        },
        "explanation_instead_of_question_rate": {
            "value": round(sum(1 for r in results if r["explanation_instead_of_question"]) / n, 3),
            "note": "Düşük olmalı — model soru sormalı, açıklamamalı",
        },
        "ends_with_question_rate": {
            "value": round(sum(1 for r in results if r["ends_with_question"]) / n, 3),
            "note": "Yüksek olmalı — Sokratik soru yöntemi",
        },
        "turkish_rate": {
            "value": round(sum(1 for r in results if r["is_turkish"]) / n, 3),
            "note": "1.0 olmalı",
        },
        "abstain_when_no_evidence_rate": {
            "value": round(sum(1 for r in abstain_cases if r["abstained_correctly"]) / max(len(abstain_cases), 1), 3),
            "denominator": len(abstain_cases),
            "note": "Yüksek olmalı — kanıt yokken susmalı",
        },
        "response_length_tokens": {
            "p50": p50,
            "p95": p95,
            "note": "Hedef p50≤40, p95≤80 token (kısa Sokratik soru)",
        },
    }


def main() -> None:
    save()

    if os.getenv("TUTOR_BASELINE_SKIP_INSTALL") != "1":
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "transformers>=4.51,<5", "accelerate>=1.4",
             "bitsandbytes>=0.45", "peft>=0.14"],
            check=True,
        )

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    report["gpus"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    if not torch.cuda.is_available():
        report["status"] = "no_gpu"
        save()
        sys.exit(1)

    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    quant = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16,
    )
    torch.cuda.reset_peak_memory_stats()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, quantization_config=quant,
        device_map={"": 0}, dtype=torch.float16,
    )
    model.eval()
    report["load_peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    save()

    results = []
    for i, case in enumerate(EVAL_CASES):
        prompt_text = build_prompt(case)
        messages = [{"role": "user", "content": prompt_text}]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            enable_thinking=False, return_dict=True, return_tensors="pt",
        ).to("cuda:0")
        torch.cuda.synchronize()
        t0 = time.monotonic()
        with torch.inference_mode():
            output = model.generate(
                **inputs, max_new_tokens=128, do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        torch.cuda.synchronize()
        elapsed = round(time.monotonic() - t0, 3)
        generated = output[0, inputs["input_ids"].shape[-1]:]
        reply = tokenizer.decode(generated, skip_special_tokens=True).strip()
        analysis = analyze_response(reply, case)
        analysis["prompt"] = prompt_text
        analysis["reply"] = reply
        analysis["seconds"] = elapsed
        analysis["input_tokens"] = int(inputs["input_ids"].shape[-1])
        analysis["output_tokens"] = int(generated.numel())
        results.append(analysis)
        report["results"] = results
        report["metrics"] = compute_metrics(results)
        save()
        print(f"[{i+1}/{len(EVAL_CASES)}] {case['case']} → early={analysis['early_disclosure']} ends_q={analysis['ends_with_question']} ({elapsed}s)")

    report["metrics"] = compute_metrics(results)
    report["status"] = "completed"
    save()
    print("\n=== BASELINE METRİKLER ===")
    for key, val in report["metrics"].items():
        if isinstance(val, dict):
            print(f"  {key}: {val.get('value', val)}")
    print(f"\nTam rapor: {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)[:2000]
        report["error_type"] = type(exc).__name__
        save()
        traceback.print_exc()
        raise
