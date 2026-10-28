"""Convert a sealed Kaggle ID-only ranking result to a local pooled review."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
from ..history_rag import load_index, retrieve
from ..question_bank_extract import extract_book
from .history_rag_paired_review import canonical, write
from .history_rag_routing_experiment import score


def prepare(payload, payload_hash, result, book, index, experimental, seed=20261030):
    if result.get('schema')!='history-rag-sealed-results-v1' or result.get('status')!='complete' or result.get('input_sha256')!=payload_hash:
        raise ValueError('missing, failed or foreign ranking result')
    if payload.get('schema')!='history-rag-sealed-input-v1' or payload['question_source_checksum']!=book['source_checksum'] or payload['evidence_source_checksum']!=index['source_checksum'] or experimental['source_checksum']!=index['source_checksum']:
        raise ValueError('source provenance mismatch')
    docs={x['id']:x for x in experimental['chunks']}
    for item in payload['documents']:
        c=docs.get(item['id'])
        if not c or any(item.get(k)!=c[k] for k in ('section_id','page','text')):raise ValueError('input document differs from source candidate')
    allowed={x['id'] for x in payload['documents']}
    if len(allowed)!=len(payload['documents']):raise ValueError('duplicate document ids')
    questions={i['question']['id']:i['question'] for i in book['questions']}
    qs={q['question_id']:q for q in payload['queries']}
    if len(qs)!=len(payload['queries']):raise ValueError('duplicate question ids')
    results=result.get('rankings',[])
    if len(results)!=len(qs):raise ValueError('ranking size mismatch')
    rng=random.Random(seed);sample_cases=[];mapped=[];seen=set()
    research_index={'sections':index['sections'],'chunks':[docs[k] for k in allowed]}
    for ranking in results:
        qid=ranking.get('question_id')
        if qid not in qs or qid in seen or qid not in questions:raise ValueError('unknown or duplicate question')
        seen.add(qid);query=qs[qid];q=questions[qid]
        if query['query']!=' '.join(part.get('text','') for part in q['parts']):raise ValueError('question content mismatch')
        exact=[x['id'] for x in retrieve(research_index,allowed,query['topic'],query['query'],limit=3)]
        if ranking.get('bm25')!=exact:raise ValueError('remote BM25 differs from local implementation')
        pool={};ranks={}
        for source,target in (('bm25','topic'),('dense','quality'),('rrf','routing_quality')):
            ids=ranking.get(source)
            if not isinstance(ids,list) or len(ids)>3 or len(ids)!=len(set(ids)):
                raise ValueError('invalid ranking')
            ranks[target]=[]
            for cid in ids:
                c=docs.get(cid)
                if cid not in allowed or c['section_id']!=query['section_id']:raise ValueError('foreign or out-of-section candidate')
                evidence={key:c.get(key,[] if key in ('segments','source_attributions') else None) for key in ('page','bbox','text','segments','source_attributions')}
                eid=hashlib.sha256(canonical(evidence).encode()).hexdigest()[:20]
                pool[eid]={'evidence_id':eid,**evidence,'label':None,'reviewer':None,'source_checked':False}
                ranks[target].append(eid)
        evidence=list(pool.values());rng.shuffle(evidence)
        public={key:value for key,value in q.items() if key not in ('answer_label','answer_source_checked')}
        sample_cases.append({'question':public,'topic':query['topic'],'section_id':query['section_id'],
                             'question_source_checked':False,'question_reviewer':None,'evidence':evidence})
        mapped.append({'question_id':qid,'ranks':ranks,'routing':{'switched':False}})
    sample={'schema':'history-rag-routing-review-v1','question_source_checksum':book['source_checksum'],
            'evidence_source_checksum':index['source_checksum'],'seed':seed,'k':3,
            'excluded_question_ids':[], 'eligible_section_counts':payload['coverage'],'cases':sample_cases,
            'notice':'Private pooled model comparison; unapproved research candidates and provisional labels; prior exposure tracked in input.'}
    mapping={'schema':'history-rag-routing-mapping-v1','sample_sha256':hashlib.sha256(canonical(sample).encode()).hexdigest(),
             'cases':mapped,'system_meanings':{'topic':'bm25','quality':'bge_m3','routing_quality':'rrf'}}
    return sample,mapping


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('prepare')
    for arg in ('input','result','question-pdf','source','index','experimental','sample','mapping'):create.add_argument('--'+arg,type=Path,required=True)
    evaluate=sub.add_parser('score')
    for arg in ('sample','mapping','reviewed','output'):evaluate.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':
        raw=a.input.read_bytes();sample,mapping=prepare(json.loads(raw),hashlib.sha256(raw).hexdigest(),json.loads(a.result.read_text()),
             extract_book(a.question_pdf),load_index(a.source,a.index),json.loads(a.experimental.read_text()))
        write(a.sample,sample);write(a.mapping,mapping)
        print(json.dumps({'questions':len(sample['cases']),'pool':sum(len(c['evidence']) for c in sample['cases'])}))
    else:
        sample,mapping,reviewed=(json.loads(getattr(a,k).read_text()) for k in ('sample','mapping','reviewed'))
        result=score(sample,mapping,reviewed);result['system_meanings']=mapping['system_meanings']
        result['notice']='Pooled top-3 provisional relevance labels on unapproved research candidates; no production-quality or recall claim.'
        write(a.output,result);print(json.dumps(result['scores'],ensure_ascii=False))

if __name__=='__main__':main()
