"""Local BM25/dense/RRF ranking on already computed vectors; never approves sources.

Callers must compute vectors locally and retain private text and results locally.
This module does not download models, train, or assign relevance labels.
"""
from __future__ import annotations
import math
from ..history_rag import matching_sections, retrieve


def cosine(a, b):
    if not a or len(a) != len(b) or any(not math.isfinite(float(x)) for x in (*a, *b)):
        raise ValueError('invalid embedding')
    aa=sum(float(x)**2 for x in a);bb=sum(float(x)**2 for x in b)
    if aa <= 0 or bb <= 0:raise ValueError('zero embedding')
    return sum(float(x)*float(y) for x,y in zip(a,b))/math.sqrt(aa*bb)


def rankings(index, approved_ids, topic, query, query_vector, document_vectors, k=3, rrf_constant=60):
    if k < 1 or rrf_constant < 1:raise ValueError('invalid ranking parameters')
    section_ids=set(matching_sections(index, topic))
    allowed=[c for c in index['chunks'] if c['id'] in approved_ids and c['section_id'] in section_ids]
    if len({c['id'] for c in allowed})!=len(allowed):raise ValueError('duplicate candidate identity')
    if not allowed:return {'bm25':[],'dense':[],'rrf':[]}
    missing={c['id'] for c in allowed}-document_vectors.keys()
    if missing:raise ValueError('approved candidate embedding missing')
    lexical=retrieve(index,approved_ids,topic,query,limit=len(allowed))
    dense=sorted(((cosine(query_vector, document_vectors[c['id']]),c) for c in allowed),
                 key=lambda x:(-x[0],x[1]['page'],x[1]['id']))
    lex_ids=[c['id'] for c in lexical];dense_ids=[c['id'] for _,c in dense]
    rrf={}
    for ids in (lex_ids,dense_ids):
        for rank,cid in enumerate(ids,1):rrf[cid]=rrf.get(cid,0)+1/(rrf_constant+rank)
    by_id={c['id']:c for c in allowed}
    fusion=sorted(rrf,key=lambda cid:(-rrf[cid],by_id[cid]['page'],cid))
    return {'bm25':lex_ids[:k], 'dense':dense_ids[:k], 'rrf':fusion[:k]}
