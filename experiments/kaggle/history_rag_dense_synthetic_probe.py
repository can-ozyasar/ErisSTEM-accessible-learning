"""Private Kaggle BGE-M3 dense/BM25/RRF smoke test on fabricated Turkish text.

No user, textbook, question-bank or annotation data is included. This verifies
inference mechanics only; synthetic hit rates do not estimate education quality.
"""
from __future__ import annotations
import json
import math
import platform
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

OUT=Path('/kaggle/working/history_rag_dense_probe.json')
MODEL='BAAI/bge-m3'
REVISION='5617a9f61b028005a4858fdac845db406aefb181'
report={'schema':'history-rag-dense-synthetic-v1','model':MODEL,'revision':REVISION,
        'synthetic_only':True,'status':'started','python':platform.python_version(),'stages':{},
        'notice':'Fabricated smoke test; no estimate of Turkish educational retrieval quality.'}

def save():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

def stage(name,fn):
    start=time.monotonic()
    try:
        data=fn()
        report['stages'][name]={'status':'ok','seconds':round(time.monotonic()-start,3),**(data or {})}
        save();return True
    except Exception as exc:
        report['stages'][name]={'status':'failed','seconds':round(time.monotonic()-start,3),
                                'error_type':type(exc).__name__,'error':str(exc)[:800]}
        traceback.print_exc();save();return False

save()
if not stage('install',lambda:(subprocess.run([sys.executable,'-m','pip','install','-q','sentence-transformers==3.4.1'],check=True),{})[1]):
    report['status']='install_failed';save();sys.exit(1)

import numpy as np
import torch
import transformers
import sentence_transformers
from sentence_transformers import SentenceTransformer

report['versions']={'torch':torch.__version__,'transformers':transformers.__version__,
                    'sentence_transformers':sentence_transformers.__version__,'numpy':np.__version__}
report['gpus']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
if not torch.cuda.is_available():
    report['status']='no_gpu';save();sys.exit(1)

# Invented place names, unrelated to textbook content; all labels are hand-made fixtures.
DOCS=[('d1','Arva topluluğu yerleşimlerini göl kıyısına kurmuş, balıkçılıkla geçimini sağlamıştır.'),
      ('d2','Bera halkı kurak yaylalarda koyun sürülerini otlatmak için mevsimlere göre yer değiştirmiştir.'),
      ('d3','Celu kentinde meclis kararları kil levhalara yazılarak ortak arşivde saklanmıştır.'),
      ('d4','Dona çiftçileri sulama kanalları açarak tarlalarına nehirden su taşımıştır.'),
      ('d5','Evin ustaları bakırı eritip küçük süs eşyaları üretmiştir.')]
CASES=[('q1','Arva halkı yiyeceğini nasıl kazanıyordu?',{'d1'}),
       ('q2','Hangi topluluk sürüler için yılın farklı dönemlerinde göç etmiştir?',{'d2'}),
       ('q3','Celu meclisinin kararları nasıl kaydedildi?',{'d3'}),
       ('q4','Dona tarlalarına su nereden ulaştırıldı?',{'d4'}),
       ('q5','Bakır kullanarak takı yapanlar kimdi?',{'d5'})]

model=None

def load():
    global model
    torch.cuda.reset_peak_memory_stats()
    model=SentenceTransformer(MODEL,revision=REVISION,device='cuda',trust_remote_code=False)
    return {'peak_gib':round(torch.cuda.max_memory_allocated()/2**30,3),
            'dimension':model.get_sentence_embedding_dimension(),'max_seq_length':model.max_seq_length}

if not stage('load',load):report['status']='load_failed';save();sys.exit(1)

TOKEN=re.compile(r'[a-zçğıöşü0-9]+')
def terms(text):return TOKEN.findall(text.translate(str.maketrans('Iİ','ıi')).casefold())
def bm25(query,documents):
    docs=[Counter(terms(t)) for _,t in documents];q=set(terms(query));avg=sum(sum(d.values()) for d in docs)/len(docs)
    df=Counter(k for d in docs for k in d)
    return [sum(math.log(1+(len(docs)-df[t]+.5)/(df[t]+.5))*d[t]*2.2/(d[t]+1.2*(.25+.75*sum(d.values())/avg))
                for t in q & d.keys()) for d in docs]

def run():
    torch.cuda.synchronize();start=time.monotonic()
    matrix=model.encode([x[1] for x in DOCS],batch_size=5,normalize_embeddings=True,convert_to_numpy=True)
    torch.cuda.synchronize();index_seconds=time.monotonic()-start
    start=time.monotonic()
    queries=model.encode([x[1] for x in CASES],batch_size=5,normalize_embeddings=True,convert_to_numpy=True)
    torch.cuda.synchronize();query_seconds=time.monotonic()-start
    sim=queries @ matrix.T
    methods={name:[] for name in ('bm25','dense','rrf')}
    for i,(_,q,expected) in enumerate(CASES):
        lex=bm25(q,DOCS)
        lex_order=sorted(range(len(DOCS)),key=lambda j:(-lex[j],j))
        dense_order=sorted(range(len(DOCS)),key=lambda j:(-float(sim[i,j]),j))
        fusion={j:1/(60+lex_order.index(j)+1)+1/(60+dense_order.index(j)+1) for j in range(len(DOCS))}
        rrf_order=sorted(range(len(DOCS)),key=lambda j:(-fusion[j],j))
        for name,order in [('bm25',lex_order),('dense',dense_order),('rrf',rrf_order)]:
            methods[name].append({'top1_hit':DOCS[order[0]][0] in expected,
                                  'top3_hit':bool({DOCS[j][0] for j in order[:3]} & expected)})
    return {'device':'cuda','documents':len(DOCS),'questions':len(CASES),
            'index_seconds':round(index_seconds,3),'query_batch_seconds':round(query_seconds,3),
            'peak_gib':round(torch.cuda.max_memory_allocated()/2**30,3),
            'fixture_results':{name:{'top1':sum(x['top1_hit'] for x in rows),
                                     'top3':sum(x['top3_hit'] for x in rows),'cases':len(rows)} for name,rows in methods.items()}}

report['status']='complete' if stage('synthetic_retrieval',run) else 'retrieval_failed'
save()
