import copy
import pytest
from app.pipeline.history_rag_independent_eval import digest
from app.pipeline.history_rag_semantic_judge import prepare, evaluate


def test_judge_requires_matching_input_and_all_three_checks():
    bundle={'schema':'history-rag-answerability-bundle-v1','cases':[{'case_id':'q','question':{'id':'q'},
        'choice_labels':['A','B'],'evidence':[{'text':'Kaynak metni'}]}]}
    prediction={'bundle_sha256':digest(bundle),'cases':[{'case_id':'q','action':'answer','answer_label':'A',
        'citation':{'source':1,'quote':'Kaynak metni'},'explanation':'A'}]}
    labels={'bundle_sha256':digest(bundle),'cases':[{'case_id':'q','answerability':'sufficient',
        'answer_label':'A','reviewer':'human-code','source_checked':True}]}
    inp=prepare(bundle,prediction)
    judge={'status':'complete','input_sha256':digest(inp),'cases':[{'case_id':'q','checks':{
        'choice_consistent':'yes','answer_supported':'uncertain','explanation_supported':'yes'}}]}
    result,_=evaluate(bundle,labels,prediction,inp,judge)
    assert result['cases'][0]['action']=='abstain'
    judge['cases'][0]['checks']['answer_supported']='yes'
    result,_=evaluate(bundle,labels,prediction,inp,judge)
    assert result['cases'][0]['action']=='answer'
    altered=copy.deepcopy(inp);altered['cases'][0]['answer_label']='B'
    with pytest.raises(ValueError):evaluate(bundle,labels,prediction,altered,judge)
    judge['cases'][0]['checks']={}
    result,_=evaluate(bundle,labels,prediction,inp,judge)
    assert result['cases'][0]['reason']=='invalid_judge'
