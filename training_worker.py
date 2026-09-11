import json, os, time, traceback, sqlite3
from datetime import datetime, timezone

DB=os.getenv('AI3_DB','/data/ai3.db')
POLL=float(os.getenv('AI3_TRAIN_POLL_SECONDS','5'))
FORCE_DEVICE=os.getenv('AI3_TRAIN_DEVICE','auto').lower()

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB, timeout=30); c.row_factory=sqlite3.Row; return c

def update(job_id,status,progress=0,result=None):
    with db() as c:
        c.execute('UPDATE ai_training_jobs SET status=?,progress=?,result=?,updated_at=? WHERE id=?',(status,progress,json.dumps(result) if result is not None else None,now(),job_id))

def hardware(torch):
    use_gpu=FORCE_DEVICE == 'cuda' or (FORCE_DEVICE == 'auto' and torch.cuda.is_available())
    if FORCE_DEVICE == 'cpu': use_gpu=False
    if use_gpu and not torch.cuda.is_available():
        raise RuntimeError('AI3 wurde auf CUDA festgelegt, aber keine funktionierende CUDA-GPU ist verfügbar.')
    if not use_gpu:
        threads=max(1, int(os.cpu_count() or 1))
        torch.set_num_threads(threads)
    return 'cuda' if use_gpu else 'cpu'

def train(job):
    cfg=json.loads(job['config'] or '{}')
    base=job['base_model']; dataset=job['dataset_path']; method=job['method']
    out=cfg.get('output_dir') or f"/data/models/{job['model_id']}"
    os.makedirs(out,exist_ok=True)
    try:
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from peft import LoraConfig
        from trl import SFTTrainer
    except Exception as e:
        raise RuntimeError('Training-Abhängigkeiten fehlen. Installiere training/requirements.txt oder starte den AI3-Installer erneut: '+str(e))
    device=hardware(torch)
    if device != 'cuda' and method == 'qlora':
        raise RuntimeError('QLoRA benötigt aktuell eine CUDA-GPU mit funktionierendem PyTorch/BitsAndBytes. CPU-Training verwendet LoRA.')
    update(job['id'],'running',5,{'message':f'Lade Dataset und Basismodell auf {device.upper()}','device':device,'cpu_threads':torch.get_num_threads()})
    ext=os.path.splitext(dataset)[1].lower()
    if ext=='.jsonl': ds=load_dataset('json',data_files=dataset,split='train')
    elif ext=='.json': ds=load_dataset('json',data_files=dataset,split='train')
    elif ext=='.csv': ds=load_dataset('csv',data_files=dataset,split='train')
    else: ds=load_dataset('text',data_files=dataset,split='train')
    tok=AutoTokenizer.from_pretrained(base,use_fast=True)
    if tok.pad_token is None: tok.pad_token=tok.eos_token
    kwargs={'device_map':'auto'} if device=='cuda' else {}
    if method=='qlora':
        from transformers import BitsAndBytesConfig
        kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.float16,bnb_4bit_use_double_quant=True)
    model=AutoModelForCausalLM.from_pretrained(base,**kwargs)
    args=TrainingArguments(output_dir=out,num_train_epochs=float(cfg.get('epochs',1)),per_device_train_batch_size=int(cfg.get('batch_size',1)),gradient_accumulation_steps=int(cfg.get('gradient_accumulation_steps',4)),learning_rate=float(cfg.get('learning_rate',2e-4)),logging_steps=1,save_strategy='steps',save_steps=int(cfg.get('save_steps',50)),report_to=[])
    lora=LoraConfig(r=int(cfg.get('lora_r',16)),lora_alpha=int(cfg.get('lora_alpha',32)),lora_dropout=float(cfg.get('lora_dropout',0.05)),bias='none',task_type='CAUSAL_LM',target_modules=cfg.get('target_modules',['q_proj','k_proj','v_proj','o_proj']))
    def fmt(x):
        if isinstance(x,dict): return x.get('text') or x.get('content') or json.dumps(x,ensure_ascii=False)
        return str(x)
    common={'model':model,'train_dataset':ds,'formatting_func':fmt,'peft_config':lora,'args':args}
    try:
        trainer=SFTTrainer(processing_class=tok,**common)
    except TypeError:
        trainer=SFTTrainer(tokenizer=tok,**common)
    update(job['id'],'running',20,{'message':f'{len(ds)} Datensätze geladen','device':device})
    trainer.train(); trainer.save_model(out); tok.save_pretrained(out)
    update(job['id'],'completed',100,{'artifact_path':out,'base_model':base,'method':method,'records':len(ds),'device':device})

def main():
    while True:
        job=None
        try:
            with db() as c:
                c.execute("CREATE TABLE IF NOT EXISTS ai_training_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,model_id INTEGER,dataset_id INTEGER,status TEXT,config TEXT,progress INTEGER DEFAULT 0,result TEXT,created_at TEXT,updated_at TEXT)")
                job=c.execute("SELECT j.*,m.base_model,m.method,d.path dataset_path FROM ai_training_jobs j JOIN ai_models m ON m.id=j.model_id JOIN ai_datasets d ON d.id=j.dataset_id WHERE j.status='queued' ORDER BY j.id LIMIT 1").fetchone()
                if job: c.execute("UPDATE ai_training_jobs SET status='running',updated_at=? WHERE id=? AND status='queued'",(now(),job['id']))
            if job:
                try: train(job)
                except Exception as e:
                    update(job['id'],'failed',0,{'error':str(e),'traceback':traceback.format_exc()})
            else: time.sleep(POLL)
        except Exception: time.sleep(POLL)
if __name__=='__main__': main()
