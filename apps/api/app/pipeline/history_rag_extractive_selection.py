"""Evaluate model selections against a fixed, case-scoped PDF sentence catalog."""
import argparse
import json
from collections import Counter
from pathlib import Path
from .history_rag_independent_eval import digest,score
from .history_rag_paired_review import write
from .history_rag_pdf_sentence_catalog import resolve


def evaluate(bundle,labels,catalog,inputs,raw):
    checksum=digest(bundle)
    if catalog.get('bundle_sha256')!=checksum or inputs.get('bundle_sha256')!=checksum or inputs.get('catalog_sha256')!=digest(catalog):raise ValueError('provenance mismatch')
    if raw.get('status')!='complete' or raw.get('input_sha256')!=digest(inputs):raise ValueError('incomplete or foreign run')
    original={c['case_id']:c for c in bundle['cases']};sample={c['case_id']:c for c in inputs['cases']}
    catalog_by_id={c['case_id']:c for c in catalog['cases']}
    if len(catalog_by_id)!=len(catalog['cases']) or set(catalog_by_id)!=set(original):raise ValueError('catalog case mismatch')
    for cid,c in original.items():
        if cid not in sample:raise ValueError('missing input case')
        expected=[{'sentence_id':x['sentence_id'],'source_id':src['source_id'],'text':x['quote']} for src in catalog_by_id[cid]['sources'] for x in src['sentences']]
        if sample[cid].get('question')!=c.get('question') or sample[cid].get('choice_labels')!=c['choice_labels'] or sample[cid].get('sentences')!=expected:raise ValueError('input differs from bundle or catalog')
    rows=raw.get('cases',[])
    if len(rows)!=len(original) or len(sample)!=len(original) or len({r.get('case_id') for r in rows})!=len(original) or {r['case_id'] for r in rows}!=set(original) or set(sample)!=set(original):raise ValueError('case mismatch')
    predictions=[]
    for r in rows:
        cid=r['case_id'];c=original[cid];d=r.get('result');reason='invalid_output';answer=None;extra={}
        if not sample[cid]['sentences']:
            if d!={'decision':'no_evidence'}:raise ValueError('empty case is not deterministic')
            reason='no_evidence'
        elif isinstance(d,dict) and d.get('decision')=='insufficient':reason='model_insufficient'
        elif isinstance(d,dict) and d.get('decision')=='sufficient':
            label=d.get('answer_label');sid=d.get('sentence_id');explanation=d.get('explanation')
            candidates=[s for s in sample[cid]['sentences'] if s['sentence_id']==sid]
            if label not in c['choice_labels'] or len(candidates)!=1 or not isinstance(explanation,str) or not explanation.strip() or len(explanation)>500:
                reason='invalid_selection'
            else:
                s=candidates[0];match=resolve(catalog,cid,s['source_id'],sid)
                if s['text']!=match['quote']:raise ValueError('catalog selection modified')
                answer=label;reason='extractive_selection';extra={'source_id':s['source_id'],'sentence_id':sid,'explanation':explanation}
        predictions.append({'case_id':cid,'action':'answer' if answer else 'abstain','answer_label':answer,'reason':reason,**extra})
    output={'schema':'history-rag-extractive-predictions-v1','bundle_sha256':checksum,'catalog_sha256':digest(catalog),'cases':predictions}
    report=score(bundle,labels,output);report['reasons']=dict(Counter(x['reason'] for x in predictions))
    report['notice']='PDF sentence identity is verifiable but relevance, answer support and explanation grounding still require review.'
    return output,report


def main():
    p=argparse.ArgumentParser()
    for k in ('bundle','labels','catalog','inputs','raw','output','report'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();read=lambda k:json.loads(getattr(a,k).read_text());out,report=evaluate(*(read(k) for k in ('bundle','labels','catalog','inputs','raw')))
    write(a.output,out);write(a.report,report);print(json.dumps({'counts':report['counts'],'reasons':report['reasons']}))
if __name__=='__main__':main()
