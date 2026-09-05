"""AI3 Own Verification: encrypted evidence + manual host review.

No eID, EUDI wallet or external KYC/identity provider is contacted. This is
an operator verification workflow, not a government-certified identity proof.
"""
import base64, hashlib, json, os, sqlite3
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DB_PATH=os.getenv("AI3_DB","/data/ai3.db")
MAX_BYTES=int(os.getenv("AI3_VERIFICATION_MAX_BYTES","8388608")); RETENTION_DAYS=int(os.getenv("AI3_VERIFICATION_RETENTION_DAYS","30"))
KEY_FILE=os.getenv("AI3_DATA_ENCRYPTION_KEY_FILE","/run/secrets/ai3_data_key")

def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".",exist_ok=True); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def now(): return datetime.now(timezone.utc).isoformat()
def key():
    raw=open(KEY_FILE,"rb").read().strip() if os.path.exists(KEY_FILE) else os.getenv("AI3_DATA_ENCRYPTION_KEY","").encode()
    if len(raw)!=32: raise RuntimeError("AI3 data encryption key must be 32 bytes")
    return raw

def enc(raw:bytes,aad:bytes):
    nonce=os.urandom(12); return nonce+AESGCM(key()).encrypt(nonce,raw,aad)
def dec(blob:bytes,aad:bytes): return AESGCM(key()).decrypt(blob[:12],blob[12:],aad)

def user(session):
    if not session or not session.startswith("ai3_user_"): raise HTTPException(401,"user session required")
    with db() as c:
        r=c.execute("SELECT u.* FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.active=1 AND u.active=1",(hashlib.sha256(session.encode()).hexdigest(),)).fetchone()
    if not r or r["expires_at"]<=now(): raise HTTPException(401,"invalid or expired user session")
    return r

def install(app:FastAPI):
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS ai3_verifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',notes TEXT,created_at TEXT NOT NULL,reviewed_at TEXT,verified_at TEXT,certificate_serial TEXT);
        CREATE TABLE IF NOT EXISTS ai3_verification_evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,verification_id INTEGER NOT NULL,kind TEXT NOT NULL,mime_type TEXT NOT NULL,sha256 TEXT NOT NULL,ciphertext BLOB NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(verification_id) REFERENCES ai3_verifications(id));
        CREATE INDEX IF NOT EXISTS idx_ai3_verification_user ON ai3_verifications(user_id);
        """)
    class Evidence(BaseModel):
        kind:str=Field(pattern=r"^(id_front|id_back|selfie|other)$")
        mime_type:str=Field(pattern=r"^image/(jpeg|png|webp)$")
        data_base64:str=Field(min_length=16,max_length=MAX_BYTES*2)
    class Submit(BaseModel): evidence:list[Evidence]=Field(min_length=1,max_length=4)
    class Review(BaseModel): status:str=Field(pattern=r"^(verified|rejected|pending)$"); notes:Optional[str]=Field(default=None,max_length=4000); certificate_serial:Optional[str]=Field(default=None,max_length=128)
    @app.post("/v1/user/verification")
    def submit(body:Submit,x_ai3_user_session:str|None=Header(default=None)):
        u=user(x_ai3_user_session)
        with db() as c:
            existing=c.execute("SELECT id FROM ai3_verifications WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
            if existing: raise HTTPException(409,"verification already pending")
            cur=c.execute("INSERT INTO ai3_verifications(user_id,created_at) VALUES(?,?)",(u["id"],now())); vid=cur.lastrowid
            total=0
            for item in body.evidence:
                try: raw=base64.b64decode(item.data_base64,validate=True)
                except Exception: raise HTTPException(400,"invalid base64 evidence")
                total+=len(raw)
                if len(raw)>MAX_BYTES or total>MAX_BYTES: raise HTTPException(413,"verification evidence too large")
                digest=hashlib.sha256(raw).hexdigest(); blob=enc(raw,f"AI3-VERIFICATION:{vid}".encode())
                c.execute("INSERT INTO ai3_verification_evidence(verification_id,kind,mime_type,sha256,ciphertext,created_at) VALUES(?,?,?,?,?,?)",(vid,item.kind,item.mime_type,digest,blob,now()))
        return {"ok":True,"verification_id":vid,"status":"pending","message":"AI3 host review required"}
    @app.get("/v1/user/verification")
    def status(x_ai3_user_session:str|None=Header(default=None)):
        u=user(x_ai3_user_session)
        with db() as c: r=c.execute("SELECT id,status,notes,created_at,reviewed_at,verified_at,certificate_serial FROM ai3_verifications WHERE user_id=? ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
        return dict(r) if r else {"status":"unverified"}
    @app.get("/v1/admin/verifications")
    def queue(x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        with db() as c: rows=c.execute("SELECT v.id,v.user_id,v.status,v.created_at,v.reviewed_at,v.verified_at,v.certificate_serial,u.username,u.email FROM ai3_verifications v JOIN users u ON u.id=v.user_id ORDER BY v.id DESC").fetchall()
        return {"verifications":[dict(r) for r in rows]}
    @app.get("/v1/admin/verifications/{verification_id}/evidence/{evidence_id}")
    def evidence(verification_id:int,evidence_id:int,x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        with db() as c: r=c.execute("SELECT * FROM ai3_verification_evidence WHERE id=? AND verification_id=?",(evidence_id,verification_id)).fetchone()
        if not r: raise HTTPException(404,"evidence not found")
        raw=dec(r["ciphertext"],f"AI3-VERIFICATION:{verification_id}".encode())
        return {"id":r["id"],"kind":r["kind"],"mime_type":r["mime_type"],"sha256":r["sha256"],"data_base64":base64.b64encode(raw).decode()}
    @app.post("/v1/admin/verifications/{verification_id}/review")
    def review(verification_id:int,body:Review,x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        verified=now() if body.status=="verified" else None
        with db() as c:
            cur=c.execute("UPDATE ai3_verifications SET status=?,notes=?,reviewed_at=?,verified_at=?,certificate_serial=? WHERE id=?",(body.status,body.notes,now(),verified,body.certificate_serial,verification_id))
        if cur.rowcount!=1: raise HTTPException(404,"verification not found")
        return {"ok":True,"verification_id":verification_id,"status":body.status}
    @app.post("/v1/admin/verifications/purge-expired")
    def purge(x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        cutoff=(datetime.now(timezone.utc).timestamp()-RETENTION_DAYS*86400)
        removed=0
        with db() as c:
            rows=c.execute("SELECT id,created_at FROM ai3_verifications").fetchall()
            for r in rows:
                if datetime.fromisoformat(r["created_at"]).timestamp()<cutoff:
                    c.execute("DELETE FROM ai3_verification_evidence WHERE verification_id=?",(r["id"],)); c.execute("DELETE FROM ai3_verifications WHERE id=?",(r["id"],)); removed+=1
        return {"ok":True,"removed":removed,"retention_days":RETENTION_DAYS}
