from app.pipeline.history_rag_candidate_experiment import candidate


class Page:
    def __init__(self, blocks):
        self.blocks = blocks

    def get_text(self, kind):
        return {'blocks': [{'type': 0, 'bbox': box, 'lines': [
            {'bbox': box, 'spans': [{'text': text}]}]} for box, text in self.blocks]}


def test_quote_continuation_and_citation_keep_separate_source_regions():
    page = Page([([0, 0, 100, 10], '“İlk paragraf başlıyor.'),
                 ([0, 12, 100, 22], 'İkinci paragraf sona eriyor.”'),
                 ([40, 21, 100, 30], 'Yazar, 2020, s. 12.')])
    item = {'chunk_id': 'old', 'section_id': '1.1', 'page': 1,
            'bbox': [0, 0, 100, 10], 'text': '“İlk paragraf başlıyor.'}
    result = candidate(item, page, 'abc')
    assert [s['text'] for s in result['segments']] == ['“İlk paragraf başlıyor.', 'İkinci paragraf sona eriyor.”']
    assert result['source_attributions'][0]['text'] == 'Yazar, 2020, s. 12.'
    assert result['original_id'] == 'old' and result['id'] != 'old'
    assert result['review_status'] == 'experimental_unapproved'


def test_ambiguous_adjacent_blocks_are_not_joined():
    page = Page([([0, 0, 100, 10], 'Parça eksik'),
                 ([0, 12, 100, 20], 'devamı olabilir.'),
                 ([0, 12, 100, 20], 'başka bir metin.')])
    item = {'id': 'old', 'section_id': '1.1', 'page': 1,
            'bbox': [0, 0, 100, 10], 'text': 'Parça eksik'}
    assert len(candidate(item, page, 'abc')['segments']) == 1
