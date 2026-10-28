import pytest
from app.pipeline.history_rag_pdf_sentence_catalog import sentences, resolve
from app.pipeline.history_rag_pdf_quote_trace import make_index


def test_extract_only_and_reject_foreign_case_or_source():
    value='Birinci güvenilir cümle. İkinci başka bir cümledir.'
    line={'page':4,'segment':0,'line':0,'chars':[{'char':c,'bbox':[i,0,i+1,1]} for i,c in enumerate(value)]}
    result=sentences(make_index([line]),'src','checksum')
    assert len(result)==2 and result[0]['quote']=='Birinci güvenilir cümle.'
    catalog={'cases':[{'case_id':'question-a','sources':[{'source_id':'src','sentences':result}]}]}
    assert resolve(catalog,'question-a','src',result[0]['sentence_id']) == result[0]
    with pytest.raises(ValueError):resolve(catalog,'question-b','src',result[0]['sentence_id'])
    with pytest.raises(ValueError):resolve(catalog,'question-a','other',result[0]['sentence_id'])
