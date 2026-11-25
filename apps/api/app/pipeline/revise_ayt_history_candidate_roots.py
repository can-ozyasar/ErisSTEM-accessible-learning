"""Create a checksum-bound revision with self-contained student question roots.

The original candidates were intentionally written from source excerpts, but a
template phrase (``Kaynağa göre``) survived in some roots.  Because source
excerpts are not shown during an exam, that phrase is a student-facing content
defect rather than an instruction for the LLM.  This migration never mutates a
reviewed input in place: it writes a new candidate-pack revision and therefore
invalidates prior semantic/content-review artefacts by checksum.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT_REVISIONS = {
    "authoring-004": "1918 İspanyol gribi tedavisi gören hastaların yattığı askerî hastane nerededir?",
    "authoring-006": "Klasik mimaride dikey taş levhalara verilen ad ve bu levhaların mezar taşı dışındaki kullanım alanları aşağıdakilerden hangisinde birlikte verilmiştir?",
    "authoring-007": "Mezopotamya kanunlarında genellikle uygulanan ilke ile bazı durumlarda başvurulan yaptırım aşağıdakilerden hangisinde birlikte verilmiştir?",
    "authoring-009": "Keçe bir çadırın araba üzerine yerleştirilmesiyle elde edilen ev formu, konargöçer Türklere hangi imkânı sağlamıştır?",
    "authoring-010": "2022 yılında dünya genelinde insanların göç yollarına düşmesine yol açan nedenler arasında aşağıdakilerden hangisi yer alır?",
    "authoring-012": "Yüzyıllar boyunca ticaret yollarında yük taşımak amacıyla hangi hayvan kullanılmıştır?",
    "authoring-014": "Savaş sonrasında Bizans ile kurulan diplomatik ilişkiler kapsamında aşağıdakilerden hangisi gerçekleşmiştir?",
    "authoring-017": "TİKA'nın faaliyetleri hakkında aşağıdakilerden hangisi söylenebilir?",
    "authoring-038": "İznik çinileriyle ilgili aşağıdakilerden hangisi söylenebilir?",
    "authoring-039": "Mustafa Kemal'in büyüdüğü Makedonya ile ilgili aşağıdakilerden hangisi doğrudur?",
    "authoring-040": "Atatürk'ün kitap okuma alışkanlığıyla ilgili aşağıdakilerden hangisi söylenebilir?",
    "authoring-069": "1990'larda Türk ekonomisinin büyüme hızını artıran etken aşağıdakilerden hangisidir?",
    "authoring-071": "6 Şubat 2023 depremlerinin merkez üsleri Kahramanmaraş'ın hangi ilçeleridir?",
    "authoring-072": "Kronolojinin tarih çalışmalarındaki işlevi aşağıdakilerden hangisidir?",
    "authoring-124": "Türkiye İktisat Kongresi kararlarının ekonomide millîleşme ve tasarruf bilinci oluşturması, öncelikle hangi Atatürk ilkeleriyle ilişkilendirilmiştir?",
    "authoring-126": "Millî devlet inşa edilirken Osmanlı Devleti'nin hanedan-kul anlayışının yerini alan yeni anlayış aşağıdakilerden hangisidir?",
    "authoring-127": "Kurucu Meclisin temel özelliği aşağıdakilerden hangisidir?",
    "authoring-178": "Pembe Cami ile ilgili aşağıdakilerden hangisi doğrudur?",
    "authoring-180": "Osmanlıcılık fikri neyi esas almaktadır?",
    "authoring-183": "İzmir'in işgali sırasında yaşananlarla ilgili aşağıdakilerden hangisi doğrudur?",
    "authoring-184": "Büyük Millet Meclisinin açılışıyla ilgili aşağıdakilerden hangisi doğrudur?",
    "authoring-185": "Sevr Antlaşması'nın imzalanma süreciyle ilgili aşağıdakilerden hangisi doğrudur?",
    "authoring-195": "Hıfzıssıhha Enstitüsü ile ilgili aşağıdakilerden hangisi söylenebilir?",
    "authoring-197": "Anadolu ve Rumeli Müdâfaa-i Hukuk Grubunun kurulmasında etkili olan temel amaç nedir?",
    "authoring-204": "1946'da yürürlüğe giren İşçi Sigortaları Kurumu Kanunu hangi alanla ilgilidir?",
    "authoring-207": "Cezayir Antlaşması kimler arasında imzalanmıştır?",
}

# Preserve reviewed pronunciation substitutions already present in the source
# pack (for example, "bin dokuz yüz on sekiz") whenever removing the prefix
# is sufficient.  Only roots whose wording changes beyond that prefix need an
# explicit new speech string.
SPOKEN_REVISIONS = {
    "authoring-009": "Keçe bir çadırın araba üzerine yerleştirilmesiyle elde edilen ev formu, konargöçer Türklere hangi imkânı sağlamıştır?",
    "authoring-197": "Anadolu ve Rumeli Müdâfaa-i Hukuk Grubunun kurulmasında etkili olan temel amaç nedir?",
    "authoring-204": "Bin dokuz yüz kırk altıda yürürlüğe giren İşçi Sigortaları Kurumu Kanunu hangi alanla ilgilidir?",
}


def _checksum(questions: list[dict]) -> str:
    raw = [{key: value for key, value in item.items() if key not in {"status", "runtime_enabled"}} for item in questions]
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def revise(candidate: dict) -> dict:
    if candidate.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("AYT Tarih aday paketi gerekli")
    questions = candidate.get("questions")
    if not isinstance(questions, list) or len(questions) != 120:
        raise ValueError("Tam 120 soruluk aday paketi gerekli")
    result = copy.deepcopy(candidate)
    by_id = {item.get("id"): item for item in result["questions"]}
    if set(ROOT_REVISIONS) - set(by_id):
        raise ValueError("Kök revizyonu için beklenen aday bulunamadı")
    for identifier, root in ROOT_REVISIONS.items():
        prior = by_id[identifier].get("question")
        if not isinstance(prior, str) or not prior.startswith("Kaynağa göre"):
            raise ValueError(f"{identifier}: beklenen kaynak-bağımlı soru kökü bulunamadı")
        by_id[identifier]["question"] = root
        prior_spoken = by_id[identifier].get("spoken_question")
        if not isinstance(prior_spoken, str) or not prior_spoken.startswith("Kaynağa göre "):
            raise ValueError(f"{identifier}: beklenen sesletim metni bulunamadı")
        by_id[identifier]["spoken_question"] = SPOKEN_REVISIONS.get(
            identifier, prior_spoken.removeprefix("Kaynağa göre ")
        )
        by_id[identifier]["status"] = "source_crop_validation_required"
        by_id[identifier]["runtime_enabled"] = False
    remaining = [item["id"] for item in result["questions"] if item.get("question", "").startswith("Kaynağa göre")]
    if remaining:
        raise ValueError(f"Kaynak bağımlı kökler kaldı: {', '.join(remaining)}")
    result["candidate_checksum"] = _checksum(result["questions"])
    result["notice"] = (
        "Private candidate pack revision. Student-facing roots were made self-contained; "
        "all prior semantic/content reviews are checksum-invalid and must be regenerated. "
        "Every question remains source/crop validation required and runtime-disabled."
    )
    result["root_revision"] = {
        "reason": "Removed source-dependent student wording ('Kaynağa göre') from 26 original question roots.",
        "revised_question_ids": sorted(ROOT_REVISIONS),
        "prior_candidate_checksum": candidate.get("candidate_checksum"),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = revise(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"revised_count": len(ROOT_REVISIONS), "candidate_checksum": result["candidate_checksum"]}))


if __name__ == "__main__":
    main()
