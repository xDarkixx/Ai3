"""AI3 private agent host: owner-managed agents, permissions and execution jobs."""
import json, sqlite3, uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.main import db, now, require_admin
router=APIRouter(prefix='/v1/admin/agents',tags=['Agents'])
def init_db():
 with db() as c:c.executescript('''CREATE TABLE IF NOT EXISTS ai_agents(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,model TEXT NOT NULL,backend TEXT NOT NULL DEFAULT 'ollama',system_prompt TEXT NOT NULL DEFAULT '',permissions TEXT NOT NULL DEFAULT '[]',workspace TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS ai_agent_jobs(id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,task TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',result TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(agent_id) REFERENCES ai_agents(id));''')
class AgentIn(BaseModel):
 name:str=Field(min_length=1,max_length=100);model:str=Field(min_length=1,max_length=200);backend:str=Field(default='ollama',pattern='^(ollama|vllm|llamacpp|openai-compatible)$');system_prompt:str=Field(default='',max_length=20000);permissions:list[str]=Field(default_factory=list);workspace:str=Field(default='',max_length=500)
class JobIn(BaseModel):task:str=Field(min_length=1,max_length=100000)
@router.get('',dependencies=[Depends(require_admin)])
def agents():
 init_db()
 with db() as c:rows=c.execute('SELECT * FROM ai_agents ORDER BY name').fetchall()
 return [{**dict(r),'permissions':json.loads(r['permissions'])} for r in rows]
@router.post('',dependencies=[Depends(require_admin)])
def create(a:AgentIn):
 init_db();aid='agent_'+uuid.uuid4().hex
 with db() as c:
  try:c.execute('INSERT INTO ai_agents VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,a.name,a.model,a.backend,a.system_prompt,json.dumps(sorted(set(a.permissions))),a.workspace,1,now(),now()))
  except sqlite3.IntegrityError:raise HTTPException(409,'agent already exists')
 return {'id':aid,**a.model_dump(),'active':True}
@router.delete('/{agent_id}',dependencies=[Depends(require_admin)])
def delete(agent_id:str):
 init_db()
 with db() as c:n=c.execute('DELETE FROM ai_agents WHERE id=?',(agent_id,)).rowcount
 if not n:raise HTTPException(404,'agent not found')
 return {'ok':True}
@router.post('/{agent_id}/jobs',dependencies=[Depends(require_admin)])
def queue(agent_id:str,b:JobIn):
 init_db();jid='job_'+uuid.uuid4().hex
 with db() as c:
  if not c.execute('SELECT 1 FROM ai_agents WHERE id=? AND active=1',(agent_id,)).fetchone():raise HTTPException(404,'agent not found')
  c.execute('INSERT INTO ai_agent_jobs VALUES(?,?,?,?,?,?,?)',(jid,agent_id,b.task,'queued','',now(),now()))
 return {'id':jid,'status':'queued'}
@router.get('/jobs/{job_id}',dependencies=[Depends(require_admin)])
def job(job_id:str):
 with db() as c:r=c.execute('SELECT * FROM ai_agent_jobs WHERE id=?',(job_id,)).fetchone()
 if not r:raise HTTPException(404,'job not found')
 return dict(r)
def install(app):init_db();app.include_router(router)
