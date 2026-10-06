import pytest

from app.pipeline.table_markup_adapter import TableMarkupError, adapt_table_markup
from app.pipeline.visual_result_schema import SourceRegion


def source() -> SourceRegion:
    return SourceRegion(region_id="p51-image-1-visual", source_checksum="a" * 64, page=51, bbox=(1, 2, 30, 40))


def test_adapts_untrusted_table_markup_without_exposing_html():
    result = adapt_table_markup(
        "<table><tr><th>Başlık</th><th>Değer</th></tr><tr><td>A</td><td>2</td></tr></table>",
        source(),
        0.8,
    )

    assert [(cell.role, cell.text) for cell in result.cells] == [
        ("header", "Başlık"),
        ("header", "Değer"),
        ("data", "A"),
        ("data", "2"),
    ]


def test_rejects_non_table_or_unclosed_markup():
    with pytest.raises(TableMarkupError, match="no table"):
        adapt_table_markup("<p>not a table</p>", source(), 0.8)
    with pytest.raises(TableMarkupError, match="unclosed"):
        adapt_table_markup("<table><tr><td>x", source(), 0.8)
