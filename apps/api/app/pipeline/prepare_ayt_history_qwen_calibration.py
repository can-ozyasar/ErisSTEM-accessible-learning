"""Export answer-free frozen AYT atom retrieval input for a private GPU run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "ogm-ayt-discovery-calibration-v1"

def build(pack: dict, split: dict, corpus: dict) -> dict:
    if pack.get("schema") != "ayt-history-original-question-candidate-pack-v1" or len(pack.get("questions", [])) != 120:
        raise ValueError("120 aday paketi gerekli")
    if split.get("schema") != "ayt-history-candidate-split-v1" or split.get("candidate_checksum") != pack.get("candidate_checksum"):
        raise ValueError("Eşleşen split gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or corpus.get("corpus_checksum") != pack.get("corpus_checksum"):
        raise ValueError("Eşleşen corpus gerekli")
    ids={r.get("id") for r in split.get("records",[]) if r.get("split")=="retrieval_test"}
    questions={r.get("id"):r for r in pack["questions"]}
    if len(ids)!=24 or not ids <= set(questions): raise ValueError("24 kilitli sorgu gerekli")
    docs_by_id={}
    for book in corpus.get("books",[]):
        for atom in book.get("index",{}).get("evidence_atoms",[]):
            if not isinstance(atom.get("id"),str) or not isinstance(atom.get("text"),str): raise TypeError("Geçerli atom gerekli")
            row={"id":f'{book["source_checksum"]}:{atom["id"]}',"search_text":atom["text"]}
            if row["id"] in docs_by_id and docs_by_id[row["id"]] != row: raise ValueError("Çelişkili atom kimliği")
            docs_by_id[row["id"]]=row
    return {"schema":SCHEMA,"source_checksum":pack["candidate_checksum"],"corpus_checksum":corpus["corpus_checksum"],
      "queries":[{"id":i,"query":" ".join([questions[i]["question"],*questions[i]["choices"]]),"question_source":"original_candidate_answer_blind"} for i in sorted(ids)],
      "documents":sorted(docs_by_id.values(),key=lambda x:x["id"]),"answer_key_accessed":False,"worked_explanation_accessed":False,"runtime_enabled":False,"qlora_enabled":False,
      "notice":"Private answer-free Qwen dense/RRF candidate input; no PDF, labels, explanations or student data."}

def main():
 p=argparse.ArgumentParser(); p.add_argument("--candidate-pack",type=Path,required=True); p.add_argument("--split",type=Path,required=True); p.add_argument("--corpus",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args(); load=lambda x:json.loads(x.read_text(encoding="utf-8")); out=build(load(a.candidate_pack),load(a.split),load(a.corpus)); a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__": main()
