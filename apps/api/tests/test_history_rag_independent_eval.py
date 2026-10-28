import copy
import json
import pytest
from app.pipeline.history_rag_independent_eval import digest, exposure, freeze, score


def test_exposure_covers_prior_cases_advisory_and_pilot(tmp_path):
    files = []
    for i, doc in enumerate([
        {'cases':[{'question':{'id':'q1','source':{'page':3}}}]},
        {'advisory_pairs_before_grouping':[{'question_ids':['q2','q3'],'pages':[4,5]}]},
        {'schema':'history-rag-sealed-input-v1','queries':[{'question_id':'q4','page':6}]},
    ]):
        p=tmp_path/f'{i}.json'; p.write_text(json.dumps(doc)); files.append(p)
    assert exposure(files) == ({'q1','q2','q3','q4'}, {3,4,5,6})


def test_freeze_blocks_entire_exposed_group_and_preserves_group_split():
    rows=[{'question_id':f'q{i}', 'page':i, 'section_id':'2.2', 'group_id':f'g{(i-1)//2}'} for i in range(1,7)]
    clusters={'schema':'history-rag-reviewed-clusters-v1','question_source_checksum':'q',
              'evidence_source_checksum':'e','questions':rows}
    result=freeze(clusters,['2.1','2.2'],{'q1'},set())
    assert {r['question_id'] for r in result['questions']} == {'q3','q4','q5','q6'}
    assert result['section_counts']['2.1'] == {}
    assert {r['split'] for r in result['questions']} == {'development','test'}
    for group in ('g1','g2'):
        assert len({r['split'] for r in result['questions'] if r['group_id']==group}) == 1


def test_answerability_separates_uncertain_and_refuses_unreviewed():
    bundle={'schema':'history-rag-answerability-bundle-v1','cases':[
        {'case_id':'a','choice_labels':['A','B']}, {'case_id':'b','choice_labels':['A','B']},
        {'case_id':'c','choice_labels':['A','B']} ]}
    h=digest(bundle)
    gold={'bundle_sha256':h,'cases':[
        {'case_id':'a','answerability':'sufficient','answer_label':'A','reviewer':'teacher','source_checked':True},
        {'case_id':'b','answerability':'insufficient','answer_label':None,'reviewer':'teacher','source_checked':True},
        {'case_id':'c','answerability':'uncertain','answer_label':None,'reviewer':'teacher','source_checked':True}]}
    predictions={'bundle_sha256':h,'cases':[{'case_id':'a','action':'answer','answer_label':'A'},
        {'case_id':'b','action':'answer','answer_label':'B'}, {'case_id':'c','action':'abstain','answer_label':None}]}
    report=score(bundle,gold,predictions)
    assert report['counts']=={'sufficient_answer':1,'insufficient_answer':1,'uncertain_abstain':1}
    assert report['answer_correctness_given_sufficient_and_answered']=={'correct':1}
    broken=copy.deepcopy(gold);broken['cases'][1]['source_checked']=False
    with pytest.raises(ValueError):score(bundle,broken,predictions)
    broken=copy.deepcopy(predictions);broken['bundle_sha256']='different'
    with pytest.raises(ValueError):score(bundle,gold,broken)


def test_development_package_never_contains_test_questions():
    from app.pipeline.history_rag_independent_eval import prepare_development
    q=lambda identity: {'question':{'id':identity,'source':{'page':1},'parts':[{'text':'ticaret'}],
                                  'choices':[{'label':'A','text':'X'}], 'answer_label':'A'}}
    book={'source_checksum':'book','questions':[q('development'),q('holdout')]}
    manifest={'schema':'history-rag-independent-candidates-v1','question_source_checksum':'book',
              'evidence_source_checksum':'source','questions':[
                  {'question_id':'development','section_id':'2.2','split':'development'},
                  {'question_id':'holdout','section_id':'2.2','split':'test'}]}
    index={'source_checksum':'source','sections':[{'id':'2.2','title':'Tarih'}]}
    experimental={'source_checksum':'source','chunks':[{'id':'x','section_id':'2.2','page':1,
        'bbox':[1,2,3,4],'text':'ticaret','segments':[],'source_attributions':[]}]}
    bundle=prepare_development(manifest,book,index,experimental)
    assert len(bundle['cases'])==2
    assert {c['question']['id'] for c in bundle['cases']} == {'development'}
    assert all('answer_label' not in c['question'] for c in bundle['cases'])
    assert [len(c['evidence']) for c in bundle['cases']]==[1,0]
