from app.history_rag import _printed_page_offset


class _Page:
    def __init__(self, text=""):
        self.text = text

    def get_text(self):
        return self.text


class _Pdf:
    def __init__(self, headings):
        self.pages = [_Page() for _ in range(40)]
        for page, heading in headings.items():
            self.pages[page - 1] = _Page(heading)
        self.page_count = len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]


def test_book_heading_evidence_calibrates_printed_page_offset():
    rows = [{"id": f"1.{i}", "title": f"Tarihsel konu {i}", "start": 16 + i * 3}
            for i in range(1, 5)]
    pdf = _Pdf({row["start"] + 1: f"{row['id']}. {row['title']}" for row in rows})
    assert _printed_page_offset(pdf, rows) == 1


def test_ambiguous_headings_cannot_shift_book():
    rows = [{"id": f"1.{i}", "title": f"Tarihsel konu {i}", "start": 16 + i * 3}
            for i in range(1, 5)]
    pdf = _Pdf({rows[0]["start"] + 1: "1.1. Tarihsel konu 1",
                rows[1]["start"] + 1: "1.2. Tarihsel konu 2",
                rows[2]["start"]: "1.3. Tarihsel konu 3",
                rows[3]["start"]: "1.4. Tarihsel konu 4"})
    assert _printed_page_offset(pdf, rows) == 0
