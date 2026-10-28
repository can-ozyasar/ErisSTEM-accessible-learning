"""Freeze page-grouped local question splits, with no claim of semantic deduplication."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..history_rag import load_index, matching_sections
from ..question_bank_extract import extract_book
from ..question_bank_routes import _layout_contaminated
from .history_rag_paired_review import write


def page_split(checksum: str, page: int, seed: int) -> str:
    key=f'{seed}:{checksum}:{page}'.encode()
    value=int.from_bytes(hashlib.sha256(key).digest()[:8], 'big') / (2**64)
    return 'train' if value < .6 else 'dev' if value < .8 else 'test'


def build(book, index, exposed_ids, exposed_pages, seed=20261029):
    if not isinstance(exposed_ids, set) or not isinstance(exposed_pages, set): raise ValueError('exposure sets required')
    eligible=[]; counts=Counter(); by_section=defaultdict(Counter)
    for item in book['questions']:
        q=item['question']
        if item['issues'] or _layout_contaminated(q) or q.get('visuals'): continue
        topic=(book['page_contexts'].get(q['source']['page']) or {}).get('topic')
        section=matching_sections(index,topic)
        if len(section)!=1: continue
        split=page_split(book['source_checksum'],q['source']['page'],seed)
        row={'question_id':q['id'],'page':q['source']['page'],'section_id':section[0],
             'split':split,'previously_exposed':q['id'] in exposed_ids,
             'page_exposed_in_prior_samples':q['source']['page'] in exposed_pages}
        counts[split]+=1;by_section[section[0]][split]+=1;eligible.append(row)
    eligible.sort(key=lambda x:(x['page'],x['question_id']))
    return {'schema':'history-rag-question-splits-v1','question_source_checksum':book['source_checksum'],
            'evidence_source_checksum':index['source_checksum'],'seed':seed,'questions':eligible,
            'counts':dict(counts),'section_counts':{k:dict(v) for k,v in sorted(by_section.items())},
            'notice':'Pages are grouped; cross-page paraphrases and common source leakage remain. Exposed questions must not be treated as a clean test.'}


def main():
    p=argparse.ArgumentParser()
    for name in ('question-pdf','source','index','previous-one','previous-two','previous-three','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();book=extract_book(a.question_pdf);index=load_index(a.source,a.index);previous=[];pages=set()
    for path in (a.previous_one,a.previous_two,a.previous_three):
        item=json.loads(path.read_text(encoding='utf-8'))
        if item.get('question_source_checksum') != book['source_checksum']:raise ValueError('question checksum mismatch')
        previous.extend(c['question']['id'] for c in item['cases'])
        pages.update(c['question']['source']['page'] for c in item['cases'])
    result=build(book,index,set(previous),pages);write(a.output,result)
    clean=Counter(q['split'] for q in result['questions'] if not q['previously_exposed'] and not q['page_exposed_in_prior_samples'])
    print(json.dumps({'counts':result['counts'],'pages_not_in_three_samples_counts':dict(clean),'section_counts':result['section_counts']},ensure_ascii=False))

if __name__=='__main__':main()
