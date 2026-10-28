"""Apply provisional duplicate reviews without treating them as expert labels."""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from .history_rag_paired_review import write
from .history_rag_question_splits import page_split


def regroup(manifest, reviews):
    if manifest.get('schema')!='history-rag-question-clusters-v1' or reviews.get('schema')!='history-rag-cluster-review-v1':
        raise ValueError('schema mismatch')
    if reviews.get('question_source_checksum') != manifest['question_source_checksum']:
        raise ValueError('source mismatch')
    candidates={tuple(x['question_ids']) for x in manifest['advisory_pairs_before_grouping']}
    judgments=reviews.get('pairs',[])
    if len(judgments)!=len(candidates):raise ValueError('review count mismatch')
    seen=set()
    for item in judgments:
        pair=tuple(item.get('question_ids',[]))
        if pair not in candidates or pair in seen or item.get('label') not in ('shared_stimulus','distinct_template','uncertain') or not item.get('reviewer'):
            raise ValueError('invalid review')
        seen.add(pair)
    rows={r['question_id']:r for r in manifest['questions']}; parent={k:k for k in rows}
    def find(k):
        while parent[k]!=k:
            parent[k]=parent[parent[k]];k=parent[k]
        return k
    def union(a,b):
        x,y=find(a),find(b)
        if x!=y:parent[max(x,y)]=min(x,y)
    groups=defaultdict(list)
    for k,v in rows.items():groups[v['group_id']].append(k)
    for members in groups.values():
        for other in members[1:]:union(members[0],other)
    for item in judgments:
        if item['label'] in ('shared_stimulus','uncertain'):
            a,b=item['question_ids'];union(a,b)
    groups=defaultdict(list)
    for k in rows:groups[find(k)].append(k)
    result=[];sections=defaultdict(Counter)
    for members in groups.values():
        pages=sorted({rows[k]['page'] for k in members}); group_id='pages:'+','.join(map(str,pages))
        split=page_split(manifest['question_source_checksum'],pages[0],manifest['seed'])
        exposed=any(rows[k]['page_exposed_in_prior_samples'] for k in members)
        for k in members:
            row={**rows[k],'group_id':group_id,'split':split,'group_exposed':exposed}
            result.append(row);sections[row['section_id']][split]+=1
    result.sort(key=lambda r:(r['page'],r['question_id']))
    return {'schema':'history-rag-reviewed-clusters-v1','question_source_checksum':manifest['question_source_checksum'],
            'evidence_source_checksum':manifest['evidence_source_checksum'],'seed':manifest['seed'],
            'questions':result,'counts':dict(Counter(r['split'] for r in result)),
            'section_counts':{k:dict(v) for k,v in sorted(sections.items())},
            'review_labels':dict(Counter(x['label'] for x in judgments)),
            'notice':'Provisional AI review of extracted question text. Unknown near duplicates remain; not an independent expert-validated split.'}


def main():
    p=argparse.ArgumentParser()
    for x in ('manifest','reviewed','output'):p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();result=regroup(json.loads(a.manifest.read_text()),json.loads(a.reviewed.read_text()));write(a.output,result)
    print(json.dumps({'counts':result['counts'],'section_counts':result['section_counts'],'review_labels':result['review_labels']},ensure_ascii=False))

if __name__=='__main__':main()
