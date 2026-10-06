"""Safely adapt model-generated table markup into the strict visual table schema.

Markup is treated as untrusted transport data, never as HTML for a browser. The
adapter extracts only text from td/th nodes and then validates the result with
the Pydantic schema used by downstream review/publishing code.
"""

from __future__ import annotations

from html.parser import HTMLParser

from .visual_result_schema import SourceRegion, VisualTableDraft

MAX_MARKUP_CHARS = 200_000


class TableMarkupError(ValueError):
    """Raised for malformed, unsupported, or non-table model output."""


class _TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str]]] = []
        self._current_row: list[tuple[str, str]] | None = None
        self._current_cell: list[str] | None = None
        self._current_role: str | None = None
        self._table_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_depth += 1
        elif tag == "tr" and self._table_depth == 1:
            if self._current_row is not None:
                raise TableMarkupError("nested table row is not supported")
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None and self._current_cell is None:
            self._current_cell = []
            self._current_role = "header" if tag == "th" else "data"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            text = " ".join("".join(self._current_cell).split())
            self._current_row.append((self._current_role or "unknown", text))
            self._current_cell, self._current_role = None, None
        elif tag == "tr" and self._current_row is not None:
            if self._current_cell is not None:
                raise TableMarkupError("unclosed table cell")
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def close(self) -> None:
        super().close()
        if self._table_depth or self._current_row is not None or self._current_cell is not None:
            raise TableMarkupError("unclosed table markup")


def adapt_table_markup(markup: str, source: SourceRegion, confidence: float) -> VisualTableDraft:
    """Parse simple table markup as data and return a schema-validated draft."""
    if not markup or len(markup) > MAX_MARKUP_CHARS:
        raise TableMarkupError("table markup length is invalid")
    parser = _TableTextParser()
    try:
        parser.feed(markup)
        parser.close()
    except TableMarkupError:
        raise
    except Exception as exc:  # HTMLParser may raise implementation-specific errors.
        raise TableMarkupError("table markup could not be parsed") from exc
    if not parser.rows:
        raise TableMarkupError("no table cells found")
    cells = [
        {"row": row_index, "column": column_index, "role": role, "text": text, "confidence": confidence}
        for row_index, row in enumerate(parser.rows, start=1)
        for column_index, (role, text) in enumerate(row, start=1)
    ]
    return VisualTableDraft.model_validate(
        {"kind": "table", "source": source.model_dump(), "cells": cells, "confidence": confidence}
    )
