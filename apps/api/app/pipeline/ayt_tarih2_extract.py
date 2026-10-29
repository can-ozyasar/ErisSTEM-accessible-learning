"""Private AYT Tarih-2 candidate extraction; no answer keys or exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

from ..question_bank_extract import extract_page

YEAR = re.compile(r"\b(20(?:22|23|24|25|26))-AYT\b")
PAGES = range(129, 150)

def build(source: Path) -> dict:
    raw = source.read_bytes(); checksum = hashlib.sha256(raw).hexdigest(); rows=[]
    with pymupdf.open(stream=raw, filetype='pdf') as pdf:
        for page_no in PAGES:
            page = pdf[page_no-1]
            candidates = extract_page(page, page_no, checksum)
            labels=[]
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0: continue
                text=' '.join(''.join(s['text'] for s in line['spans']) for line in block['lines'])
                for hit in YEAR.finditer(text): labels.append((int(hit.group(1)), block['bbox']))
            for candidate in candidates:
                q=candidate['question']; box=q['source']['bbox']; near=[year for year,b in labels if abs(b[1]-box[1])<170]
                year=near[0] if len(set(near))==1 else None
                rows.append({'candidate_id':f'ayt-soz-t2:{checksum[:12]}:{page_no}:{q["number"]}:{len(rows)}',
                  'source_kind':'official_exam_private','source_checksum':checksum,'page':page_no,'bbox':box,
                  'test':'Tarih-2','exam_year':year,'year_status':'bound' if year else 'review_required',
                  'issues': sorted(set(candidate['issues']+([] if year else ['exam_year_review_required']))),
                  'question':q})
    return {'schema':'ayt-tarih2-candidates-v1','source_checksum':checksum,'page_allowlist':list(PAGES),
      'candidate_count':len(rows),'candidates':rows,
      'notice':'Private teacher review only. Answers and solution pages are not parsed or exported.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(build(a.source),ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
