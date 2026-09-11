import hashlib, os, secrets, sqlite3
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
DB_PATH=os.getenv('AI3_DB','/data/ai3.db'); ADMIN_KEY=os.getenv('AI3_ADMIN_KEY',''); OLLAMA_URL=os.getenv('AI3_OLLAMA_URL','http://ollama:11434').rstrip('/')
api=FastAPI(title='AI3 API Server',version='1.2.0')
api.add_middleware(CORSMiddleware,allow_origins=os.getenv('AI3_CORS_ORIGINS','*').split(','),allow_credentials=False,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Authorization','Content-Type','X-AI3-Admin-Key'])
def now(): return datetime.now(timezone.utc).isoformat()
def db():
 c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def init_db():
 with db() as con: con.executescript("CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,status TEXT NOT NULL DEFAULT 'unknown',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS api_events(id INTEGER PRIMARY KEY AUTOINCREMENT,endpoint TEXT NOT NULL,status_code INTEGER NOT NULL,created_at TEXT NOT NULL);")
@api.on_event('startup')
def startup(): os.makedirs(os.path.dirname(DB_PATH) or '.',exist_ok=True); init_db()
def admin(k):
 if not ADMIN_KEY or not k or not secrets.compare_digest(k,ADMIN_KEY): raise HTTPException(401,'invalid admin key')
def token_ok(a):
 if not a or not a.lower().startswith('bearer '): raise HTTPException(401,'Bearer token required')
 raw=a[7:].strip()
 with db() as con:
  row=con.execute('SELECT id,active,expires_at,scopes FROM tokens WHERE token_hash=?',(hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
  if not row or not row['active'] or (row['expires_at'] and row['expires_at']<=now()): raise HTTPException(401,'invalid or expired token')
  if 'ai:inference' not in row['scopes'].split(',') and 'admin' not in row['scopes'].split(','): raise HTTPException(403,'missing scope: ai:inference')
  con.execute('UPDATE tokens SET last_used_at=? WHERE id=?',(now(),row['id']))
def bearer_or_admin(a,k):
 if k: admin(k)
 else: token_ok(a)
class PullRequest(BaseModel): name:str=Field(min_length=1,max_length=200,pattern=r'^[A-Za-z0-9._:/-]+$')
class ChatMessage(BaseModel): role:str=Field(pattern='^(system|user|assistant)$'); content:str=Field(min_length=1,max_length=200000)
class ChatRequest(BaseModel): model:str=Field(min_length=1,max_length=200); messages:list[ChatMessage]=Field(min_length=1,max_length=100); stream:bool=False
@api.get('/health')
def health(): return {'status':'ok','service':'ai3-api-server','ollama':OLLAMA_URL}
@api.get('/api/v1/models')
async def models(authorization:str|None=Header(default=None),x_ai3_admin_key:str|None=Header(default=None)):
 bearer_or_admin(authorization,x_ai3_admin_key)
 async with httpx.AsyncClient(timeout=30) as client:r=await client.get(f'{OLLAMA_URL}/api/tags')
 if r.status_code>=400: raise HTTPException(r.status_code,r.text[:1000])
 data=r.json()
 with db() as con:
  for m in data.get('models',[]):
   n=m.get('name')
   if n: con.execute("INSERT INTO models(name,status,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET status='ready',updated_at=excluded.updated_at",(n,'ready',now(),now()))
 return data
@api.post('/api/v1/models/pull')
async def pull_model(body:PullRequest,x_ai3_admin_key:str|None=Header(default=None)):
 admin(x_ai3_admin_key)
 with db() as con: con.execute("INSERT INTO models(name,status,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET status='downloading',updated_at=excluded.updated_at",(body.name,'downloading',now(),now()))
 async with httpx.AsyncClient(timeout=None) as client:r=await client.post(f'{OLLAMA_URL}/api/pull',json={'name':body.name,'stream':False})
 s='ready' if r.status_code<400 else 'error'
 with db() as con:
  con.execute('UPDATE models SET status=?,updated_at=? WHERE name=?',(s,now(),body.name)); con.execute('INSERT INTO api_events(endpoint,status_code,created_at) VALUES(?,?,?)',('/api/v1/models/pull',r.status_code,now()))
 if r.status_code>=400: raise HTTPException(r.status_code,r.text[:1000])
 return {'ok':True,'model':body.name,'status':s}
@api.post('/v1/chat/completions')
async def chat_completions(body:ChatRequest,authorization:str|None=Header(default=None),x_ai3_admin_key:str|None=Header(default=None)):
 bearer_or_admin(authorization,x_ai3_admin_key)
 if body.stream: raise HTTPException(400,'streaming is not enabled yet')
 payload={'model':body.model,'messages':[m.model_dump() for m in body.messages],'stream':False}
 async with httpx.AsyncClient(timeout=float(os.getenv('AI3_LLM_TIMEOUT','600'))) as client:r=await client.post(f'{OLLAMA_URL}/v1/chat/completions',json=payload)
 if r.status_code>=400: raise HTTPException(r.status_code,r.text[:2000])
 data=r.json()
 with db() as con: con.execute('INSERT INTO api_events(endpoint,status_code,created_at) VALUES(?,?,?)',('/v1/chat/completions',r.status_code,now()))
 return data
@api.get('/api/v1/status')
def status(authorization:str|None=Header(default=None),x_ai3_admin_key:str|None=Header(default=None)):
 bearer_or_admin(authorization,x_ai3_admin_key)
 with db() as con: model_count=con.execute("SELECT COUNT(*) FROM models WHERE status='ready'").fetchone()[0]; event_count=con.execute('SELECT COUNT(*) FROM api_events').fetchone()[0]
 return {'service':'AI3 API Server','version':api.version,'ready_models':model_count,'api_events':event_count}
