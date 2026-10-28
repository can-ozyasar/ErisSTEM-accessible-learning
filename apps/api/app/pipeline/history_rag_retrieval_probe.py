"""Small local retrieval diagnostic; evaluates designated IDs, not answer quality."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from ..history_rag import load_index, retrieve


def compare(index, experimental, cases, k=3):
    if experimental.get('schema') != 'history-rag-experimental-candidates-v1' or experimental.get('source_checksum') != index['source_checksum']:
        raise ValueError('experimental source mismatch')
    if k < 1 or not cases:
        raise ValueError('invalid cases or k')
    variants = {'baseline': index, 'experimental': {'sections': index['sections'], 'chunks': experimental['chunks']}}
    rows = []
    for case in cases:
        topic = case['topic']
        result = {'question': case['question'], 'topic': topic, 'target_original_id': case['target_original_id']}
        for name, corpus in variants.items():
            ranked = retrieve(corpus, {c['id'] for c in corpus['chunks']}, topic, case['question'], limit=k)
            hits = [{'id': c['id'], 'original_id': c.get('original_id', c['id']), 'page': c['page'],
                     'score': c['score'], 'text': c['text']} for c in ranked]
            result[name] = {'target_hit': any(c['original_id'] == case['target_original_id'] for c in hits), 'retrieved': hits}
        rows.append(result)
    return {'schema': 'history-rag-retrieval-probe-v1', 'source_checksum': index['source_checksum'], 'k': k,
            'cases': rows, 'summary': {name: {'designated_id_hits': sum(r[name]['target_hit'] for r in rows), 'cases': len(rows)} for name in variants},
            'notice': 'Target IDs and questions were written after inspecting sources; experimental corpus includes these selected targets. All candidates are treated as available, including unapproved; not production retrieval, semantic recall, answer quality or an independent benchmark.'}


def main():
    p=argparse.ArgumentParser()
    for arg in ('source', 'index', 'experimental', 'cases', 'output'):
        p.add_argument('--'+arg, type=Path, required=True)
    a=p.parse_args()
    root=(Path(__file__).resolve().parents[4]/'data/private').resolve()
    if not a.output.resolve().is_relative_to(root): raise ValueError('output must be inside data/private')
    index=load_index(a.source,a.index)
    result=compare(index,json.loads(a.experimental.read_text(encoding='utf-8')),json.loads(a.cases.read_text(encoding='utf-8')))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result['summary'],ensure_ascii=False))

if __name__ == '__main__': main()
