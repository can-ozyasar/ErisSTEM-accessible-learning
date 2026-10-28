"""Research-only PDF quote index with reversible character-level source regions.

Only an explicit PDF soft hyphen at the end of a line may be removed. Visible
hyphens, punctuation and letters are never repaired. An occurrence says nothing
about whether the quote supports an answer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import pymupdf
from .history_rag_independent_eval import digest
from .history_rag_paired_review import write


def make_index(lines):
    """Return normalized search text and provenance for every retained character."""
    text=[]; refs=[]; changes=[]
    for line in lines:
        chars=line['chars']
        while chars and chars[0]['char'].isspace(): chars=chars[1:]
        if not chars: continue
        while text and text[-1]==' ':text.pop();refs.pop()
        if text:
            if text[-1]=='\u00ad' and chars[0]['char'].islower():
                changes.append({'type':'pdf_soft_hyphen_line_break','at':len(text)-1,'source':refs[-1]})
                text.pop();refs.pop()
            else:
                text.append(' ');refs.append(None)
        for c in chars:
            char=c['char']
            if len(char)!=1:raise ValueError('each PDF character must be one code point')
            if char.isspace():
                if not text or text[-1]==' ':continue
                char=' '
            text.append(char);refs.append({'page':line['page'],'bbox':c['bbox'],'segment':line['segment'],'line':line['line']})
    while text and text[-1]==' ':text.pop();refs.pop()
    return {'text':''.join(text),'refs':refs,'changes':changes}


def trace(index, quote):
    if not isinstance(quote,str):return {'status':'invalid'}
    q=re.sub(r'\s+',' ',quote).strip()
    if len(q)<12:return {'status':'invalid'}
    hay=index['text'];start=hay.find(q)
    if start<0:return {'status':'not_found'}
    if hay.find(q,start+1)>=0:return {'status':'ambiguous'}
    end=start+len(q); grouped={}
    for ref in index['refs'][start:end]:
        if ref is None:continue
        key=(ref['page'],ref['segment'],ref['line']);bbox=ref['bbox']
        if key not in grouped:grouped[key]=list(bbox)
        else:
            a=grouped[key];a[0]=min(a[0],bbox[0]);a[1]=min(a[1],bbox[1]);a[2]=max(a[2],bbox[2]);a[3]=max(a[3],bbox[3])
    return {'status':'matched','normalized_span':[start,end],'quote':q,
            'regions':[{'page':k[0],'segment':k[1],'line':k[2],'bbox':[round(x,2) for x in v]} for k,v in grouped.items()],
            'transformations':[c for c in index['changes'] if start<=c['at']<end]}


def extract_lines(pdf, evidence):
    segments=evidence.get('segments') or [{'page':evidence['page'],'bbox':evidence['bbox']}]
    if not segments:raise ValueError('missing source regions')
    lines=[]; previous=None
    for sn,seg in enumerate(segments):
        page=seg['page'];box=pymupdf.Rect(seg['bbox'])
        if not isinstance(page,int) or page<1 or page>len(pdf) or box.is_empty or not pdf[page-1].rect.contains(box):raise ValueError('invalid PDF region')
        if previous is not None:
            pp,pb=previous
            overlap=max(0,min(pb.x1,box.x1)-max(pb.x0,box.x0))
            if page!=pp or box.y0 < pb.y1-1 or box.y0-pb.y1 > 20 or overlap < .7*min(pb.width,box.width):
                raise ValueError('noncontiguous or ambiguous segment boundary')
        previous=(page,box)
        blocks=pdf[page-1].get_text('rawdict',clip=box)['blocks']
        for block in blocks:
            if block.get('type')!=0:continue
            for line in block['lines']:
                chars=[]
                for span in line['spans']:
                    for ch in span['chars']:
                        chars.append({'char':ch['c'],'bbox':[round(float(v),3) for v in ch['bbox']]})
                if chars:lines.append({'page':page,'segment':sn,'line':len(lines),'chars':chars})
    return lines


def main():
    p=argparse.ArgumentParser()
    for k in ('bundle','raw','source','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();bundle=json.loads(a.bundle.read_text());raw=json.loads(a.raw.read_text())
    if bundle.get('split')!='development' or raw.get('status')!='complete' or raw.get('bundle_sha256')!=digest(bundle):raise ValueError('input mismatch')
    checksum=hashlib.sha256(a.source.read_bytes()).hexdigest()
    if checksum!=bundle['evidence_source_checksum']:raise ValueError('PDF checksum mismatch')
    cases={c['case_id']:c for c in bundle['cases']};results=[]
    with pymupdf.open(a.source) as pdf:
        for row in raw['cases']:
            c=cases[row['case_id']]
            for stage in ('gate','answer'):
                data=row.get(stage)
                citation=data.get('citation') if isinstance(data,dict) else None
                if not isinstance(citation,dict):continue
                number=citation.get('source');quote=citation.get('quote')
                if type(number) is not int or not 1<=number<=len(c['evidence']):
                    results.append({'case_id':row['case_id'],'stage':stage,'status':'invalid_source'});continue
                evidence=c['evidence'][number-1]
                try:
                    index=make_index(extract_lines(pdf,evidence));hit=trace(index,quote)
                except ValueError as exc:hit={'status':'invalid_regions','error':str(exc)}
                results.append({'case_id':row['case_id'],'stage':stage,'source_id':evidence['id'],**hit})
    out={'schema':'history-rag-pdf-quote-traces-v1','bundle_sha256':digest(bundle),'pdf_checksum':checksum,'results':results,
         'notice':'Private research output. Source occurrence does not establish entailment or source approval.'}
    write(a.output,out)
    from collections import Counter
    print(json.dumps({'results':len(results),'status_counts':dict(Counter(x['status'] for x in results))},ensure_ascii=False))

if __name__=='__main__':main()
