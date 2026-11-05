from app.pipeline.source_structure_audit import page_signals


def test_page_structure_audit_routes_dense_grid_to_visual_review():
    blocks = [{"text": f"Kısa bilgi maddesi {index} için tarihsel açıklama ayrıntılı biçimde yapılmıştır.",
               "bbox": [20 + index * 30, 100 + index * 18, 180, 114], "layout": {}}
              for index in range(5)]
    result = page_signals(blocks, page_height=800, drawing_count=0)
    assert result["grid_or_diagram_review_required"] is True
    assert result["short_atom_candidate_count"] >= 1


def test_page_structure_audit_does_not_mark_ordinary_prose_as_visual_structure():
    blocks = [{"text": "Bu paragraf, tarihsel bir gelişmenin nedenlerini ve sonuçlarını açıklamak için yeterince uzun yazılmıştır.",
               "bbox": [40, 120, 450, 160], "layout": {}}]
    result = page_signals(blocks, page_height=800, drawing_count=0)
    assert result["grid_or_diagram_review_required"] is False
