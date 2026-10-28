"""Prepare a private, limited real-question retrieval pilot without relevance labels.

Input may contain copyrighted excerpts; never publish. Selection explicitly marks
previously exposed groups and cannot produce an expert-validated test by itself.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
from ..history_rag import load_index
from ..question_bank_extract import extract_book
from .history_rag_paired_review import write


def prepare(book,index,experimental,clusters,seed=20261030):
    if clusters.get('schema')!='history-rag-reviewed-clusters-v1' or clusters.get('question_source_checksum')!=book['source_checksum'] or clusters.get('evidence_source_checksum')!=index['source_checksum']:
        raise ValueError('cluster provenance mismatch')
    if experimental.get('schema')!='history-rag-experimental-candidates-v1' or experimental.get('source_checksum')!=index['source_checksum']:
        raise ValueError('candidate provenance mismatch')
    questions={i['question']['id']:i['question'] for i in book['questions']}
    rng=random.Random(seed);chosen=[];coverage={}
    # The question bank only maps four sections. Select one group per covered
    # section, preferring groups never included in the three recent pilots.
    for section in ('2.1','2.2','2.3','2.5'):
        rows=[r for r in clusters['questions'] if r['section_id']==section]
        clean=[r for r in rows if not r['group_exposed'] and not r['previously_exposed']]
        eligible=clean if clean else [r for r in rows if not r['previously_exposed']]
        if not eligible:
            coverage[section]={'selected':0,'reason':'no available question'};continue
        groups=sorted({r['group_id'] for r in eligible});group=rng.choice(groups)
        candidate=sorted((r for r in eligible if r['group_id']==group),key=lambda r:r['question_id'])
        row=rng.choice(candidate);q=questions[row['question_id']]
        topic=next(s['title'] for s in index['sections'] if s['id']==section)
        chosen.append({'question_id':q['id'],'section_id':section,'page':q['source']['page'],
                       'group_id':row['group_id'],'prior_page_exposure':row['group_exposed'],
                       'source_split':row['split'],'topic':topic,
                       'query':' '.join(part.get('text','') for part in q['parts'])})
        coverage[section]={'selected':1,'prior_page_exposure':row['group_exposed'],'eligible_groups':len(groups)}
    sections={q['section_id'] for q in chosen}
    docs=[{'id':c['id'],'section_id':c['section_id'],'page':c['page'],'text':c['text']} for c in experimental['chunks'] if c['section_id'] in sections]
    if not docs or len({c['id'] for c in docs})!=len(docs):raise ValueError('invalid document set')
    return {'schema':'history-rag-sealed-input-v1','question_source_checksum':book['source_checksum'],
            'evidence_source_checksum':index['source_checksum'],'seed':seed,'coverage':coverage,
            'documents':docs,'queries':chosen,
            'notice':'Private source-derived text, no relevance labels; unapproved research candidates. Do not publish.'}


def main():
    p=argparse.ArgumentParser()
    for x in ('question-pdf','source','index','experimental','clusters','output'):p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args();book=extract_book(a.question_pdf);index=load_index(a.source,a.index)
    result=prepare(book,index,json.loads(a.experimental.read_text()),json.loads(a.clusters.read_text()))
    write(a.output,result)
    print(json.dumps({'queries':len(result['queries']),'documents':len(result['documents']),'coverage':result['coverage'],
                      'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()},ensure_ascii=False))

if __name__=='__main__':main()
