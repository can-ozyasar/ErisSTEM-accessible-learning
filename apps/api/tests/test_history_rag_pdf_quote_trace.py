from app.pipeline.history_rag_pdf_quote_trace import make_index, trace


def line(value, n):
    return {'page':1,'segment':0,'line':n,'chars':[{'char':c,'bbox':[i,n,i+1,n+1]} for i,c in enumerate(value)]}


def test_soft_hyphen_join_has_character_level_source_and_does_not_invent_letters():
    idx=make_index([line('Doğru değer\u00ad',0),line('lendirmeye dayanır.',1)])
    assert idx['text']=='Doğru değerlendirmeye dayanır.'
    hit=trace(idx,'değerlendirmeye dayanır.')
    assert hit['status']=='matched' and len(hit['regions'])==2
    assert hit['transformations'][0]['type']=='pdf_soft_hyphen_line_break'
    assert trace(idx,'değerlendirmeye dayanırk.')['status']=='not_found'


def test_visible_hyphen_and_ambiguous_occurrences_not_silently_fixed():
    idx=make_index([line('Türk-İslam devletleri',0),line('bir örnektir.',1)])
    assert trace(idx,'Türkİslam devletleri')['status']=='not_found'
    duplicate=make_index([line('Aynı uzun cümle. Aynı uzun cümle.',0)])
    assert trace(duplicate,'Aynı uzun cümle.')['status']=='ambiguous'


def test_extract_restricts_geometry_and_rejects_noncontiguous_regions():
    import pymupdf
    import pytest
    from app.pipeline.history_rag_pdf_quote_trace import extract_lines
    pdf=pymupdf.open();page=pdf.new_page();page.insert_text((50,60),'Visible source statement.')
    page.insert_text((50,250),'Separate unrelated statement.')
    evidence={'page':1,'bbox':[45,45,230,70],'segments':[{'page':1,'bbox':[45,45,230,70]}]}
    text=make_index(extract_lines(pdf,evidence))['text']
    assert 'Visible source statement.' in text
    assert 'Separate unrelated' not in text
    evidence['segments'].append({'page':1,'bbox':[45,230,250,260]})
    with pytest.raises(ValueError):extract_lines(pdf,evidence)
