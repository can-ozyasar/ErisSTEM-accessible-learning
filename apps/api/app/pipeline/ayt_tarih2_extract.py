"""Private AYT Tarih-2 candidate extraction; no answer keys or exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

from ..question_bank_extract import extract_page

YEAR = re.compile(r"\b(20(?:18|19|2[0-6]))-AYT\b")
PAGES = range(129, 150)
TARGET_YEARS = {2022, 2023, 2024, 2025, 2026}


def _year_in_question_box(labels: list[tuple[int, tuple]], box: tuple | list) -> int | None:
    """Bind a year only when its printed label is inside this question lane.

    The AYT PDF interleaves years in two columns. Vertical proximity alone can
    assign a label from the other column; containment is auditable through the
    recorded question and label coordinates.
    """
    x0, y0, x1, y1 = box
    matches = {
        year for year, (lx0, ly0, lx1, ly1) in labels
        if x0 - 2 <= (lx0 + lx1) / 2 <= x1 + 2 and y0 - 2 <= (ly0 + ly1) / 2 <= y1 + 2
    }
    return next(iter(matches)) if len(matches) == 1 else None

def build(source: Path, *, pages: range = PAGES, test: str = "Tarih-2", prefix: str = "ayt-soz-t2") -> dict:
    raw = source.read_bytes(); checksum = hashlib.sha256(raw).hexdigest(); rows=[]
    with pymupdf.open(stream=raw, filetype='pdf') as pdf:
        for page_no in pages:
            page = pdf[page_no-1]
            candidates = extract_page(page, page_no, checksum)
            labels=[]
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0: continue
                text=' '.join(''.join(s['text'] for s in line['spans']) for line in block['lines'])
                for hit in YEAR.finditer(text): labels.append((int(hit.group(1)), block['bbox']))
            for candidate in candidates:
                q=candidate['question']; box=q['source']['bbox']; year=_year_in_question_box(labels, box)
                if year in TARGET_YEARS:
                    year_status, extra_issues = 'bound', []
                elif year is None:
                    year_status, extra_issues = 'review_required', ['exam_year_review_required']
                else:
                    year_status, extra_issues = 'out_of_scope', ['outside_2022_2026_scope']
                rows.append({'candidate_id':f'{prefix}:{checksum[:12]}:{page_no}:{q["number"]}:{len(rows)}',
                  'source_kind':'official_exam_private','source_checksum':checksum,'page':page_no,'bbox':box,
                  'test':test,'exam_year':year,'year_status':year_status,
                  'issues': sorted(set(candidate['issues'] + extra_issues)),
                  'question':q})
    return {'schema':'ayt-tarih2-candidates-v1','source_checksum':checksum,'page_allowlist':list(pages),
      'candidate_count':len(rows),'candidates':rows,
      'notice':'Private teacher review only. Answers and solution pages are not parsed or exported.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--start-page',type=int,default=PAGES.start);p.add_argument('--end-page',type=int,default=PAGES.stop-1);p.add_argument('--test',default='Tarih-2');p.add_argument('--prefix',default='ayt-soz-t2');a=p.parse_args()
 if a.start_page < 1 or a.end_page < a.start_page: raise ValueError('Sayfa aralığı geçersiz')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(build(a.source,pages=range(a.start_page,a.end_page+1),test=a.test,prefix=a.prefix),ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
