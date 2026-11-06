# Private Kaggle dataset: muhammedcanozyasar/eristem-ayt-multisource-dense-local11-12-v1
import json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path('/kaggle/input'); OUT=Path('/kaggle/working/official-ayt-multisource-dense-discovery-rankings-v1.json')
MODEL='Qwen/Qwen3-Embedding-4B'; INSTRUCTION='Verilen MEB tarih sorusu için gereken tarihsel ilişkiyi doğrudan destekleyen kısa kanıt parçasını getir.'
FORBIDDEN={'answer','answer_key','answer_label','correct_choice','worked_explanation','pdf_path','raw_pdf'}; TOKENS=re.compile(r'[a-zçğıöşü0-9]+',re.I)
def tokens(s): return TOKENS.findall(s.translate(str.maketrans('Iİ','ıi')).casefold())
def rank(scores,docs): return [docs[i]['id'] for i in sorted(range(len(docs)),key=lambda i:(-float(scores[i]),docs[i]['id']))]
def rrf(*rs,limit):
 d={}
 for r in rs:
  for pos,x in enumerate(r,1): d[x]=d.get(x,0)+1/(60+pos)
 return [x for x,_ in sorted(d.items(),key=lambda p:(-p[1],p[0]))[:limit]]
inputs=list(ROOT.rglob('input.json'))
if len(inputs)!=1: raise ValueError(f'Tek private girdi gerekli: {inputs}')
data=json.loads(inputs[0].read_text())
INPUT_SCHEMAS={'ayt-multisource-dense-discovery-v1','ayt-full-multisource-dense-discovery-v1'}
if data.get('schema') not in INPUT_SCHEMAS or FORBIDDEN & set(data) or data.get('runtime_enabled') or data.get('qlora_enabled'): raise ValueError('Answer-free discovery girdi sözleşmesi geçersiz')
subprocess.run([sys.executable,'-m','pip','install','-q','sentence-transformers>=5','rank-bm25'],check=True)
import numpy as np, torch
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
docs,queries=data['documents'],data['queries']; texts=[x['text'] for x in docs]; bm=BM25Okapi([tokens(x) for x in texts])
model=SentenceTransformer(MODEL,device='cuda',model_kwargs={'torch_dtype':torch.float16}); model.max_seq_length=1024
vectors=model.encode(texts,batch_size=2,normalize_embeddings=True,show_progress_bar=True); rankings={}; timing=[]
for q in queries:
 start=time.perf_counter(); lex=rank(bm.get_scores(tokens(q['query'])),docs); v=model.encode([f'Instruct: {INSTRUCTION}\nQuery: {q["query"]}'],normalize_embeddings=True,show_progress_bar=False)[0]; dense=rank(np.asarray(vectors)@np.asarray(v),docs); fusion=rrf(lex[:20],dense[:20],limit=20); timing.append((time.perf_counter()-start)*1000); rankings[q['id']]={'bm25':lex[:20],'qwen_dense_tr':dense[:20],'rrf':fusion}
OUT.write_text(json.dumps({'schema':'official-ayt-full-multisource-dense-discovery-rankings-v1' if data['schema']=='ayt-full-multisource-dense-discovery-v1' else 'official-ayt-multisource-dense-discovery-rankings-v1','corpus_checksum':data['corpus_checksum'],'source_bindings':data['source_bindings'],'embedding_model':MODEL,'instruction':INSTRUCTION,'document_count':len(docs),'query_count':len(queries),'rankings':rankings,'latencies_ms':timing,'gpu':torch.cuda.get_device_name(0),'answer_key_accessed':False,'worked_explanation_accessed':False,'runtime_enabled':False,'qlora_enabled':False,'notice':'Candidate discovery only; every ranking requires separate checksum-bound PDF crop review.'},ensure_ascii=False,indent=2))
