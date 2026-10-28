from copy import deepcopy

import pytest

from app.pipeline.history_rag_morphology_review import prepare, score


def test_morphology_review_excludes_previous_questions_and_preserves_pool(monkeypatch):
    import app.pipeline.history_rag_morphology_review as module
    question = {'id': 'new', 'parts': [{'text': 'Babiller'}], 'source': {'page': 1}}
    previous_question = {'id': 'old', 'parts': [{'text': 'Eski'}], 'source': {'page': 1}}
    book = {'source_checksum': 'q', 'questions': [{'question': question}, {'question': previous_question}]}
    index = {'source_checksum': 's', 'sections': [{'id': '1.1', 'title': 'Konu'}]}
    experimental = {'schema': 'history-rag-experimental-candidates-v1', 'source_checksum': 's',
                    'chunks': [{'id': 'a', 'section_id': '1.1', 'page': 1, 'bbox': [0, 0, 1, 1],
                                'text': 'Babil kenti', 'review_flags': []}]}
    previous = {'question_source_checksum': 'q', 'cases': [{'question': previous_question}]}
    def select(filtered, idx, per_section, seed):
        assert [item['question']['id'] for item in filtered['questions']] == ['new']
        return [{'question': question, 'topic': 'Konu', 'section_id': '1.1'}], {'1.1': 1}
    monkeypatch.setattr(module, 'select_questions', select)
    sample, mapping = prepare(book, index, experimental, [previous])
    assert sample['excluded_question_ids'] == ['old']
    reviewed = deepcopy(sample)
    case = reviewed['cases'][0]
    case.update(question_source_checked=True, question_reviewer='reviewer')
    case['evidence'][0].update(label='relevant', source_checked=True, reviewer='reviewer')
    result = score(sample, mapping, reviewed)
    assert result['scores']['quality']['questions_with_relevant'] == 1
    assert result['scores']['topic']['questions_with_relevant'] == 0
    reviewed['cases'][0]['evidence'][0]['text'] = 'altered'
    with pytest.raises(ValueError, match='evidence changed'):
        score(sample, mapping, reviewed)


def test_morphology_review_rejects_foreign_source():
    with pytest.raises(ValueError, match='experimental source mismatch'):
        prepare({'source_checksum': 'q'}, {'source_checksum': 's'},
                {'schema': 'history-rag-experimental-candidates-v1', 'source_checksum': 'different'}, [])
