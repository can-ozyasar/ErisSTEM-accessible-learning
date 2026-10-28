from copy import deepcopy
import pytest
from app.pipeline.history_rag_sealed_review import prepare


def fixtures():
    q={'id':'q1','parts':[{'text':'Babil kenti'}],'source':{'page':1}}
    doc={'id':'d1','section_id':'2.1','page':3,'bbox':[0,0,1,1], 'text':'Babil kenti gelişti.'}
    book={'source_checksum':'q','questions':[{'question':q}]}
    index={'source_checksum':'s','sections':[{'id':'2.1','title':'Konu'}]}
    experimental={'source_checksum':'s','chunks':[doc]}
    payload={'schema':'history-rag-sealed-input-v1','question_source_checksum':'q','evidence_source_checksum':'s',
             'coverage':{'2.1':{}}, 'documents':[{k:doc[k] for k in ('id','section_id','page','text')}],
             'queries':[{'question_id':'q1','section_id':'2.1','topic':'Konu','query':'Babil kenti'}]}
    result={'schema':'history-rag-sealed-results-v1','input_sha256':'hash','status':'complete',
            'rankings':[{'question_id':'q1','bm25':['d1'],'dense':['d1'],'rrf':['d1']}]}
    return payload,result,book,index,experimental


def test_pool_is_blind_and_shared_for_identical_evidence():
    payload,result,book,index,exp=fixtures()
    sample,mapping=prepare(payload,'hash',result,book,index,exp)
    assert len(sample['cases'][0]['evidence'])==1
    assert len(set(mapping['cases'][0]['ranks']['topic']+mapping['cases'][0]['ranks']['quality']))==1
    assert sample['cases'][0]['evidence'][0]['label'] is None


def test_rejects_changed_source_or_foreign_rank():
    payload,result,book,index,exp=fixtures()
    altered=deepcopy(payload);altered['documents'][0]['text']='Farklı'
    with pytest.raises(ValueError,match='differs'):prepare(altered,'hash',result,book,index,exp)
    altered=deepcopy(result);altered['rankings'][0]['dense']=['foreign']
    with pytest.raises(ValueError,match='foreign'):prepare(payload,'hash',altered,book,index,exp)
    altered=deepcopy(result);altered['rankings'][0]['bm25']=[]
    with pytest.raises(ValueError,match='BM25 differs'):prepare(payload,'hash',altered,book,index,exp)
