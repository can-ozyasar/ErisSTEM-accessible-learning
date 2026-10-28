"""Private development-only model judge; no expert labels are uploaded."""
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
INPUT=Path('/kaggle/input/datasets/muhammedcanozyasar/history-rag-semantic-judge-input-v1/input.json')
EXPECTED='74faaaf230c35f1ffdabc35fa953bc1aeb2d4a21c81a102565ab5ce9cab28554'
MODEL='Qwen/Qwen3-14B';REV='40c069824f4251a91eefaf281ebe4c544efd3e18'
OUT=Path('/kaggle/working/history_rag_semantic_judge_raw.json')
r={'schema':'history-rag-semantic-judge-raw-v1','status':'started','model':MODEL,'revision':REV,'cases':[]}
def save():OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
save()
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','transformers==5.3.0','accelerate==1.12.0','bitsandbytes==0.49.2'],check=True)
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 raw=INPUT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('file checksum mismatch')
 obj=json.loads(raw)
 if obj.get('schema')!='history-rag-semantic-judge-input-v1' or not torch.cuda.is_available():raise ValueError('invalid input or GPU unavailable')
 r['input_sha256']=hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 tok=AutoTokenizer.from_pretrained(MODEL,revision=REV)
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
 model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,quantization_config=quant,device_map={'':0},dtype=torch.float16).eval()
 r['gpu']=torch.cuda.get_device_name(0);r['resolved_revision']=getattr(model.config,'_commit_hash',None);save()
 for c in obj['cases']:
  q=c['question']; question='\n'.join(p['text'] for p in q['parts']);choices='\n'.join(f"{x['label']}) {x['text']}" for x in q['choices'])
  prompt=('Bir yanıtı bağımsızca kaynak bakımından denetle. Aşağıda yalnız tek kaynak verilmiştir. Soru metni ve model açıklamasındaki iddiaları kaynak kanıtı sayma; kendi tarih bilgini kanıt sayma. '
          'Üç ayrı soruyu yanıtla: (1) explanation ifadesi işaretlenen seçeneğin kendisiyle tutarlı mı? (2) bu kaynak seçeneği sorunun cevabı olarak destekliyor mu? (3) explanation içindeki tarihsel iddiaların tamamı bu kaynak tarafından destekleniyor mu? '
          'Destek yoksa no, emin değilsen uncertain yaz. Yalnız JSON üret: {"choice_consistent":"yes","answer_supported":"no","explanation_supported":"uncertain"}. Her değer yes, no veya uncertain olmalı.\n\n'
          +'SORU:\n'+question+'\n'+choices+'\n\nSEÇİLEN SEÇENEK: '+c['answer_label']+'\nAÇIKLAMA: '+c['explanation']+'\n\nKAYNAK:\n'+c['cited_evidence']['text']+'\nALINTI: '+c['citation']['quote'])
  enc=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
  start=time.monotonic()
  with torch.inference_mode():generated=model.generate(**enc,max_new_tokens=120,do_sample=False)
  text=tok.decode(generated[0,enc['input_ids'].shape[1]:],skip_special_tokens=True).strip()
  try: result=json.loads(text)
  except (TypeError,ValueError):result=None
  r['cases'].append({'case_id':c['case_id'],'checks':result,'raw_output':text,'seconds':round(time.monotonic()-start,3)});save()
 r['status']='complete';save()
except Exception as e:
 r['status']='failed';r['error_type']=type(e).__name__;r['error']=str(e)[:500];save();traceback.print_exc();sys.exit(1)
