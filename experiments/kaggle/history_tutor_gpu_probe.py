"""Private Kaggle feasibility probe. Synthetic input only; no product-quality claims."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

OUT = Path('/kaggle/working/tutor_probe_report.json')
MODEL = 'Qwen/Qwen3.5-9B'
REVISION = os.environ.get('TUTOR_MODEL_REVISION', 'c202236235762e1c871ad0ccb60c8ee5ba337b9a')
report = {'model': MODEL, 'requested_revision': REVISION, 'synthetic_only': True,
          'status': 'started', 'stages': {}, 'python': platform.python_version()}

def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

def stage(name, function):
    started = time.monotonic()
    try:
        result = function()
        report['stages'][name] = {'status': 'ok', 'seconds': round(time.monotonic() - started, 2), **(result or {})}
        save()
        return True
    except Exception as exc:
        report['stages'][name] = {'status': 'failed', 'seconds': round(time.monotonic() - started, 2),
                                  'error_type': type(exc).__name__, 'error': str(exc)[:1200]}
        traceback.print_exc()
        save()
        return False

save()
if not stage('install', lambda: (subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
        'transformers==5.3.0', 'accelerate==1.12.0', 'peft==0.18.1', 'bitsandbytes==0.49.2'], check=True), {})[1]):
    report['status'] = 'install_failed'; save(); sys.exit(1)

import torch
import transformers, accelerate, peft, bitsandbytes
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

report['versions'] = {'torch': torch.__version__, 'transformers': transformers.__version__,
                      'accelerate': accelerate.__version__, 'peft': peft.__version__,
                      'bitsandbytes': bitsandbytes.__version__, 'cuda': torch.version.cuda}
report['gpus'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
save()
if not torch.cuda.is_available():
    report['status'] = 'no_gpu'; save(); sys.exit(1)

processor = model = None

def load():
    global processor, model
    processor = AutoProcessor.from_pretrained(MODEL, revision=REVISION)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    torch.cuda.reset_peak_memory_stats()
    model = AutoModelForImageTextToText.from_pretrained(MODEL, revision=REVISION,
        quantization_config=quant, device_map={'': 0}, dtype=torch.float16)
    return {'peak_gib': round(torch.cuda.max_memory_allocated()/2**30, 3),
            'resolved_revision': getattr(model.config, '_commit_hash', None)}

if not stage('load_4bit', load):
    report['status'] = 'load_failed'; save(); sys.exit(1)

messages = [{'role': 'user', 'content': [{'type': 'text', 'text':
    'Öğrenciye kısa bir ipucu ver: ortak hafıza toplumsal kimliği destekler. Cevabı söyleme.'}]}]
inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                        return_dict=True, return_tensors='pt').to('cuda:0')

def infer():
    torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize(); started = time.monotonic()
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=64, do_sample=False)
    torch.cuda.synchronize()
    count = generated.shape[-1] - inputs['input_ids'].shape[-1]
    elapsed = time.monotonic() - started
    return {'input_tokens': inputs['input_ids'].shape[-1], 'output_tokens': count,
            'tokens_per_second': round(count / max(elapsed, .001), 2),
            'peak_gib': round(torch.cuda.max_memory_allocated()/2**30, 3)}

stage('inference', infer)

def train_step():
    global model
    model.config.use_cache = False
    # PEFT's generic helper upcasts the large unquantized embedding to fp32,
    # exceeding one T4. Freeze the base and checkpoint without that upcast.
    for parameter in model.parameters():
        parameter.requires_grad = False
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'], task_type='CAUSAL_LM'))
    model.train()
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=1e-4)
    torch.cuda.reset_peak_memory_stats()
    out = model(**inputs, labels=inputs['input_ids'])
    out.loss.backward(); optimizer.step(); optimizer.zero_grad(set_to_none=True)
    torch.cuda.synchronize()
    adapter = Path('/kaggle/working/probe-adapter')
    model.save_pretrained(adapter)
    return {'loss': float(out.loss.detach().cpu()), 'peak_gib': round(torch.cuda.max_memory_allocated()/2**30, 3),
            'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad),
            'note': 'Synthetic smoke test, loss is not a quality metric; adapter is not trained for use.'}

stage('training_step', train_step)
report['status'] = 'completed' if all(x['status'] == 'ok' for x in report['stages'].values()) else 'partial'
save()
print(json.dumps(report, ensure_ascii=False, indent=2))
