from app.pipeline.history_rag_question_clusters import cluster


def test_page_groups_and_similar_cross_page_questions_share_split(monkeypatch):
    import app.pipeline.history_rag_question_clusters as module
    rows=[{'question_id':'a','page':1,'section_id':'1.1','split':'train','previously_exposed':False,'page_exposed_in_prior_samples':False},
          {'question_id':'b','page':2,'section_id':'1.1','split':'test','previously_exposed':False,'page_exposed_in_prior_samples':True},
          {'question_id':'c','page':2,'section_id':'1.1','split':'test','previously_exposed':False,'page_exposed_in_prior_samples':True}]
    monkeypatch.setattr(module,'build',lambda *args: {'questions':rows})
    text='Tarım faaliyetlerinde sulama kanallarının toplumsal yaşam üzerindeki etkileri nelerdir?'
    book={'source_checksum':'book','questions':[{'question':{'id':key,'parts':[{'text':text if key!='c' else 'Bambaşka bir soru içeriği var.'}]}} for key in ('a','b','c')]}
    index={'source_checksum':'index'}
    result=cluster(book,index,set(),set())
    by_id={r['question_id']:r for r in result['questions']}
    assert by_id['a']['split']==by_id['b']['split']==by_id['c']['split']
    assert by_id['a']['group_exposed']
    assert any(x['original_cross_split'] for x in result['near_duplicate_pairs'])
