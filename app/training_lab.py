"""AI3 Training Lab: dataset/model registry and controlled LoRA/QLoRA job queue."""
import json, sqlite3, uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.main import db, now, require_admin
router=APIRouter(prefix='/v1/admin/training',tags=['Training Lab'])
def init_db():
 with db() as c:c.executescript('''CREATE TABLE IF NOT EXISTS ai_datasets(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,format TEXT NOT NULL,path TEXT NOT NULL,records INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS ai_models(id TEXT PRIMARY KEY,name TEXT NOT NULL,base_model TEXT NOT NULL,method TEXT NOT NULL,artifact_path TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'registered',created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS ai_training_jobs(id TEXT PRIMARY KEY,model_id TEXT NOT NULL,dataset_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',config TEXT NOT NULL,progress REAL NOT NULL DEFAULT 0,result TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(model_id) REFERENCES ai_models(id),FOREIGN KEY(dataset_id) REFERENCES ai_datasets(id));''')
class DatasetIn(BaseModel): name:str=Field(min_length=1,max_length=120); format:str=Field(pattern='^(jsonl|json|csv|txt)$'); path:str=Field(min_length=1,max_length=1000); records:int=Field(default=0,ge=0)
class ModelIn(BaseModel): name:str=Field(min_length=1,max_length=120); base_model:str=Field(min_length=1,max_length=300); method:str=Field(default='qlora',pattern='^(lora|qlora)$'); artifact_path:str=''
class TrainIn(BaseModel): model_id:str; dataset_id:str; config:dict={}
@router.get('/status',dependencies=[Depends(require_admin)])
def status():
 init_db();
 with db() as c:return {'datasets':c.execute('SELECT COUNT(*) FROM ai_datasets').fetchone()[0],'models':c.execute('SELECT COUNT(*) FROM ai_models').fetchone()[0],'jobs':c.execute('SELECT COUNT(*) FROM ai_training_jobs').fetchone()[0],'backend':'job-queue'}
@router.post('/datasets',dependencies=[Depends(require_admin)])
def dataset(b:DatasetIn):
 init_db(); did='ds_'+uuid.uuid4().hex
 with db() as c:
  try:c.execute('INSERT INTO ai_datasets VALUES(?,?,?,?,?,?)',(did,b.name,b.format,b.path,b.records,now()))
  except sqlite3.IntegrityError:raise HTTPException(409,'dataset already exists')
 return {'id':did,**b.model_dump()}
@router.get('/datasets',dependencies=[Depends(require_admin)])
def datasets():
 init_db();
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM ai_datasets ORDER BY created_at DESC')]
@router.post('/models',dependencies=[Depends(require_admin)])
def model(b:ModelIn):
 init_db(); mid='model_'+uuid.uuid4().hex
 with db() as c:c.execute('INSERT INTO ai_models VALUES(?,?,?,?,?,?,?)',(mid,b.name,b.base_model,b.method,b.artifact_path,'registered',now()))
 return {'id':mid,**b.model_dump(),'status':'registered'}
@router.get('/models',dependencies=[Depends(require_admin)])
def models():
 init_db();
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM ai_models ORDER BY created_at DESC')]
@router.post('/jobs',dependencies=[Depends(require_admin)])
def train(b:TrainIn):
 init_db(); jid='train_'+uuid.uuid4().hex
 with db() as c:
  if not c.execute('SELECT 1 FROM ai_models WHERE id=?',(b.model_id,)).fetchone() or not c.execute('SELECT 1 FROM ai_datasets WHERE id=?',(b.dataset_id,)).fetchone():raise HTTPException(404,'model or dataset not found')
  c.execute('INSERT INTO ai_training_jobs VALUES(?,?,?,?,?,?,?,?,?)',(jid,b.model_id,b.dataset_id,'queued',json.dumps(b.config),0.0,'',now(),now()))
 return {'id':jid,'status':'queued','method':'controlled-lora/qlora'}
@router.get('/jobs/{job_id}',dependencies=[Depends(require_admin)])
def job(job_id:str):
 with db() as c:r=c.execute('SELECT * FROM ai_training_jobs WHERE id=?',(job_id,)).fetchone()
 if not r:raise HTTPException(404,'training job not found')
 d=dict(r);d['config']=json.loads(d['config']);return d
def install(app):init_db();app.include_router(router)
