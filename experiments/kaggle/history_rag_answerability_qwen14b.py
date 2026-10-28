"""Private development-only grounded-answer and abstention probe. No labels uploaded."""
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
INPUT=Path('/kaggle/input/datasets/muhammedcanozyasar/history-rag-answerability-input-v1/input.json')
EXPECTED='783ceb43cdce98d9a7eb55df1f34aa8e4fdbc313acb004e206ae068a05e97832'
OUT=Path('/kaggle/working/history_rag_answerability_predictions.json')
MODEL='Qwen/Qwen3-14B'; REV='40c069824f4251a91eefaf281ebe4c544efd3e18'
r={'schema':'history-rag-answerability-predictions-v1','status':'started','input_sha256':EXPECTED,'model':MODEL,'revision':REV,'cases':[]}
def save():OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2))
save()
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','transformers==5.3.0','accelerate==1.12.0','bitsandbytes==0.49.2'],check=True)
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 if not torch.cuda.is_available():raise RuntimeError('GPU unavailable')
 raw=INPUT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('input checksum mismatch')
 bundle=json.loads(raw)
 if bundle.get('schema')!='history-rag-answerability-bundle-v1' or bundle.get('split')!='development':raise ValueError('unexpected bundle')
 r['bundle_sha256']=hashlib.sha256(json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 tok=AutoTokenizer.from_pretrained(MODEL,revision=REV)
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
 model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,quantization_config=quant,device_map={'':0},dtype=torch.float16).eval()
 r['gpu']=torch.cuda.get_device_name(0);r['resolved_revision']=getattr(model.config,'_commit_hash',None);save()
 for c in bundle['cases']:
  q=c['question'];question='\n'.join(p['text'] for p in q['parts']);choices='\n'.join(f"{x['label']}) {x['text']}" for x in q['choices']);evidence='\n\n'.join(f"[{i+1}] {e['text']}" for i,e in enumerate(c['evidence'])) or '(kaynak yok)'
  prompt=('Sadece verilen kaynakların sorudaki tek doğru seçeneği desteklediği durumlarda cevap ver. '
          'Soru kökündeki bilgilere dayanabilirsin ama dış kaynak yetersizse kendi bilgine güvenme ve çekimser kal. '
          'Yanıtın yalnızca şu JSON biçiminde olsun: {"action":"answer","answer_label":"A"} '
          'veya {"action":"abstain","answer_label":null}.\n\nSORU:\n'+question+'\n'+choices+'\n\nKAYNAKLAR:\n'+evidence)
  enc=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
  started=time.monotonic()
  with torch.inference_mode():generated=model.generate(**enc,max_new_tokens=96,do_sample=False)
  text=tok.decode(generated[0,enc['input_ids'].shape[1]:],skip_special_tokens=True).strip()
  try:
   parsed=json.loads(text);action=parsed['action'];answer=parsed['answer_label']
   if action not in ('answer','abstain') or (action=='answer' and answer not in c['choice_labels']) or (action=='abstain' and answer is not None):raise ValueError('invalid output')
   row={'case_id':c['case_id'],'action':action,'answer_label':answer}
  except (ValueError,KeyError,TypeError):row={'case_id':c['case_id'],'action':'invalid','answer_label':None}
  row['input_tokens']=int(enc['input_ids'].shape[1]);row['output_tokens']=int(generated.shape[1]-enc['input_ids'].shape[1]);row['seconds']=round(time.monotonic()-started,3)
  r['cases'].append(row);save()
 r['status']='complete' if all(x['action']!='invalid' for x in r['cases']) else 'invalid_outputs';save()
except Exception as e:
 r['status']='failed';r['error_type']=type(e).__name__;r['error']=str(e)[:500];save();traceback.print_exc();sys.exit(1)
