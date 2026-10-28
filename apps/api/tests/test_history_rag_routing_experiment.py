from copy import deepcopy
import hashlib
import pytest

from app.pipeline.history_rag_paired_review import canonical
from app.pipeline.history_rag_routing_experiment import rank, score


def test_quality_penalty_changes_ranking_without_rewriting_or_approval():
    index={'sections':[{'id':'1.1','title':'Deneme Bölümü'}]}
    chunks=[{'id':'bad','section_id':'1.1','page':1,'text':'Ticaret yolları ticaret yolları ticaret yolları',
             'review_flags':['rubrik_kontrolu']},
            {'id':'good','section_id':'1.1','page':2,'text':'Ticaret yolları gelişmiştir.','review_flags':[]}]
    ranks, route=rank(index,chunks,'Deneme Bölümü','Ticaret yolları')
    assert ranks['topic'][0]['id']=='bad'
    assert ranks['quality'][0]['id']=='good'
    assert route['switched'] is False and chunks[0]['text'].startswith('Ticaret')


def test_unknown_topic_never_silently_searches_entire_book():
    index={'sections':[{'id':'1.1','title':'Deneme Bölümü'}]}
    ranks,route=rank(index,[], 'Bilinmeyen','Soru metni')
    assert all(not rows for rows in ranks.values())
    assert route['proposed_section'] is None


def test_review_integrity_and_uncertain_labels():
    e={'evidence_id':'e','page':1,'bbox':[0,0,1,1],'text':'Metin.', 'segments':[],
       'source_attributions':[],'label':None,'reviewer':None,'source_checked':False}
    sample={'schema':'history-rag-routing-review-v1','question_source_checksum':'a','evidence_source_checksum':'b',
            'seed':1,'k':3,'excluded_question_ids':[],'eligible_section_counts':{'1.1':1},
            'cases':[{'question':{'id':'q'},'topic':'Konu','section_id':'1.1','question_source_checked':False,
                      'question_reviewer':None,'evidence':[e]}]}
    mapping={'sample_sha256':hashlib.sha256(canonical(sample).encode()).hexdigest(),
             'cases':[{'question_id':'q','ranks':{key:['e'] for key in ('topic','quality','routing_quality')},
                       'routing':{'switched':False}}]}
    review=deepcopy(sample); c=review['cases'][0]; c.update(question_source_checked=True,question_reviewer='ai')
    c['evidence'][0].update(label='uncertain',reviewer='ai',source_checked=True)
    result=score(sample,mapping,review)
    assert result['scores']['topic']['uncertain']==1
    c['evidence'][0]['text']='Farklı'
    with pytest.raises(ValueError,match='evidence changed'):score(sample,mapping,review)
