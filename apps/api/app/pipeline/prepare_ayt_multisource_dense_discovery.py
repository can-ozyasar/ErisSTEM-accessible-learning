"""Prepare an answer-free 11+12 grade MEB retrieval coverage experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ayt_target_atom_queue import _documents
from .prepare_atom_retrieval_audit import need_plan


def build(pool: dict, corpus: dict) -> dict:
    if pool.get('schema') != 'official-ayt-target-discovery-pool-v1' or corpus.get('schema') != 'multi-history-rag-v1':
        raise ValueError('Resmî havuz ve çok kaynaklı corpus gerekli')
    if pool.get('answer_key_accessed') is not False or pool.get('worked_explanation_accessed') is not False:
        raise ValueError('Cevap veya çözüm erişimli veri kullanılamaz')
    b12=next((b for b in corpus['books'] if b['grade']==12),None); b11=next((b for b in corpus['books'] if b['grade']==11),None)
    if not b11 or not b12: raise ValueError('PDF-doğrulanabilir 11 ve 12. sınıf kaynakları gerekli')
    atoms12,ctx12=_documents(b12,set(pool['candidate_section_ids']))
    # 11th-grade headings do not share 12th-grade section IDs; retain all clean candidates.
    atoms11,ctx11=_documents(b11,{r['section_id'] for r in b11['index']['evidence_atoms']})
    docs=[*atoms12,*ctx12,*atoms11,*ctx11]
    queries=[]
    for r in pool['rows']:
        plan=need_plan(' '.join(r.get('target_section_options',[])),r['question']['stem'])
        queries.append({'id':r['candidate_id'],'query':plan['retrieval_query'],'need_plan':plan,'evaluation_only':True})
    return {'schema':'ayt-multisource-dense-discovery-v1','corpus_checksum':corpus['corpus_checksum'],'source_bindings':[{'source_checksum':b['source_checksum'],'source_name':b['source_name'],'grade':b['grade']} for b in (b11,b12)],'documents':docs,'queries':queries,'answer_key_accessed':False,'worked_explanation_accessed':False,'runtime_enabled':False,'qlora_enabled':False,'notice':'Private answer-free source-coverage experiment. Every candidate requires PDF crop review.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();load=lambda x:json.loads(x.read_text());r=build(load(a.pool),load(a.corpus));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'queries':len(r['queries']),'documents':len(r['documents'])}))
if __name__=='__main__':main()
