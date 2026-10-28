"""Prepare and assess a separate model-based semantic judge, for research only."""
import argparse
import json
from pathlib import Path
from .history_rag_independent_eval import digest,score
from .history_rag_paired_review import write

CHECKS=('choice_consistent','answer_supported','explanation_supported')

def prepare(bundle,predictions):
    if predictions.get('bundle_sha256') != digest(bundle): raise ValueError('bundle mismatch')
    by_id={x['case_id']:x for x in bundle['cases']}
    if len(predictions.get('cases',[])) != len(by_id) or {x['case_id'] for x in predictions['cases']} != set(by_id):raise ValueError('case mismatch')
    cases=[]
    for p in predictions['cases']:
        if p['action']!='answer':continue
        c=by_id[p['case_id']]; cite=p['citation'];number=cite['source']
        if type(number) is not int or not 1 <= number <= len(c['evidence']):raise ValueError('bad citation')
        cases.append({'case_id':c['case_id'],'question':c['question'],'choice_labels':c['choice_labels'],
                      'answer_label':p['answer_label'],'explanation':p['explanation'],
                      'citation':cite,'cited_evidence':c['evidence'][number-1]})
    return {'schema':'history-rag-semantic-judge-input-v1','bundle_sha256':digest(bundle),
            'predictions_sha256':digest(predictions),'cases':cases,
            'notice':'Private source text; no relevance labels. Model judge is not independent expert review.'}


def evaluate(bundle,labels,predictions,judge_input,judge):
    if judge_input != prepare(bundle,predictions):raise ValueError('judge input differs')
    if judge.get('status')!='complete' or judge.get('input_sha256')!=digest(judge_input):raise ValueError('judge input mismatch')
    rows=judge.get('cases',[]);expected={x['case_id'] for x in judge_input['cases']}
    if len(rows)!=len(expected) or {x.get('case_id') for x in rows}!=expected:raise ValueError('judge cases mismatch')
    judged={x['case_id']:x for x in rows};new=[]
    for p in predictions['cases']:
        x={**p}
        if p['action']=='answer':
            verdict=judged[p['case_id']].get('checks')
            if not isinstance(verdict,dict) or set(verdict)!=set(CHECKS) or any(verdict[k] not in ('yes','no','uncertain') for k in CHECKS):
                x={'case_id':p['case_id'],'action':'abstain','answer_label':None,'reason':'invalid_judge'}
            elif not all(verdict[k]=='yes' for k in CHECKS):
                x={'case_id':p['case_id'],'action':'abstain','answer_label':None,'reason':'judge_not_confirmed'}
            else:x['reason']='model_judge_confirmed'
        new.append(x)
    result={'schema':'history-rag-semantic-gated-predictions-v1','bundle_sha256':digest(bundle),'cases':new}
    report=score(bundle,labels,result)
    from collections import Counter
    report['reasons']=dict(Counter(x['reason'] for x in new));report['notice']='Model judge decisions and AI labels are provisional; same-model judging is not independent expert verification.'
    return result,report


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for k in ('bundle','predictions','output'):a.add_argument('--'+k,type=Path,required=True)
    b=sub.add_parser('evaluate')
    for k in ('bundle','labels','predictions','judge-input','judge','output','report'):b.add_argument('--'+k,type=Path,required=True)
    args=p.parse_args()
    read=lambda k:json.loads(getattr(args,k).read_text())
    if args.action=='prepare':
        obj=prepare(read('bundle'),read('predictions'));write(args.output,obj);print(json.dumps({'cases':len(obj['cases']),'input_sha256':digest(obj)}))
    else:
        obj,report=evaluate(*(read(k) for k in ('bundle','labels','predictions','judge_input','judge')));write(args.output,obj);write(args.report,report);print(json.dumps({'counts':report['counts'],'reasons':report['reasons']}))
if __name__=='__main__':main()
