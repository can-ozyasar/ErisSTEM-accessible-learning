"""Private BGE-M3/BM25 retrieval over sealed source-derived input.

Only identifiers and scores are exported. This is not an expert accuracy test.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

INPUT=Path('/kaggle/input/datasets/muhammedcanozyasar/history-rag-sealed-pilot-v1/input.json')
EXPECTED='b43bd8c386915aad60c5842d4e77200eb073666ca84229d6ff32d0585527d5b5'
OUT=Path('/kaggle/working/history_rag_sealed_rankings.json')
MODEL='BAAI/bge-m3';REVISION='5617a9f61b028005a4858fdac845db406aefb181'
report={'schema':'history-rag-sealed-results-v1','input_sha256':EXPECTED,'model':MODEL,'revision':REVISION,
        'status':'started','stages':{},'notice':'Private research candidates; identifiers and scores only; relevance not yet judged.'}
def save():
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
def stage(name,fn):
    started=time.monotonic()
    try:
        result=fn();report['stages'][name]={'status':'ok','seconds':round(time.monotonic()-started,3),**(result or {})};save();return True
    except Exception as exc:
        report['stages'][name]={'status':'failed','seconds':round(time.monotonic()-started,3),
                                'error_type':type(exc).__name__,'error':str(exc)[:600]}
        traceback.print_exc();save();return False
save()
if not stage('install',lambda:(subprocess.run([sys.executable,'-m','pip','install','-q','sentence-transformers==3.4.1'],check=True),{})[1]):
    report['status']='install_failed';save();sys.exit(1)
import numpy as np
import torch,transformers,sentence_transformers
from sentence_transformers import SentenceTransformer
report['versions']={'torch':torch.__version__,'transformers':transformers.__version__,'sentence_transformers':sentence_transformers.__version__}
report['gpus']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
if not torch.cuda.is_available():report['status']='no_gpu';save();sys.exit(1)
payload=model=None

def load():
    global payload,model
    raw=INPUT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('input checksum mismatch')
    payload=json.loads(raw)
    if payload.get('schema')!='history-rag-sealed-input-v1':raise ValueError('invalid input schema')
    docs=payload['documents'];queries=payload['queries']
    if len({x['id'] for x in docs})!=len(docs) or len({x['question_id'] for x in queries})!=len(queries):raise ValueError('duplicate ids')
    torch.cuda.reset_peak_memory_stats()
    model=SentenceTransformer(MODEL,revision=REVISION,device='cuda',trust_remote_code=False)
    model.max_seq_length=512
    return {'documents':len(docs),'questions':len(queries),'max_seq_length':512,
            'peak_gib':round(torch.cuda.max_memory_allocated()/2**30,3)}
if not stage('load',load):report['status']='load_failed';save();sys.exit(1)
TOKENS=re.compile(r'[a-zçğıöşü0-9]+',re.I)
STOP={'ve','veya','ile','bir','bu','da','de','için','olan','olarak','tarih','tarihi','tarihin','hangi','aşağıdaki','göre','ise','en','ne'}
def terms(text):return [x for x in TOKENS.findall(text.translate(str.maketrans('Iİ','ıi')).casefold()) if len(x)>2 and x not in STOP]

def execute():
    docs=payload['documents'];queries=payload['queries'];torch.cuda.reset_peak_memory_stats()
    start=time.monotonic();matrix=model.encode([d['text'] for d in docs],batch_size=8,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    torch.cuda.synchronize();doc_s=time.monotonic()-start
    start=time.monotonic();qmatrix=model.encode([q['query'] for q in queries],batch_size=4,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    torch.cuda.synchronize();query_s=time.monotonic()-start
    trunc_docs=sum(len(model.tokenizer(d['text'],truncation=False)['input_ids'])>512 for d in docs)
    trunc_queries=sum(len(model.tokenizer(q['query'],truncation=False)['input_ids'])>512 for q in queries)
    results=[]
    for n,q in enumerate(queries):
        indices=[i for i,d in enumerate(docs) if d['section_id']==q['section_id']]
        if not indices:results.append({'question_id':q['question_id'],'bm25':[],'dense':[],'rrf':[]});continue
        counters=[Counter(terms(docs[i]['text'])) for i in indices];freq=Counter(t for c in counters for t in c)
        average=sum(sum(c.values()) for c in counters)/len(counters);qterms=set(terms(q['query']))
        scores=[]
        for local,i in enumerate(indices):
            c=counters[local];length=sum(c.values());score=0.0
            for t in qterms & c.keys():
                idf=math.log(1+(len(indices)-freq[t]+.5)/(freq[t]+.5))
                score+=idf*c[t]*2.2/(c[t]+1.2*(.25+.75*length/average))
            if score>0:scores.append((score,docs[i]['id']))
        pages={d['id']:d['page'] for d in docs}
        lexical=[x[1] for x in sorted(scores,key=lambda x:(-x[0],pages[x[1]],x[1]))]
        similarities=matrix[indices] @ qmatrix[n]
        dense=[docs[indices[i]]['id'] for i in sorted(range(len(indices)),key=lambda i:(-float(similarities[i]),pages[docs[indices[i]]['id']],docs[indices[i]]['id']))]
        fusion={}
        for ranked in (lexical,dense):
            for rank,cid in enumerate(ranked,1):fusion[cid]=fusion.get(cid,0.0)+1/(60+rank)
        rrf=sorted(fusion,key=lambda cid:(-fusion[cid],pages[cid],cid))
        results.append({'question_id':q['question_id'],'bm25':lexical[:3],'dense':dense[:3],'rrf':rrf[:3]})
    report['rankings']=results
    return {'doc_embedding_seconds':round(doc_s,3),'query_embedding_seconds':round(query_s,3),
            'documents_truncated':trunc_docs,'queries_truncated':trunc_queries,
            'peak_gib':round(torch.cuda.max_memory_allocated()/2**30,3)}
report['status']='complete' if stage('retrieve',execute) else 'retrieve_failed';save()
