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

OUT = Path('/kaggle/working/tutor_qwen14b_report.json')
MODEL = 'Qwen/Qwen3-14B'
REVISION = os.environ.get('TUTOR_MODEL_REVISION', '40c069824f4251a91eefaf281ebe4c544efd3e18')
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
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, PeftModel, get_peft_model

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
    processor = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    torch.cuda.reset_peak_memory_stats()
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION,
        quantization_config=quant, device_map={'': 0}, dtype=torch.float16)
    return {'peak_gib': round(torch.cuda.max_memory_allocated()/2**30, 3),
            'resolved_revision': getattr(model.config, '_commit_hash', None)}

if not stage('load_4bit', load):
    report['status'] = 'load_failed'; save(); sys.exit(1)

messages = [{'role': 'user', 'content': 'Öğrenciye kısa bir ipucu ver: ortak hafıza toplumsal kimliği destekler. Cevabı söyleme.'}]
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
    for parameter in model.parameters():
        parameter.requires_grad = False
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'], task_type='CAUSAL_LM'))
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=1e-4)
    examples = [
        ('Ortak hafıza toplumsal kimliği destekler. İpucu ver.', 'Ortak hafıza ile toplumsal kimlik arasındaki ilişkiyi düşünür müsün?'),
        ('Tarım yerleşik yaşamı destekledi. İpucu ver.', 'Tarımın sürekli üretim gerektirmesi yerleşmeyi nasıl etkiler?'),
        ('Kanıt yok. İpucu ver.', 'Yeterli kaynak bulunamadı; soru kökünü birlikte inceleyelim.')]
    torch.cuda.reset_peak_memory_stats()
    losses, grad_norms, counts = [], [], []
    model.train()
    for prompt, answer in examples:
        prefix = [{'role': 'user', 'content': prompt}]
        full = prefix + [{'role': 'assistant', 'content': answer}]
        a = processor.apply_chat_template(prefix, tokenize=True, add_generation_prompt=True,
                                          return_dict=True, return_tensors='pt', enable_thinking=False).to('cuda:0')
        b = processor.apply_chat_template(full, tokenize=True, add_generation_prompt=False,
                                          return_dict=True, return_tensors='pt', enable_thinking=False).to('cuda:0')
        prefix_ids, ids = a['input_ids'][0], b['input_ids'][0]
        if len(ids) <= len(prefix_ids) or not torch.equal(ids[:len(prefix_ids)], prefix_ids):
            raise ValueError('Completion prefix mismatch or empty target')
        labels = b['input_ids'].clone(); labels[:, :len(prefix_ids)] = -100
        optimizer.zero_grad(set_to_none=True)
        out = model(**b, labels=labels)
        if not torch.isfinite(out.loss): raise ValueError('Non-finite loss')
        out.loss.backward()
        gradients = [p.grad for p in trainable if p.grad is not None]
        nonfinite = sum(not torch.isfinite(g).all().item() for g in gradients)
        if not gradients or nonfinite:
            raise ValueError(f'gradients={len(gradients)} nonfinite={nonfinite} trainable={len(trainable)}')
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        if not torch.isfinite(norm) or norm.item() <= 0: raise ValueError('Invalid gradient norm')
        optimizer.step()
        if any(not torch.isfinite(p).all().item() for p in trainable): raise ValueError('Non-finite weights')
        losses.append(float(out.loss.detach().cpu())); grad_norms.append(float(norm.detach().cpu()))
        counts.append({'input': int(ids.numel()), 'target': int((labels != -100).sum())})
    torch.cuda.synchronize()
    adapter = Path('/kaggle/working/qwen14b-probe-adapter')
    model.save_pretrained(adapter)
    return {'losses': losses, 'gradient_norms': grad_norms, 'tokens': counts,
            'peak_gib': round(torch.cuda.max_memory_allocated()/2**30, 3),
            'trainable_parameters': sum(p.numel() for p in trainable),
            'note': 'Three synthetic examples; not a quality metric or usable adapter.'}

if stage('training_steps', train_step):
    def reload_adapter():
        global model
        model = model.unload()
        model = PeftModel.from_pretrained(model, '/kaggle/working/qwen14b-probe-adapter', is_trainable=False)
        model.eval()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=16, do_sample=False)
        return {'output_tokens': int(generated.shape[-1] - inputs['input_ids'].shape[-1])}
    stage('reload_and_inference', reload_adapter)

report['status'] = 'completed' if all(x['status'] == 'ok' for x in report['stages'].values()) else 'partial'
save()
print(json.dumps(report, ensure_ascii=False, indent=2))
