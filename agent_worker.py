import asyncio, json, os, sqlite3
from datetime import datetime, timezone
import httpx

DB_PATH=os.getenv('AI3_DB','/data/ai3.db')
OLLAMA_URL=os.getenv('AI3_OLLAMA_URL','http://ollama:11434').rstrip('/')
POLL=float(os.getenv('AI3_AGENT_POLL_SECONDS','2'))


def now(): return datetime.now(timezone.utc).isoformat()
def db():
 c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

async def run_job(row):
 with db() as c:
  c.execute("UPDATE ai_agent_jobs SET status='running',updated_at=? WHERE id=? AND status='queued'",(now(),row['id']))
 try:
  with db() as c:
   a=c.execute('SELECT * FROM ai_agents WHERE id=? AND active=1',(row['agent_id'],)).fetchone()
  if not a: raise RuntimeError('agent not found or inactive')
  if a['backend']!='ollama': raise RuntimeError('worker currently supports only local Ollama agents')
  messages=[]
  if a['system_prompt']: messages.append({'role':'system','content':a['system_prompt']})
  messages.append({'role':'user','content':row['task']})
  async with httpx.AsyncClient(timeout=float(os.getenv('AI3_AGENT_TIMEOUT','600'))) as client:
   r=await client.post(f'{OLLAMA_URL}/api/chat',json={'model':a['model'],'messages':messages,'stream':False})
  if r.status_code>=400: raise RuntimeError(f'Ollama {r.status_code}: {r.text[:2000]}')
  data=r.json(); result=((data.get('message') or {}).get('content') or '')
  if not result: raise RuntimeError('Ollama returned no message content')
  with db() as c:c.execute("UPDATE ai_agent_jobs SET status='completed',result=?,updated_at=? WHERE id=?",(result,now(),row['id']))
 except Exception as exc:
  with db() as c:c.execute("UPDATE ai_agent_jobs SET status='failed',result=?,updated_at=? WHERE id=?",(str(exc),now(),row['id']))

async def main():
 while True:
  try:
   with db() as c:
    rows=c.execute("SELECT * FROM ai_agent_jobs WHERE status='queued' ORDER BY created_at LIMIT 4").fetchall()
   if rows: await asyncio.gather(*(run_job(r) for r in rows))
  except Exception:
   pass
  await asyncio.sleep(POLL)

if __name__=='__main__': asyncio.run(main())
