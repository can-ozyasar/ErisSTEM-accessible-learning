import pytest
from app.pipeline.history_rag_retrieval_probe import compare


def test_compares_same_question_and_keeps_original_identity():
    index = {'source_checksum': 'hash', 'sections': [{'id': '1.1', 'title': 'Deneme Bölümü'}],
             'chunks': [{'id': 'old', 'section_id': '1.1', 'page': 1, 'text': 'Başka içerik örneği.'}]}
    exp = {'schema': 'history-rag-experimental-candidates-v1', 'source_checksum': 'hash',
           'chunks': [{'id': 'new', 'original_id': 'target', 'section_id': '1.1', 'page': 2,
                       'text': 'Tarih kaynakları arşivlerde bulunur.'}]}
    cases = [{'topic': 'Deneme Bölümü', 'question': 'Tarih kaynakları nerede bulunur?', 'target_original_id': 'target'}]
    result = compare(index, exp, cases)
    assert not result['cases'][0]['baseline']['target_hit']
    assert result['cases'][0]['experimental']['target_hit']
    with pytest.raises(ValueError, match='source mismatch'):
        compare(index, {**exp, 'source_checksum': 'wrong'}, cases)
