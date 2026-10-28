import pytest
from app.pipeline.history_rag_dense_compare import rankings


def test_all_rankers_respect_teacher_approval_and_topic_gate():
    index={'sections':[{'id':'1.1','title':'Tarih Konusu'},{'id':'2.1','title':'Diğer Konu'}],
           'chunks':[{'id':'allowed','section_id':'1.1','page':1,'text':'Tarih kaynakları bilgi sağlar.'},
                     {'id':'unapproved','section_id':'1.1','page':2,'text':'Tarih kaynakları'},
                     {'id':'other','section_id':'2.1','page':3,'text':'Tarih kaynakları'}]}
    embeddings={'allowed':[1,0], 'unapproved':[1,0], 'other':[1,0]}
    result=rankings(index,{'allowed','other'},'Tarih Konusu','Tarih kaynakları',[1,0],embeddings)
    assert result=={'bm25':['allowed'],'dense':['allowed'],'rrf':['allowed']}
    assert rankings(index,{'allowed'},'Belirsiz','Tarih',[1,0],embeddings)=={'bm25':[],'dense':[],'rrf':[]}


def test_invalid_and_missing_vectors_fail_closed():
    index={'sections':[{'id':'1.1','title':'Tarih Konusu'}],
           'chunks':[{'id':'a','section_id':'1.1','page':1,'text':'Tarih.'}]}
    with pytest.raises(ValueError,match='missing'):
        rankings(index,{'a'},'Tarih Konusu','Tarih',[1,0],{})
    with pytest.raises(ValueError,match='zero'):
        rankings(index,{'a'},'Tarih Konusu','Tarih',[1,0],{'a':[0,0]})
    with pytest.raises(ValueError,match='invalid'):
        rankings(index,{'a'},'Tarih Konusu','Tarih',[1,0],{'a':[float('nan'),1]})
