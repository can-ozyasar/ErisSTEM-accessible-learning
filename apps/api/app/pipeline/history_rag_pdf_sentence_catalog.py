"""Build a private, extractive sentence catalog from PDF-backed research cases."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import pymupdf
from .history_rag_independent_eval import digest
from .history_rag_paired_review import canonical,write
from .history_rag_pdf_quote_trace import extract_lines,make_index,trace


def sentences(index,source_id,pdf_checksum):
    result=[];text=index['text']
    # Punctuation splitting is intentionally simple; ambiguous and short spans
    # are discarded rather than completed with guessed source text.
    for match in re.finditer(r'[^.!?]+[.!?](?:[”’\"])?(?:\s+|$)|[^.!?]+$',text):
        q=match.group().strip()
        found=trace(index,q)
        if found['status']!='matched':continue
        material={'source_id':source_id,'pdf_checksum':pdf_checksum,'span':found['normalized_span'],'quote':q}
        identity=hashlib.sha256(canonical(material).encode()).hexdigest()[:24]
        result.append({'sentence_id':identity,**material,'regions':found['regions'],'transformations':found['transformations']})
    return result


def resolve(catalog,case_id,source_id,sentence_id):
    matches=[s for c in catalog['cases'] if c['case_id']==case_id for src in c['sources'] if src['source_id']==source_id for s in src['sentences'] if s['sentence_id']==sentence_id]
    if len(matches)!=1:raise ValueError('unknown, ambiguous, or out-of-case sentence')
    return matches[0]


def build(bundle,pdf,checksum):
    if bundle.get('schema')!='history-rag-answerability-bundle-v1' or bundle.get('split')!='development' or checksum!=bundle['evidence_source_checksum']:
        raise ValueError('invalid bundle or source checksum')
    cases=[]
    for c in bundle['cases']:
        sources=[]
        for e in c['evidence']:
            try:
                index=make_index(extract_lines(pdf,e));rows=sentences(index,e['id'],checksum)
                sources.append({'source_id':e['id'],'page':e['page'],'status':'indexed','sentences':rows})
            except ValueError as exc:
                sources.append({'source_id':e['id'],'page':e['page'],'status':'invalid_regions','error':str(exc),'sentences':[]})
        cases.append({'case_id':c['case_id'],'sources':sources})
    return {'schema':'history-rag-pdf-sentence-catalog-v1','bundle_sha256':digest(bundle),'pdf_checksum':checksum,'cases':cases,
            'notice':'Extractive PDF text only. Sentence occurrence and coordinates do not prove relevance, support, correctness or approval.'}


def main():
    p=argparse.ArgumentParser()
    for k in ('bundle','source','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();bundle=json.loads(a.bundle.read_text());checksum=hashlib.sha256(a.source.read_bytes()).hexdigest()
    with pymupdf.open(a.source) as pdf:catalog=build(bundle,pdf,checksum)
    write(a.output,catalog)
    print(json.dumps({'cases':len(catalog['cases']),'sources':sum(len(c['sources']) for c in catalog['cases']),
                      'sentences':sum(len(s['sentences']) for c in catalog['cases'] for s in c['sources']),
                      'invalid_sources':sum(s['status']!='indexed' for c in catalog['cases'] for s in c['sources'])}))

if __name__=='__main__':main()
