"""Project validated Qwen dense candidates into the source-review queue."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .prepare_ogm_real_question_evidence_queue import _documents

def build(challenger: dict, corpus: dict, rankings: dict) -> dict:
    if challenger.get("schema") != "ogm-ayt-real-question-evidence-queue-v1": raise ValueError("challenger queue gerekli")
    if rankings.get("schema") != "ogm-ayt-relation-retrieval-rankings-v1": raise ValueError("Qwen rankings gerekli")
    if rankings.get("corpus_checksum") != corpus.get("corpus_checksum") or rankings.get("question_source_checksum", rankings.get("source_checksum")) != challenger.get("question_source_checksum"): raise ValueError("checksum uyuşmazlığı")
    docs={row["id"]:row for row in _documents(corpus)}; proposals=[]
    for row in challenger["proposals"]:
        ids=rankings["rankings"].get(row["candidate_id"],{}).get("qwen_dense",[])[:12]
        if len(ids)!=12 or not set(ids)<=set(docs): raise ValueError("dense top-12 geçersiz")
        suggestions=[docs[item] for item in ids]
        proposals.append({**row,"status":"qwen_dense_candidates_require_independent_pdf_crop_review","suggestions":suggestions})
    return {"schema":"ogm-ayt-real-question-evidence-queue-v1","question_source_checksum":challenger["question_source_checksum"],"corpus_checksum":corpus["corpus_checksum"],"question_count":len(proposals),"retrieval":{"method":"qwen3_embedding_4b_dense","answer_key_used":False,"supplementary_source_used":False},"proposals":proposals,"runtime_enabled":False,"notice":"Dense candidates only; independent full-coverage review required."}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--challenger',type=Path,required=True);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--rankings',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();l=lambda x:json.loads(x.read_text());o=build(l(a.challenger),l(a.corpus),l(a.rankings));a.output.write_text(json.dumps(o,ensure_ascii=False,indent=2));print(len(o['proposals']))
if __name__=='__main__':main()
