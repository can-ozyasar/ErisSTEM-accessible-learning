from copy import deepcopy
import hashlib

import pymupdf
import pytest

from app.history_rag import _clean
from app.pipeline.history_rag_coverage_audit import sample_omissions, evaluate_omissions


def test_omitted_sample_excludes_indexed_blocks_and_checks_integrity():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((50, 80), 'This is an indexed text block with more than forty characters.')
    page.insert_text((50, 180), 'This is a separate omitted text block with more than forty characters.')
    block = page.get_text('dict')['blocks'][0]
    box = [round(float(n), 2) for n in block['bbox']]
    text = _clean(' '.join(''.join(span['text'] for span in line['spans']) for line in block['lines']))
    identity = hashlib.sha256(f'abc:1:{box}:{text}'.encode()).hexdigest()[:20]
    index = {'source_checksum': 'abc', 'chunks': [{'id': identity}],
             'sections': [{'id': '1.1', 'start': 1, 'end': 1}]}
    sample = sample_omissions(pdf, index)
    assert len(sample['items']) == 1
    assert sample['items'][0]['chunk_id'] != identity
    assert evaluate_omissions(pdf, index, sample)['labeled'] == 0
    changed = deepcopy(sample)
    changed['items'][0]['text'] = 'tampered'
    with pytest.raises(ValueError, match='content changed'):
        evaluate_omissions(pdf, index, changed)
    sample['items'][0].update(label='useful', reviewer='test', source_checked=True)
    assert evaluate_omissions(pdf, index, sample)['labels'] == {'useful': 1}
    pdf.close()
