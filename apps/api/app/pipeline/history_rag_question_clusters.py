"""Group pages and lexical near-duplicates for research splits, not semantic proof."""
from __future__ import annotations
import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from ..history_rag import fold, load_index, terms
from ..question_bank_extract import extract_book
from .history_rag_paired_review import write
from .history_rag_question_splits import build, page_split


def signature(text):
    normalized = re.sub(r'\s+', ' ', fold(text)).strip()
    grams = {normalized[i:i+4] for i in range(max(0, len(normalized)-3))}
    return set(terms(text)), grams


def jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def cluster(book, index, exposed_ids, exposed_pages, seed=20261029):
    base=build(book,index,exposed_ids,exposed_pages,seed)
    rows={r['question_id']:r for r in base['questions']}
    texts={i['question']['id']:' '.join(p.get('text','') for p in i['question'].get('parts',[]))
           for i in book['questions'] if i['question']['id'] in rows}
    signatures={key:signature(text) for key,text in texts.items()}
    parent={key:key for key in rows}
    def find(key):
        while parent[key]!=key:
            parent[key]=parent[parent[key]];key=parent[key]
        return key
    def union(a,b):
        x,y=find(a),find(b)
        if x!=y:parent[max(x,y)]=min(x,y)
    pages=defaultdict(list)
    for key,row in rows.items():pages[row['page']].append(key)
    for ids in pages.values():
        for identity in ids[1:]:union(ids[0],identity)
    similar=[]; advisory=[]
    for a,b in itertools.combinations(sorted(rows),2):
        if rows[a]['page']==rows[b]['page']:continue
        ta,ga=signatures[a];tb,gb=signatures[b]
        token=jaccard(ta,tb);character=jaccard(ga,gb)
        if token>=.28 and character>=.3 and rows[a]['split'] != rows[b]['split'] and min(len(ta),len(tb))>=5:
            advisory.append({'question_ids':[a,b], 'pages':[rows[a]['page'],rows[b]['page']],
                             'token_jaccard':round(token,3), 'char4_jaccard':round(character,3)})
        if token>=.6 and character>=.7 and min(len(ta),len(tb))>=5:
            union(a,b)
            similar.append({'question_ids':[a,b],'pages':[rows[a]['page'],rows[b]['page']],
                            'token_jaccard':round(token,3),'char4_jaccard':round(character,3),
                            'original_cross_split':rows[a]['split'] != rows[b]['split']})
    groups=defaultdict(list)
    for key in rows:groups[find(key)].append(key)
    new=[]
    for members in groups.values():
        group_pages=sorted({rows[key]['page'] for key in members})
        group_id='pages:'+','.join(map(str,group_pages))
        # All connected pages follow the same immutable assignment.
        split=page_split(book['source_checksum'],group_pages[0],seed)
        group_exposed=any(rows[k]['page_exposed_in_prior_samples'] for k in members)
        for key in members:new.append({**rows[key],'original_split':rows[key]['split'],
                                       'split':split,'group_id':group_id,'group_exposed':group_exposed})
    new.sort(key=lambda x:(x['page'],x['question_id']))
    counts=Counter(x['split'] for x in new); section=defaultdict(Counter)
    for x in new:section[x['section_id']][x['split']]+=1
    return {'schema':'history-rag-question-clusters-v1','question_source_checksum':book['source_checksum'],
            'evidence_source_checksum':index['source_checksum'],'seed':seed,'thresholds':{'tokens':.6,'char4':.7},
            'questions':new,'counts':dict(counts),'section_counts':{k:dict(v) for k,v in sorted(section.items())},
            'near_duplicate_pairs':similar,'advisory_pairs_before_grouping':advisory,'group_count':len(groups),
            'notice':'Heuristic lexical duplicates and same pages only; semantic paraphrases and shared knowledge can still cross splits. No expert labels.'}


def main():
    p=argparse.ArgumentParser()
    for x in ('question-pdf','source','index','previous-one','previous-two','previous-three','output'):p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();book=extract_book(a.question_pdf);index=load_index(a.source,a.index);ids=set();pages=set()
    for path in (a.previous_one,a.previous_two,a.previous_three):
        sample=json.loads(path.read_text(encoding='utf-8'))
        if sample.get('question_source_checksum')!=book['source_checksum']:raise ValueError('question checksum mismatch')
        ids.update(x['question']['id'] for x in sample['cases']);pages.update(x['question']['source']['page'] for x in sample['cases'])
    result=cluster(book,index,ids,pages);write(a.output,result)
    print(json.dumps({'counts':result['counts'],'section_counts':result['section_counts'],
                      'cross_split_pairs_before':sum(x['original_cross_split'] for x in result['near_duplicate_pairs']),
                      'near_pairs':len(result['near_duplicate_pairs']),'advisory_cross_split_pairs':len(result['advisory_pairs_before_grouping']),'groups':result['group_count']},ensure_ascii=False))

if __name__=='__main__':main()
