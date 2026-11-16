import pytest

from app.pipeline.history_rag_layout_audit import analyze, holdout


class Page:
    def __init__(self, lines):
        self.lines = lines

    def get_text(self, kind):
        return {'blocks': [{'type': 0, 'lines': [
            {'bbox': [0, i * 10, 100, i * 10 + 9], 'spans': [{'text': line}]}
            for i, line in enumerate(self.lines)]}]}


def test_soft_hyphen_reconstruction_preserves_visible_hyphens():
    item = {'id': 'a', 'page': 1, 'bbox': [0, 0, 100, 30],
            'text': 'Tür kistan ve Perge-Side bölgesi.'}
    result = analyze(item, Page(['Tür\xad', 'kistan ve Perge-Side', 'bölgesi.']))
    assert 'satir_sonu_tire_kontrolu' in result['flags']
    assert result['proposed_soft_hyphen_text'] == 'Türkistan ve Perge-Side bölgesi.'
    assert item['text'] == 'Tür kistan ve Perge-Side bölgesi.'


def test_does_not_propose_reconstruction_if_source_text_does_not_match():
    item = {'id': 'a', 'page': 1, 'bbox': [0, 0, 100, 20], 'text': 'Farklı içerik.'}
    result = analyze(item, Page(['Tür\xad', 'kistan']))
    assert result['proposed_soft_hyphen_text'] is None


def test_chunk_boundary_and_activity_are_review_flags():
    item = {'id': 'a', 'page': 1, 'bbox': [0, 0, 100, 10],
            'text': 'bu etkinlik için hazırlık'}
    result = analyze(item, Page([item['text']]))
    assert {'parca_siniri_kontrolu', 'etkinlik_veya_degerlendirme'} <= set(result['flags'])


def test_holdout_is_disjoint_and_deterministic():
    from app.pipeline.history_rag_audit import create_sample
    index = {'source_checksum': 'abc', 'chunks': [
        {'id': str(i), 'section_id': '1.1', 'page': i + 1,
         'bbox': [0, 0, 1, 1], 'text': 'Metin.'} for i in range(12)]}
    dev = create_sample(index, 3, 42)
    first = holdout(index, dev, 13, 5)
    assert first == holdout(index, dev, 13, 5)
    assert not {x['chunk_id'] for x in dev['items']} & {x['chunk_id'] for x in first['items']}
    assert all(x['label'] is None and not x['source_checked'] for x in first['items'])
    with pytest.raises(ValueError):
        holdout({**index, 'source_checksum': 'changed'}, dev, 13, 5)


def test_holdout_evaluation_rejects_tampering_and_handles_no_labels():
    from copy import deepcopy

    from app.pipeline.history_rag_audit import create_sample
    from app.pipeline.history_rag_layout_audit import evaluate_holdout
    index = {'source_checksum': 'abc', 'chunks': [
        {'id': str(i), 'section_id': '1.1', 'page': 1,
         'bbox': [0, 0, 100, 10], 'text': 'Metin.'} for i in range(12)]}
    dev = create_sample(index, 3, 42)
    sample = holdout(index, dev, 20261025, 5)
    result = evaluate_holdout(index, dev, sample, [Page(['Metin.'])])
    assert result['labeled'] == 0
    assert result['experimental']['recall'] is None
    altered = deepcopy(sample)
    altered['items'][0]['text'] = 'Değiştirilmiş.'
    with pytest.raises(ValueError, match='content changed'):
        evaluate_holdout(index, dev, altered, [Page(['Metin.'])])
    sample['items'][0].update(label='lesson_fact', reviewer='reviewer', source_checked=True)
    result = evaluate_holdout(index, dev, sample, [Page(['Metin.'])])
    assert result['labeled'] == 1 and result['complete'] is False


def test_rubric_and_nearby_citation_are_flagged_without_removing_content():
    item = {'id': 'a', 'page': 1, 'bbox': [0, 0, 100, 10],
            'text': 'Zihin haritası düzenli ve okunaklıdır.'}
    result = analyze(item, Page([item['text'], 'Yazar, 2021, s. 23']))
    assert {'rubrik_kontrolu', 'ayri_kaynak_atfi_kontrolu'} <= set(result['flags'])
