"""Private development experiment selecting an existing PDF sentence by ID."""
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
INPUT=Path('/kaggle/input/datasets/muhammedcanozyasar/history-rag-extractive-selection-input-v1/input.json')
EXPECTED='5aea8bb523e7603a73ee8bceaf7b9ee2f615191afd420823e7947c5fe8f9a9f8'
OUT=Path('/kaggle/working/history_rag_extractive_raw.json')
MODEL='Qwen/Qwen3-14B';REV='40c069824f4251a91eefaf281ebe4c544efd3e18'
r={'schema':'history-rag-extractive-raw-v1','status':'started','model':MODEL,'revision':REV,'cases':[]}
def save():OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
save()
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','transformers==5.3.0','accelerate==1.12.0','bitsandbytes==0.49.2'],check=True)
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 raw=INPUT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('input mismatch')
 obj=json.loads(raw)
 if obj.get('schema')!='history-rag-extractive-selection-input-v1' or not torch.cuda.is_available():raise ValueError('bad input or GPU')
 r['input_sha256']=hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 tok=AutoTokenizer.from_pretrained(MODEL,revision=REV)
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
 model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,quantization_config=quant,device_map={'':0},dtype=torch.float16).eval()
 r['gpu']=torch.cuda.get_device_name(0);r['resolved_revision']=getattr(model.config,'_commit_hash',None);save()
 for c in obj['cases']:
  if not c['sentences']:
   r['cases'].append({'case_id':c['case_id'],'result':{'decision':'no_evidence'}});save();continue
  q=c['question'];question='\n'.join(p['text'] for p in q['parts']);choices='\n'.join(f"{x['label']}) {x['text']}" for x in q['choices'])
  source='\n'.join(f"[{s['sentence_id']}] {s['text']}" for s in c['sentences'])
  prompt=('Gösterilen kaynak cümlelerinden biri tek bir cevap seçeneğini doğrudan destekliyorsa sadece o cümlenin kimliğini kullanarak cevap ver. Kendi bilgini kanıt sayma. Kaynak yetersiz veya belirsizse sadece {"decision":"insufficient"} yaz. '
  'Yeterliyse sadece şu JSON biçimini kullan: {"decision":"sufficient","answer_label":"A","sentence_id":"cümle kimliği","explanation":"yalnız kaynağın desteklediği kısa açıklama"}. Kimliği aynen kopyala; açıklamada kaynakta bulunmayan bilgi ekleme.\n\nSORU:\n'+question+'\n'+choices+'\n\nKAYNAK CÜMLELERİ:\n'+source)
  enc=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
  start=time.monotonic()
  with torch.inference_mode(): gen=model.generate(**enc,max_new_tokens=220,do_sample=False)
  text=tok.decode(gen[0,enc['input_ids'].shape[1]:],skip_special_tokens=True).strip()
  try:result=json.loads(text)
  except (ValueError,TypeError):result=None
  r['cases'].append({'case_id':c['case_id'],'result':result,'raw_output':text,'input_tokens':int(enc['input_ids'].shape[1]),'seconds':round(time.monotonic()-start,3)});save()
 r['status']='complete';save()
except Exception as e:
 r['status']='failed';r['error_type']=type(e).__name__;r['error']=str(e)[:500];save();traceback.print_exc();sys.exit(1)
