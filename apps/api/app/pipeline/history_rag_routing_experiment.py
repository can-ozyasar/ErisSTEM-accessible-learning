"""Research-only topic-routing and ranking comparison on a fresh question sample."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

from ..history_rag import load_index, matching_sections, retrieve
from ..question_bank_extract import extract_book
from .history_rag_paired_review import canonical, select_questions, write

SYSTEMS = ('topic', 'quality', 'routing_quality')
PENALIZED = {'rubrik_kontrolu', 'etkinlik_veya_degerlendirme'}


def rank(index, chunks, topic, question, k=3, margin=1.25, penalty=.25):
    """Same global BM25 weights for all variants; route by score margin, then rerank."""
    allowed = matching_sections(index, topic)
    if len(allowed) != 1:
        return {name: [] for name in SYSTEMS}, {'given_section': None, 'proposed_section': None, 'switched': False}
    synthetic = {'sections': [{'id': 'all', 'title': 'Deney Havuzu'}],
                 'chunks': [{**c, 'section_id': 'all'} for c in chunks]}
    original_by_id = {c['id']: c for c in chunks}
    scored = retrieve(synthetic, set(original_by_id), 'Deney Havuzu', question, limit=len(chunks))
    scored = [{**original_by_id[c['id']], 'score': c['score']} for c in scored]
    in_topic = [c for c in scored if c['section_id'] == allowed[0]]
    top_section = scored[0]['section_id'] if scored else allowed[0]
    in_score = in_topic[0]['score'] if in_topic else 0
    switched = bool(scored and top_section != allowed[0] and scored[0]['score'] > margin * in_score)
    selected = top_section if switched else allowed[0]
    def sorted_quality(section):
        rows = [c for c in scored if c['section_id'] == section]
        return sorted(rows, key=lambda c: (-c['score'] * (penalty if PENALIZED.intersection(c.get('review_flags', [])) else 1), c['page'], c['id']))[:k]
    return {'topic': in_topic[:k], 'quality': sorted_quality(allowed[0]),
            'routing_quality': sorted_quality(selected)}, {'given_section': allowed[0], 'proposed_section': selected, 'switched': switched}


def prepare(book, index, experimental, previous, seed=20261028, k=3):
    if experimental.get('source_checksum') != index['source_checksum']:
        raise ValueError('source checksum mismatch')
    if previous.get('question_source_checksum') != book['source_checksum']:
        raise ValueError('question source checksum mismatch')
    excluded = {x['question']['id'] for x in previous['cases']}
    filtered = {**book, 'questions': [x for x in book['questions'] if x['question']['id'] not in excluded]}
    selected, populations = select_questions(filtered, index, 2, seed)
    rng = random.Random(seed + 1)
    review_cases, mappings = [], []
    for case in selected:
        q=case['question']; query=' '.join(x.get('text','') for x in q['parts'])
        rankings, routing=rank(index, experimental['chunks'], case['topic'], query, k=k)
        pool={}; ranks={}
        for system, hits in rankings.items():
            ranks[system]=[]
            for c in hits:
                evidence={key:c.get(key,[] if key in ('segments','source_attributions') else None) for key in ('page','bbox','text','segments','source_attributions')}
                eid=hashlib.sha256(canonical(evidence).encode()).hexdigest()[:20]
                pool[eid]={'evidence_id':eid, **evidence, 'label':None, 'reviewer':None, 'source_checked':False}
                ranks[system].append(eid)
        evidence=list(pool.values());rng.shuffle(evidence)
        review_cases.append({'question':q,'topic':case['topic'],'section_id':case['section_id'],
                             'question_source_checked':False,'question_reviewer':None,'evidence':evidence})
        mappings.append({'question_id':q['id'],'ranks':ranks,'routing':routing})
    sample={'schema':'history-rag-routing-review-v1','question_source_checksum':book['source_checksum'],
            'evidence_source_checksum':index['source_checksum'],'seed':seed,'k':k,
            'excluded_question_ids':sorted(excluded),'eligible_section_counts':populations,'cases':review_cases,
            'notice':'Top-k pooled research candidates; source systems and routing are concealed. No approvals.'}
    mapping={'schema':'history-rag-routing-mapping-v1','sample_sha256':hashlib.sha256(canonical(sample).encode()).hexdigest(),'cases':mappings}
    return sample,mapping


def score(sample,mapping,reviewed):
    if mapping.get('sample_sha256') != hashlib.sha256(canonical(sample).encode()).hexdigest():
        raise ValueError('sample mismatch')
    keys=('schema','question_source_checksum','evidence_source_checksum','seed','k','excluded_question_ids','eligible_section_counts')
    if any(sample.get(k)!=reviewed.get(k) for k in keys):raise ValueError('metadata mismatch')
    originals={c['question']['id']:c for c in sample['cases']}
    if len(reviewed.get('cases',[]))!=len(originals) or len(mapping.get('cases',[]))!=len(originals):raise ValueError('case count mismatch')
    labels={};checked=set();seen=set()
    for c in reviewed['cases']:
        qid=c['question']['id']
        if qid not in originals or qid in seen:raise ValueError('invalid question')
        seen.add(qid);orig=originals[qid]
        if any(c.get(k)!=orig[k] for k in ('question','topic','section_id')):raise ValueError('question changed')
        if c.get('question_source_checked') is True and isinstance(c.get('question_reviewer'),str) and c['question_reviewer'].strip():checked.add(qid)
        elif c.get('question_source_checked') is not False or c.get('question_reviewer') is not None:raise ValueError('invalid question review')
        es={x['evidence_id']:x for x in orig['evidence']}
        if len(c.get('evidence',[]))!=len(es):raise ValueError('invalid evidence count')
        encountered=set()
        for item in c['evidence']:
            eid=item['evidence_id']
            if eid not in es or eid in encountered:raise ValueError('invalid evidence identity')
            encountered.add(eid)
            if any(item.get(k)!=es[eid][k] for k in ('page','bbox','text','segments','source_attributions')):raise ValueError('evidence changed')
            label=item.get('label')
            if label is None:
                if item.get('source_checked') is not False or item.get('reviewer') is not None:raise ValueError('invalid unreviewed evidence')
            elif label not in ('relevant','irrelevant','uncertain') or item.get('source_checked') is not True or not isinstance(item.get('reviewer'),str) or not item['reviewer'].strip():raise ValueError('invalid label')
            labels[qid,eid]=label
    seen=set();results={name:[] for name in SYSTEMS}
    for m in mapping['cases']:
        qid=m.get('question_id')
        if qid not in originals or qid in seen or set(m.get('ranks',{}))!=set(SYSTEMS):raise ValueError('invalid mapping')
        seen.add(qid)
        for system in SYSTEMS:
            ids=m['ranks'][system]
            if len(ids)>sample['k'] or len(ids)!=len(set(ids)) or any((qid,eid) not in labels for eid in ids):raise ValueError('invalid ranks')
            values=[labels[qid,eid] for eid in ids]
            if qid in checked and all(v is not None for v in values):results[system].append(values)
    scores={name:{'questions_evaluated':len(rows),'questions_with_relevant':sum('relevant' in r for r in rows),
                  'relevant':sum(r.count('relevant') for r in rows),'irrelevant':sum(r.count('irrelevant') for r in rows),
                  'uncertain':sum(r.count('uncertain') for r in rows),'returned':sum(map(len,rows))} for name,rows in results.items()}
    return {'schema':'history-rag-routing-report-v1','questions':len(originals),'scores':scores,
            'switched':sum(bool(c['routing']['switched']) for c in mapping['cases']),
            'notice':'AI or reviewer labels on pooled top-k only; candidate corpus is unapproved; not production performance or corpus recall.'}


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    pre=sub.add_parser('prepare')
    for x in ('question-pdf','source','index','experimental','previous','sample','mapping'):pre.add_argument('--'+x,type=Path,required=True)
    ev=sub.add_parser('score')
    for x in ('sample','mapping','reviewed','output'):ev.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':
        idx=load_index(a.source,a.index);book=extract_book(a.question_pdf)
        sample,mapping=prepare(book,idx,json.loads(a.experimental.read_text()),json.loads(a.previous.read_text()))
        write(a.sample,sample);write(a.mapping,mapping)
        print(json.dumps({'questions':len(sample['cases']),'pool':sum(len(x['evidence']) for x in sample['cases'])}))
    else:
        result=score(*(json.loads(getattr(a,k).read_text()) for k in ('sample','mapping','reviewed')))
        write(a.output,result);print(json.dumps(result['scores'],ensure_ascii=False))

if __name__=='__main__':main()
