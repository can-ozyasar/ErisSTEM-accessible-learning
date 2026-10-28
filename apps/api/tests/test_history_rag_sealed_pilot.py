import pytest
from app.pipeline.history_rag_sealed_pilot import prepare


def test_pilot_prefers_unexposed_group_and_records_limitations():
    book={'source_checksum':'q', 'questions':[
        {'question':{'id':'a','source':{'page':1},'parts':[{'text':'soru'}]}},
        {'question':{'id':'b','source':{'page':2},'parts':[{'text':'soru iki'}]}}]}
    index={'source_checksum':'s','sections':[{'id':'2.1','title':'Bölüm'}]}
    candidates={'schema':'history-rag-experimental-candidates-v1','source_checksum':'s',
                'chunks':[{'id':'x','section_id':'2.1','page':3,'text':'kaynak'}]}
    clusters={'schema':'history-rag-reviewed-clusters-v1','question_source_checksum':'q','evidence_source_checksum':'s',
              'questions':[{'question_id':'a','section_id':'2.1','group_id':'a','group_exposed':False,'previously_exposed':False,'split':'test'},
                           {'question_id':'b','section_id':'2.1','group_id':'b','group_exposed':True,'previously_exposed':False,'split':'dev'}]}
    result=prepare(book,index,candidates,clusters)
    assert result['queries'][0]['question_id']=='a'
    assert result['queries'][0]['prior_page_exposure'] is False
    assert result['coverage']['2.5']['selected']==0
    assert result['documents'][0]['page']==3
    assert all('label' not in q for q in result['queries'])
    with pytest.raises(ValueError,match='candidate provenance mismatch'):
        prepare(book,index,{**candidates,'source_checksum':'wrong'},clusters)
