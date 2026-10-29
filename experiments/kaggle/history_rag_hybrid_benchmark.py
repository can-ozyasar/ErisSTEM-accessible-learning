"""Private Kaggle runner for BM25, BGE-M3 dense and fixed-k RRF.
Input contains only short teacher-approved snippets and evidence labels."""
from __future__ import annotations
import json, os, time
from pathlib import Path
ROOT=Path('/kaggle/input/history-rag-hybrid-dev-v1'); INPUT=ROOT/'history-rag-hybrid-dev-v1.json'; OUT=Path('/kaggle/working/history-rag-hybrid-report.json')
FORBIDDEN={'answer','answer_key','answer_label','correct_choice','pdf_path','raw_pdf'}
def load():
 data=json.loads(INPUT.read_text())
 if data.get('schema')!='history-rag-hybrid-dev-v1' or data.get('split')!='development': raise ValueError('private development schema required')
 if FORBIDDEN & set(data) or any(FORBIDDEN & set(q) for q in data.get('queries', [])): raise ValueError('answer keys, PDFs and sealed data are forbidden')
 return data
def main():
 data=load(); docs=data['documents']; queries=data['queries']; from rank_bm25 import BM25Okapi; from sentence_transformers import SentenceTransformer; import numpy as np
 tok=lambda x:x.casefold().split(); bm=BM25Okapi([tok(d['text']) for d in docs]); model_id=data.get('bge_m3_model','BAAI/bge-m3'); model=SentenceTransformer(model_id,trust_remote_code=True); vectors=model.encode([d['text'] for d in docs],normalize_embeddings=True,show_progress_bar=True)
 rankings={}; timings=[]
 for q in queries:
  pool=[(i,d) for i,d in enumerate(docs) if d['section_id']==q['section_id']] or list(enumerate(docs)); start=time.perf_counter(); ls=bm.get_scores(tok(q['query'])); lexical=[d['id'] for _,d in sorted(((ls[i],d) for i,d in pool),key=lambda x:(-x[0],x[1]['id']))]; qv=model.encode(q['query'],normalize_embeddings=True); dense=[d['id'] for i,d in sorted(pool,key=lambda x:(-float(np.dot(qv,vectors[x[0]])),x[1]['id']))]; rrf=sorted(set(lexical+dense),key=lambda x:(-(1/(60+lexical.index(x)+1) if x in lexical else 0)-(1/(60+dense.index(x)+1) if x in dense else 0),x)); rankings[q['id']]={'bm25':lexical[:20],'dense':dense[:20],'rrf':rrf[:20]}; timings.append((time.perf_counter()-start)*1000)
 OUT.write_text(json.dumps({'schema':'history-rag-hybrid-result-v1','input_source_checksum':data['source_checksum'],'input_approval_checksum':data['approval_checksum'],'model':model_id,'gpu':os.environ.get('KAGGLE_KERNEL_RUN_TYPE','unknown'),'document_count':len(docs),'query_count':len(queries),'rankings':rankings,'latencies_ms':timings,'reranker':'run only after RRF metric gate'},ensure_ascii=False)); print(OUT)
if __name__=='__main__':main()
