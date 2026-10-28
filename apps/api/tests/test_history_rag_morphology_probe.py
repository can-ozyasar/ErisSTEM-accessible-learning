from app.pipeline.history_rag_morphology_probe import normalize_words, retrieve_plural_probe


def test_plural_probe_recovers_variant_without_modifying_stored_text():
    index={'sections':[{'id':'1.1','title':'Eski Çağ'}],
           'chunks':[{'id':'a','section_id':'1.1','page':1,'text':'Babil kenti tarihi.'}]}
    assert normalize_words('Babiller') == ['babil']
    assert retrieve_plural_probe(index, {'a'}, 'Eski Çağ', 'Babiller')[0]['id'] == 'a'
    assert index['chunks'][0]['text'] == 'Babil kenti tarihi.'


def test_plural_probe_does_not_bypass_approval_or_topic():
    index={'sections':[{'id':'1.1','title':'Eski Çağ'}],
           'chunks':[{'id':'a','section_id':'1.1','page':1,'text':'Babil kenti tarihi.'}]}
    assert retrieve_plural_probe(index, set(), 'Eski Çağ', 'Babiller') == []
    assert retrieve_plural_probe(index, {'a'}, 'Başka bir konu', 'Babiller') == []
