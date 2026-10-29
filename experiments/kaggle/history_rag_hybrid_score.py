"""Score private BGE/RRF/Qwen-reranker rankings and write the product gate.

The input is a local-only development label file plus the benchmark ranking
output. It does not accept answers, PDFs or sealed test rows.
"""
from __future__ import annotations
import json, math
from pathlib import Path
IN=Path('/kaggle/input/history-rag-hybrid-dev-v1'); LABELS=IN/'history-rag-hybrid-dev-v1.json'; RANKS=Path('/kaggle/working/history-rag-hybrid-report.json'); OUT=Path('/kaggle/working/history-rag-hybrid-gate.json')
FORBIDDEN={'answer','answer_key','answer_label','correct_choice'}
def dcg(v): return sum(x/math.log2(i+2) for i,x in enumerate(v))
def score(queries, rankings, latency):
 r1=r3=mrr=ndcg=coverage=wrong=abstain=answerable=0
 for q in queries:
  result=rankings.get(q['id'],[])[:3]; gold=set(q.get('gold_source_ids',[]))
  if q.get('abstain'): abstain+=not result; continue
  answerable+=1; hits=[x in gold for x in result]; r1+=bool(hits[:1] and hits[0]); r3+=any(hits); coverage+=gold.issubset(set(result)); rank=next((i+1 for i,x in enumerate(hits) if x),0); mrr+=1/rank if rank else 0; ndcg+=dcg([int(x) for x in hits])/dcg([1]*min(3,len(gold))); wrong+=sum(x in set(q.get('wrong_source_ids',[])) for x in result)
 n=max(1,answerable); ordered=sorted(latency); p95=ordered[max(0,math.ceil(.95*len(ordered))-1)] if ordered else 0
 return {'recall_at_1':r1/n,'recall_at_3':r3/n,'mrr_at_3':mrr/n,'ndcg_at_3':ndcg/n,'evidence_coverage_at_3':coverage/n,'wrong_evidence_rate':wrong/max(1,len(queries)*3),'correct_abstention':abstain/max(1,sum(bool(q.get('abstain')) for q in queries)),'p95_ms':p95}
def main():
 labels=json.loads(LABELS.read_text()); run=json.loads(RANKS.read_text())
 if labels.get('split')!='development' or any(FORBIDDEN & set(x) for x in labels.get('queries',[])): raise ValueError('private development labels without answers required')
 variants={name:{qid:value[name] for qid,value in run['rankings'].items() if name in value} for name in ('bm25','dense','rrf','reranker')}
 results={name:score(labels['queries'],value,run['latencies_ms']) for name,value in variants.items() if value}; base=results['bm25']; decisions={}
 for name,result in results.items():
  delta={'recall_at_3':result['recall_at_3']-base['recall_at_3'],'mrr_at_3':result['mrr_at_3']-base['mrr_at_3'],'wrong_evidence_rate':result['wrong_evidence_rate']-base['wrong_evidence_rate']}; decisions[name]={'accepted':delta['recall_at_3']>=.05 and delta['mrr_at_3']>=.03 and delta['wrong_evidence_rate']<=0 and result['p95_ms']<=1000,'delta_vs_bm25':delta}
 OUT.write_text(json.dumps({'schema':'history-rag-hybrid-gate-v1','source_checksum':labels['source_checksum'],'approval_checksum':labels['approval_checksum'],'metrics':results,'decisions':decisions},ensure_ascii=False));print(OUT)
if __name__=='__main__':main()
