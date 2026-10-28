import copy
import pytest
from app.pipeline.history_rag_independent_eval import digest
from app.pipeline.history_rag_extractive_selection import evaluate


def test_case_scoped_sentence_selection_rejects_foreign_id():
    bundle={'cases':[{'case_id':'q','question':{'id':'q'},'choice_labels':['A'],'evidence':[{}]}]}
    sent={'sentence_id':'one','source_id':'src','text':'Kaynak metni örneği.'}
    catalog={'bundle_sha256':digest(bundle),'cases':[{'case_id':'q','sources':[{'source_id':'src','sentences':[{'sentence_id':'one','quote':sent['text']}]}]}]}
    inp={'bundle_sha256':digest(bundle),'catalog_sha256':digest(catalog),'cases':[{'case_id':'q','question':{'id':'q'},'choice_labels':['A'],'sentences':[sent]}]}
    labels={'bundle_sha256':digest(bundle),'cases':[{'case_id':'q','answerability':'sufficient','answer_label':'A','source_checked':True,'reviewer':'reviewer'}]}
    bundle['schema']='history-rag-answerability-bundle-v1'
    # Rebind all input fingerprints after adding the schema.
    catalog['bundle_sha256']=digest(bundle);inp['bundle_sha256']=digest(bundle);inp['catalog_sha256']=digest(catalog);labels['bundle_sha256']=digest(bundle)
    result={'decision':'sufficient','answer_label':'A','sentence_id':'one','explanation':'metin'}
    raw={'status':'complete','input_sha256':digest(inp),'cases':[{'case_id':'q','result':result}]}
    predictions,_=evaluate(bundle,labels,catalog,inp,raw)
    assert predictions['cases'][0]['action']=='answer'
    raw2=copy.deepcopy(raw);raw2['cases'][0]['result']['sentence_id']='foreign'
    predictions,_=evaluate(bundle,labels,catalog,inp,raw2)
    assert predictions['cases'][0]['reason']=='invalid_selection'
    raw2['input_sha256']='wrong'
    with pytest.raises(ValueError):evaluate(bundle,labels,catalog,inp,raw2)
