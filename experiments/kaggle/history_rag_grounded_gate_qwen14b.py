"""Private development probe: separate evidence gate and cited answer stages."""
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
INPUT=Path('/kaggle/input/datasets/muhammedcanozyasar/history-rag-answerability-input-v1/input.json')
EXPECTED='783ceb43cdce98d9a7eb55df1f34aa8e4fdbc313acb004e206ae068a05e97832'
OUT=Path('/kaggle/working/history_rag_grounded_gate_raw.json')
MODEL='Qwen/Qwen3-14B';REV='40c069824f4251a91eefaf281ebe4c544efd3e18'
r={'schema':'history-rag-grounded-gate-raw-v1','status':'started','input_sha256':EXPECTED,'model':MODEL,'revision':REV,'cases':[]}
def save():OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
save()
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','transformers==5.3.0','accelerate==1.12.0','bitsandbytes==0.49.2'],check=True)
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 if not torch.cuda.is_available():raise RuntimeError('GPU unavailable')
 raw=INPUT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('input checksum mismatch')
 bundle=json.loads(raw)
 if bundle.get('schema')!='history-rag-answerability-bundle-v1' or bundle.get('split')!='development':raise ValueError('invalid bundle')
 r['bundle_sha256']=hashlib.sha256(json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 tok=AutoTokenizer.from_pretrained(MODEL,revision=REV)
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
 model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,quantization_config=quant,device_map={'':0},dtype=torch.float16).eval()
 r['gpu']=torch.cuda.get_device_name(0);r['resolved_revision']=getattr(model.config,'_commit_hash',None);save()
 def run(prompt):
  enc=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
  start=time.monotonic()
  with torch.inference_mode(): generated=model.generate(**enc,max_new_tokens=220,do_sample=False)
  text=tok.decode(generated[0,enc['input_ids'].shape[1]:],skip_special_tokens=True).strip()
  try: parsed=json.loads(text)
  except (ValueError,TypeError):parsed=None
  return parsed,{'input_tokens':int(enc['input_ids'].shape[1]),'output_tokens':int(generated.shape[1]-enc['input_ids'].shape[1]),'seconds':round(time.monotonic()-start,3),'raw_output':text}
 for c in bundle['cases']:
  if not c['evidence']:
   r['cases'].append({'case_id':c['case_id'],'gate':{'decision':'no_evidence'},'answer':None});save();continue
  q=c['question'];question='\n'.join(p['text'] for p in q['parts']);choices='\n'.join(f"{x['label']}) {x['text']}" for x in q['choices']);evidence='\n\n'.join(f"[{i+1}] {e['text']}" for i,e in enumerate(c['evidence']))
  context='SORU:\n'+question+'\n'+choices+'\n\nKAYNAKLAR:\n'+evidence
  gate_prompt=('Sen bir kaynak yeterliliği denetçisisin. Sadece gösterilen dış kaynakların tek doğru seçeneği destekleyip desteklemediğini değerlendir. Kendi bilgini kanıt sayma. Kaynak sadece aynı konuda ise veya karar için gereken ilişkiyi söylemiyorsa yetersizdir. Kaynak yeterli değilse sadece {"decision":"insufficient"} yaz. Yeterliyse sadece {"decision":"sufficient","answer_label":"A","citation":{"source":1,"quote":"kaynaktan birebir kısa alıntı"}} biçiminde JSON yaz. source gösterilen kaynak numarasıdır. Alıntıyı metinden aynen ve en az 12 karakterle yaz.\n\n'+context)
  gate,gmeta=run(gate_prompt);answer=None;ameta=None
  if isinstance(gate,dict) and gate.get('decision')=='sufficient':
   answer_prompt=('Yalnız gösterilen kaynakları kullanarak soruya cevap ver. Kaynak tek doğru seçeneği desteklemiyorsa {"answer_label":null} yaz. Destekliyorsa yalnız JSON yaz: {"answer_label":"A","citation":{"source":1,"quote":"kaynaktan birebir kısa alıntı"},"explanation":"kısa açıklama"}. source kaynak numarasıdır. Alıntıyı aynen ve en az 12 karakter yaz.\n\n'+context)
   answer,ameta=run(answer_prompt)
  r['cases'].append({'case_id':c['case_id'],'gate':gate,'answer':answer,'gate_meta':gmeta,'answer_meta':ameta});save()
 r['status']='complete';save()
except Exception as e:
 r['status']='failed';r['error_type']=type(e).__name__;r['error']=str(e)[:500];save();traceback.print_exc();sys.exit(1)
