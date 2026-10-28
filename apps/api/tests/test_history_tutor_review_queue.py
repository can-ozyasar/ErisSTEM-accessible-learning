from app.pipeline.history_tutor_review_queue import build_queue


def test_queue_is_unapproved_filters_and_respects_source_topics():
    index = {'source_checksum':'e'*64, 'sections':[{'id':'1.1','title':'Geçmiş Toplum'}],
             'chunks':[{'id':'s1','section_id':'1.1','section_title':'Geçmiş Toplum','page':3,'bbox':[0, 0, 10, 10],
                        'text':'Toplum geçmiş bilgisini ve ortak hafızayı inceler.'}]}
    question = {'id':'q1','source':{'page':1},'parts':[{'text':'Toplum geçmiş bilgisini nasıl inceler?'}],
                'choices':[], 'visuals':[], 'answer_label':'A', 'answer_source_checked':True}
    book = {'source_checksum':'q'*64, 'page_contexts':{1:{'topic':'Geçmiş Toplum'}},
            'questions':[{'question':question,'issues':[]}]}
    result = build_queue(book,index)
    case = result['cases'][0]
    assert case['review_status'] == 'pending'
    assert case['candidate_source_ids'] == ['s1'] and case['relevant_source_ids'] == []
    assert 'answer_label' not in case['question'] and not case['source_facts_checked']
    book['questions'][0]['issues'] = ['needs_review']
    assert not build_queue(book,index)['cases']
