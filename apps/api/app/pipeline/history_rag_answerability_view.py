"""Create a private local expert-review page; does not change approvals."""
import argparse
import json
from pathlib import Path
from .history_rag_independent_eval import digest
from .history_rag_paired_review import write

HTML = '''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Kanıt yeterliliği incelemesi</title><style>body{font:17px system-ui;max-width:980px;margin:2em auto;padding:0 1em;line-height:1.5}article{border:1px solid #aaa;padding:1em;margin:1em 0}label{display:block;margin:1em 0}select,input,button{font:inherit}pre{white-space:pre-wrap;font:inherit}summary{cursor:pointer}</style>
<h1>Kanıt yeterliliği incelemesi · geliştirme kümesi</h1><p>Bu özel araştırma çalışmasıdır; burada işaretleme, kaynağı öğrenciye yayınlamak için onaylamaz. Her durumda sadece gösterilen kanıtları kullanarak sorunun tek seçeneğine güvenle ulaşılıp ulaşılmadığını değerlendirin. Boş kanıtlar yapay kontrol örnekleridir. Soruyu ve tüm kaynak bölgelerini PDF'de kontrol edin; emin değilseniz belirsiz seçin.</p><label>İnceleyen adınız veya kodunuz <input id="who" maxlength="100"></label><button id="export">İncelemeyi JSON olarak indir</button><p id="progress"></p><main id="items"></main>
<script>const data=__DATA__, checksum=__HASH__;const main=document.getElementById('items'),review=[];
const add=(parent,tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;parent.append(e);return e};
for(const [i,c] of data.cases.entries()){const a=add(main,'article');add(a,'h2',(i+1)+'. Soru · '+(c.kind==='empty_control'?'Boş kanıt kontrolü':'Getirilen kanıt'));let q=c.question;let link=add(a,'a','Soru PDF sayfası '+q.source.page);link.href='../../soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf#page='+q.source.page;link.target='_blank';add(a,'pre',q.parts.map(p=>p.text).join('\\n')+'\\n\\n'+q.choices.map(x=>x.label+') '+x.text).join('\\n'));if(!c.evidence.length)add(a,'p','Bu durumda gösterilen kanıt yok.');for(const [j,e] of c.evidence.entries()){let d=add(a,'details');add(d,'summary','Kanıt '+(j+1)+' · PDF sayfası '+e.page);let l=add(d,'a','Ders kitabında aç');l.href='../../meb/tarih-9sinif-ders-kitabi_20261006.pdf#page='+e.page;l.target='_blank';add(d,'pre',e.text)}let label=add(a,'label','Kanıt yeterliliği '),s=add(label,'select');for(const [v,n] of [['','Seçiniz'],['sufficient','Yeterli: gösterilen kanıt tek doğru seçeneği destekliyor'],['insufficient','Yetersiz: gösterilen kanıtla güvenli cevap verilemiyor'],['uncertain','Belirsiz']]){let o=add(s,'option',n);o.value=v}let al=add(a,'label','Yeterliyse doğru seçenek '),ans=add(al,'select');for(const v of ['',...c.choice_labels]){let o=add(ans,'option',v||'Seçiniz');o.value=v}let check=add(a,'label'),box=add(check,'input');box.type='checkbox';check.append(' Soruyu ve gösterilen bütün kanıtları PDF ile kontrol ettim.');review.push({c,s,ans,box});}
document.getElementById('export').onclick=()=>{const who=document.getElementById('who').value.trim();if(!who||review.some(x=>!x.s.value||!x.box.checked||(x.s.value==='sufficient'&&!x.ans.value)||(x.s.value!=='sufficient'&&x.ans.value))){alert('İnceleyen kodunu, tüm değerlendirmeleri ve kaynak kontrollerini doldurun; yalnız yeterli durumlarda seçenek girin.');return}let out={bundle_sha256:checksum,cases:review.map(x=>({case_id:x.c.case_id,answerability:x.s.value,answer_label:x.ans.value||null,reviewer:who,source_checked:true}))};let u=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download='answerability-development-reviewed.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};</script></html>'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    private=(Path(__file__).resolve().parents[4]/'data/private').resolve()
    if not a.bundle.resolve().is_relative_to(private) or not a.output.resolve().is_relative_to(private): raise ValueError('private paths required')
    obj=json.loads(a.bundle.read_text());
    if obj.get('schema')!='history-rag-answerability-bundle-v1' or obj.get('split')!='development':raise ValueError('development bundle required')
    data=json.dumps(obj,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as out:out.write(HTML.replace('__DATA__',data).replace('__HASH__',json.dumps(digest(obj))))
    a.output.chmod(0o600); print('Private review page created; no source approval changed.')

if __name__=='__main__':main()
