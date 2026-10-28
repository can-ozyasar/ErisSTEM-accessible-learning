from app.pipeline.history_rag_question_splits import build, page_split


def test_page_grouping_is_deterministic_and_exposure_is_separate(monkeypatch):
    import app.pipeline.history_rag_question_splits as module
    monkeypatch.setattr(module, '_layout_contaminated', lambda question: False)
    book={'source_checksum':'book','page_contexts':{1:{'topic':'Konu'},2:{'topic':'Konu'}},
          'questions':[{'issues':[], 'question':{'id':name,'source':{'page':page},'visuals':[]}}
                       for name,page in [('a',1),('b',1),('c',2)]]}
    index={'source_checksum':'evidence','sections':[{'id':'1.1','title':'Konu'}]}
    result=build(book,index,{'a'},{1})
    rows={r['question_id']:r for r in result['questions']}
    assert rows['a']['split']==rows['b']['split']==page_split('book',1,20261029)
    assert rows['a']['previously_exposed'] and not rows['b']['previously_exposed']
    assert rows['b']['page_exposed_in_prior_samples'] and not rows['c']['page_exposed_in_prior_samples']
    assert result==build(book,index,{'a'},{1})
