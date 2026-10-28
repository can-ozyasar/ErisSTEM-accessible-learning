from copy import deepcopy
import hashlib
import pytest

from app.pipeline.history_rag_paired_review import canonical, score


def fixtures():
    evidence = {'evidence_id': 'e', 'page': 1, 'bbox': [0, 0, 1, 1], 'text': 'Metin.',
                'segments': [], 'source_attributions': [], 'label': None,
                'reviewer': None, 'source_checked': False}
    sample = {'schema': 'history-rag-paired-review-v1', 'question_source_checksum': 'q',
              'evidence_source_checksum': 's', 'seed': 1, 'per_section': 1,
              'eligible_section_counts': {'1.1': 1}, 'k': 3,
              'cases': [{'question': {'id': 'q1'}, 'section_id': '1.1', 'topic': 'Konu',
                         'question_source_checked': False, 'question_reviewer': None,
                         'evidence': [evidence]}]}
    mapping = {'sample_sha256': hashlib.sha256(canonical(sample).encode()).hexdigest(),
               'cases': [{'question_id': 'q1', 'ranks': {'baseline': ['e'], 'experimental': ['e']}}]}
    return sample, mapping


def test_scoring_requires_checked_questions_and_verified_evidence():
    sample, mapping = fixtures()
    reviewed = deepcopy(sample)
    assert score(sample, mapping, reviewed)['scores']['baseline']['questions_evaluated'] == 0
    case = reviewed['cases'][0]
    case.update(question_source_checked=True, question_reviewer='r')
    case['evidence'][0].update(label='uncertain', reviewer='r', source_checked=True)
    result = score(sample, mapping, reviewed)['scores']['baseline']
    assert result['questions_evaluated'] == 1 and result['uncertain'] == 1
    assert result['questions_with_relevant'] == 0
    case['evidence'][0]['text'] = 'Changed'
    with pytest.raises(ValueError, match='evidence changed'):
        score(sample, mapping, reviewed)


def test_scoring_rejects_invalid_mapping():
    sample, mapping = fixtures()
    mapping['cases'][0]['ranks']['baseline'] = ['foreign']
    with pytest.raises(ValueError, match='invalid mapping ranks'):
        score(sample, mapping, deepcopy(sample))
