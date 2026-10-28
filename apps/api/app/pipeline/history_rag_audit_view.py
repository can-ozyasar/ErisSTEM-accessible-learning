"""Generate a self-contained local review page for an audit sample."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

HTML = '''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Kaynak kalite denetimi</title>
<style>body{font:17px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5}article{border:1px solid #bbb;padding:1rem;margin:1rem 0}label{display:block;margin:.5rem 0}select,input,button{font:inherit;padding:.35rem}textarea{width:100%;height:7em}p{white-space:pre-wrap}button{cursor:pointer}</style>
<h1>Kaynak kalite denetimi</h1><p>Bu örnekler otomatik uyarılar gösterilmeden seçildi. PDF kaynağıyla karşılaştırın. Bu sınıflandırma öğrenciye yayın veya kaynak onayı oluşturmaz. Bitince dosyayı indirin; sayfayı yenilemeden önce de ara kayıt indirin.</p>
<label>İnceleyen adı veya kodu <input id="reviewer" maxlength="100"></label><p id="progress"></p><button id="export">İncelemeyi JSON olarak indir</button><main id="items"></main>
<script>const sample=__DATA__; const main=document.getElementById('items'); const reviewer=document.getElementById('reviewer');
reviewer.value=sample.items.find(x=>x.label && x.reviewer)?.reviewer||'';
const names={'':'İncelenmedi','lesson_fact':'Ders bilgisi','activity':'Etkinlik / yönerge','caption':'Görsel veya tablo açıklaması','incomplete':'Eksik bağlam / bölünmüş','extraction_error':'Metin çıkarma hatası','other':'Diğer / uygun değil'};
function progress(){document.getElementById('progress').textContent=sample.items.filter(x=>x.label!==null && x.source_checked).length+' / '+sample.items.length+' parça işaretlendi.'}
for (const [i,x] of sample.items.entries()) {const a=document.createElement('article'); const h=document.createElement('h2'); h.textContent=(i+1)+'. Bölüm '+x.section_id+' · PDF sayfası '+x.page; a.append(h);
const p=document.createElement('p');p.textContent=x.text;a.append(p);const id=document.createElement('small');id.textContent='Parça: '+x.chunk_id;a.append(id);
const l=document.createElement('label');l.textContent='Tür ';const s=document.createElement('select');for(const [v,n] of Object.entries(names)){const o=document.createElement('option');o.value=v;o.textContent=n;s.append(o)} s.value=x.label||'';l.append(s);a.append(l);
const checkLabel=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.checked=x.source_checked===true;checkLabel.append(box,document.createTextNode(' PDF ile karşılaştırdım'));a.append(checkLabel);
s.onchange=()=>{x.label=s.value||null;if(!x.label){box.checked=false;x.source_checked=false;x.reviewer=null}progress()};box.onchange=()=>{x.source_checked=box.checked;progress()};main.append(a)}
document.getElementById('export').onclick=()=>{const who=reviewer.value.trim();if(sample.items.some(x=>x.label!==null&&(!x.source_checked||!who))){alert('Etiketlenen her parça için kaynak kontrolünü ve inceleyen kodunu girin.');return} for(const x of sample.items){x.reviewer=x.label?who:null}
const blob=new Blob([JSON.stringify(sample,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='history-rag-reviewed.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};progress();</script></html>'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--sample',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    private=(Path(__file__).resolve().parents[4]/'data/private').resolve(); source=a.sample.resolve();target=a.output.resolve()
    if not source.is_relative_to(private) or not target.is_relative_to(private): raise ValueError('paths must be inside data/private')
    sample=json.loads(source.read_text(encoding='utf-8'))
    if sample.get('schema') not in {'history-rag-blind-audit-v1', 'history-rag-holdout-v1'}: raise ValueError('invalid schema')
    data=json.dumps(sample,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    target.parent.mkdir(parents=True,exist_ok=True);fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(HTML.replace('__DATA__',data))
    print('Local audit view created; no approvals changed.')

if __name__=='__main__':main()
