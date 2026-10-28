"""Research-only fail-closed structural gate for cited answer experiments.

An exact quote proves occurrence, never semantic entailment or expert approval.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from .history_rag_independent_eval import digest, score
from .history_rag_paired_review import write


def valid_citation(citation, evidence):
    if not isinstance(citation, dict) or set(citation) != {'source','quote'}: return False
    source, quote = citation['source'], citation['quote']
    if type(source) is not int or not 1 <= source <= len(evidence) or not isinstance(quote,str): return False
    # Match only whitespace normalization. Never fuzzy-match or repair a quote.
    norm=lambda s: re.sub(r'\s+', ' ', s).strip()
    quote=norm(quote); text=norm(evidence[source-1]['text'])
    return len(quote)>=12 and quote in text


def evaluate_case(case, raw):
    if not case['evidence']:
        if raw.get('gate') != {'decision':'no_evidence'} or raw.get('answer') is not None:
            raise ValueError('empty controls require deterministic no-evidence gate')
        return {'case_id':case['case_id'],'action':'abstain','answer_label':None,'reason':'no_evidence'}
    gate=raw.get('gate'); answer=raw.get('answer')
    def abstain(reason):return {'case_id':case['case_id'],'action':'abstain','answer_label':None,'reason':reason}
    if not isinstance(gate,dict): return abstain('invalid_gate')
    if gate.get('decision')=='insufficient':
        if answer is not None: raise ValueError('answer generated after negative gate')
        return abstain('gate_insufficient')
    if gate.get('decision')!='sufficient':return abstain('invalid_gate')
    if gate.get('answer_label') not in case['choice_labels'] or not valid_citation(gate.get('citation'),case['evidence']):
        return abstain('invalid_gate_evidence')
    if not isinstance(answer,dict) or answer.get('answer_label') not in case['choice_labels']:
        return abstain('invalid_answer')
    if answer['answer_label'] != gate['answer_label']:return abstain('answer_disagrees_with_gate')
    if not valid_citation(answer.get('citation'),case['evidence']):return abstain('invalid_answer_evidence')
    explanation=answer.get('explanation')
    if not isinstance(explanation,str) or not explanation.strip() or len(explanation)>500:return abstain('invalid_explanation')
    return {'case_id':case['case_id'],'action':'answer','answer_label':answer['answer_label'],
            'reason':'structurally_valid','citation':answer['citation'],'explanation':explanation}


def evaluate(bundle, labels, raw):
    if bundle.get('schema')!='history-rag-answerability-bundle-v1' or bundle.get('split')!='development':raise ValueError('invalid bundle')
    if raw.get('status')!='complete' or raw.get('bundle_sha256')!=digest(bundle):raise ValueError('incomplete or foreign run')
    cases=bundle['cases']; rows=raw.get('cases',[])
    if len(rows)!=len(cases) or len({x.get('case_id') for x in rows})!=len(cases) or {x['case_id'] for x in rows}!={x['case_id'] for x in cases}:
        raise ValueError('invalid case set')
    indexed={x['case_id']:x for x in rows}
    predictions={'schema':'history-rag-gated-predictions-v1','bundle_sha256':digest(bundle),
                 'cases':[evaluate_case(c,indexed[c['case_id']]) for c in cases]}
    report=score(bundle,labels,predictions)
    from collections import Counter
    report['gate_reasons']=dict(Counter(x['reason'] for x in predictions['cases']))
    report['notice']='Provisional development labels. Exact quote presence is structural only; semantic support and explanation need independent review.'
    return predictions,report


def main():
    p=argparse.ArgumentParser()
    for k in ('bundle','labels','raw','predictions','report'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(); values=[json.loads(getattr(a,k).read_text()) for k in ('bundle','labels','raw')]
    predictions,report=evaluate(*values);write(a.predictions,predictions);write(a.report,report)
    print(json.dumps({'counts':report['counts'],'gate_reasons':report['gate_reasons']},ensure_ascii=False))

if __name__=='__main__':main()
