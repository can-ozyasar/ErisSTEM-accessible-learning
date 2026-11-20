"""Generate question-specific, answer-isolated six-turn coaching drafts."""
from __future__ import annotations
import argparse, json, os, re
from pathlib import Path
from .deepseek_evidence_judge import _call
from ..tutor_dataset import CASES
from ..tutor_authoring import infer_error_type, learner_state

SCHEMA = "deepseek-contextual-source-bound-coaching-drafts-v1"

def _request(rows, model):
    groups = [{"question_id": q["id"], "question": q["question"], "source_excerpt": q["source_evidence"]["quote"],
               "learner_states": [{"case": c, "student": learner_state(c)} for c in CASES]} for q in rows]
    prompt = ("Sen görme engelli lise öğrencileri için sakin, doğal Türkçe konuşan AYT Tarih öğretmenisin. "
              "Her soru için altı öğrenci durumuna ayrı bir koç yanıtı yaz. Yalnız source_excerpt ve soru kökünü kullan; "
              "doğru cevabı, şıkkı, çözümü veya kaynak dışı tarih bilgisini asla söyleme; erken turlarda 'şık' ve 'seçenek' "
              "sözcüklerini de kullanma. Her yanıt öğrencinin son sözünü kabul edip TEK kısa soru sorsun; ezberci veya 'hangi kavram' "
              "gibi yapay dil kullanma. Kaynak cümlesini doğrudan cevaba dönüştürme; öğrencinin kendi bağlantısını kurmasını iste. "
              "Kaynakta geçen kişi, yer, kurum, ilke, sayı, olay veya sonucu ipucu olarak tekrar etme; özellikle 'iki', 'doğru', "
              "'yanlış işaretleme', 'hayatından örnek' ve öğrencinin görmediği bir görsele gönderme yapma. Soru kökünde istenen "
              "ilişkiden sapma. Altı tur birbirinden farklı bilişsel küçük adımlar taşısın: sorunun isteğini ayırma, alıntıda "
              "destek aranacak yeri bulma, ilişki kurma, tutarlılık denetimi, öğrenci gerekçesi ve kendi denetimi. Kesik ya da "
              "tam olmayan kaynak ifadesini aynen tekrar etme. JSON dışında yanıt verme: "
              '{"groups":[{"question_id":"...","turns":[{"case":"...","strategy":"...","response":"...?"}]}]}.\n'
              + json.dumps({"groups": groups}, ensure_ascii=False, separators=(",", ":")))
    return {"model":model,"temperature":0.2,"max_tokens":2200,"response_format":{"type":"json_object"},"messages":[{"role":"user","content":prompt}]}

def draft(pack, api_key, *, offset=0, limit=2, question_ids: set[str] | None = None, model="deepseek-chat", timeout_s=45, request_fn=_call):
    if pack.get("schema") != "ayt-history-question-bank-training-candidate-v1" or not api_key or not 1 <= limit <= 2: raise ValueError("Geçerli paket, API anahtarı ve 1-2 grup gerekli")
    if question_ids is not None:
        rows = [row for row in pack["questions"] if row.get("id") in question_ids]
        if len(rows) != len(question_ids):
            raise ValueError("İstenen soru kimliği pakette yok")
    else:
        rows=pack["questions"][offset:offset+limit]
    if not rows: raise ValueError("Taslak grubu yok")
    try: groups=json.loads(request_fn(_request(rows,model),api_key,timeout_s)["choices"][0]["message"]["content"])["groups"]
    except (KeyError,IndexError,TypeError,json.JSONDecodeError) as e: raise ValueError("Koç taslağı geçerli JSON dönmedi") from e
    expected={q["id"] for q in rows}
    if not isinstance(groups,list) or {g.get("question_id") for g in groups if isinstance(g,dict)} != expected: raise ValueError("Her soru için bir koçluk grubu gerekli")
    by={q["id"]:q for q in rows}; records=[]
    for group in groups:
        turns=group.get("turns",[])
        if len(turns)!=6 or [x.get("case") for x in turns] != list(CASES): raise ValueError("Altı koçluk durumu eksik")
        q=by[group["question_id"]]; quote=q["source_evidence"]["quote"][:520]; sid=f"{q['source_evidence']['source_checksum']}:{q['source_evidence']['atom_id']}"
        cleaned=[]
        for turn in turns:
            response=turn.get("response")
            if (not isinstance(response,str) or response.count("?") != 1 or not response.strip().endswith("?")
                    or re.search(r"\b(?:şık|seçenek)[a-zçğıöşü]*\b", response, re.I)):
                raise ValueError("Her koç yanıtı tek soru olmalı ve erken şık yönlendirmesi içermemeli")
            cleaned.append({"case":turn["case"],"learner_state":learner_state(turn["case"]),"strategy":str(turn.get("strategy","contextual_scaffold"))[:80],"guide_response":response.strip(),"source_ids":[sid],"evidence_quotes":[quote],"early_answer_disclosed":False,"runtime_enabled":False})
        records.append({"question_id":q["id"],"question":q["question"],"error_type":infer_error_type(q["question"]),"turns":cleaned,"runtime_enabled":False})
    return {"schema":SCHEMA,"corpus_checksum":pack["corpus_checksum"],"question_bank_checksum":pack["frozen_checksum"],"offset":offset,"records":records,"runtime_enabled":False,"qlora_enabled":False}

def main():
 p=argparse.ArgumentParser(); p.add_argument("--pack",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--offset",type=int,default=0); p.add_argument("--limit",type=int,default=2); p.add_argument("--question-id",action="append",default=[]); p.add_argument("--api-key-env",default="DEEPSEEK_API_KEY"); p.add_argument("--allow-external-private-evaluation",action="store_true"); a=p.parse_args()
 if not a.allow_external_private_evaluation: raise SystemExit("Dış servis çağrısı için --allow-external-private-evaluation zorunlu")
 key=os.getenv(a.api_key_env)
 if not key: raise SystemExit(f"{a.api_key_env} ortam değişkeni tanımlı değil")
 r=draft(json.loads(a.pack.read_text(encoding="utf-8")),key,offset=a.offset,limit=a.limit,question_ids=set(a.question_id) or None); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__ == "__main__": main()
