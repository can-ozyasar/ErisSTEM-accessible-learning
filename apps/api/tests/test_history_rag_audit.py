import copy
import pytest
from app.pipeline.history_rag_audit import create_sample, evaluate


def index():
    return {'source_checksum':'a'*64,'chunks':[
        {'id':'a','section_id':'1','page':1,'bbox':[0,0,1,1],'text':'III. Adım: Bir etkinlik'},
        {'id':'b','section_id':'1','page':2,'bbox':[0,0,1,1],'text':'Tarım yerleşik hayatı destekledi.'},
        {'id':'c','section_id':'2','page':3,'bbox':[0,0,1,1],'text':'Farklı ders bilgisi.'}]}

def test_deterministic_blind_and_incomplete_report():
    sample=create_sample(index(), 1, 123)
    assert sample == create_sample(index(), 1, 123)
    assert len(sample['items']) == 2
    assert all('warnings' not in item and item['label'] is None for item in sample['items'])
    result=evaluate(index(),sample)
    assert result['labeled'] == 0 and result['precision_on_labeled'] is None and not result['complete']

def test_labels_are_validated_and_metrics_calculated():
    sample=create_sample(index(), 5, 123)
    for item in sample['items']:
        item.update(label='activity' if item['chunk_id']=='a' else 'lesson_fact', reviewer='teacher', source_checked=True)
    result=evaluate(index(),sample)
    assert result['complete'] and result['precision_on_labeled']==1 and result['recall_on_labeled']==1
    changed=copy.deepcopy(sample); changed['items'][0]['text']='tampered'
    with pytest.raises(ValueError, match='content changed'): evaluate(index(),changed)
    changed=copy.deepcopy(sample); changed['items'][0]['source_checked']=False
    with pytest.raises(ValueError, match='source check'): evaluate(index(),changed)
    changed=copy.deepcopy(sample); changed['items'][0]=changed['items'][1]
    with pytest.raises(ValueError, match='duplicate'): evaluate(index(),changed)
