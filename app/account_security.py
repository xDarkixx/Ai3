"""Account security, email verification, password recovery and identity-proofing hooks."""
import hashlib, hmac, os, secrets, smtplib, sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional
from urllib.parse import urlencode
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
SESSION_PREFIX = "ai3_user_"
BASE_URL = os.getenv("AI3_PUBLIC_BASE_URL", "").rstrip("/")
VERIFY_HOURS = int(os.getenv("AI3_EMAIL_VERIFY_HOURS", "24"))
RESET_MINUTES = int(os.getenv("AI3_PASSWORD_RESET_MINUTES", "30"))
IDENTITY_PROVIDER_URL = os.getenv("AI3_IDENTITY_PROVIDER_URL", "").strip()
IDENTITY_CALLBACK_SECRET = os.getenv("AI3_IDENTITY_CALLBACK_SECRET", "")


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def now(): return datetime.now(timezone.utc).isoformat()
def hv(v): return hashlib.sha256(v.encode()).hexdigest()

def user_from_session(token: Optional[str]):
    if not token or not token.startswith(SESSION_PREFIX): raise HTTPException(401, "user session required")
    with db() as c:
        row = c.execute("SELECT u.* FROM user_sessions s JOIN users u ON u.id=s.user_id JOIN principals p ON p.id=u.principal_id WHERE s.token_hash=? AND s.active=1 AND u.active=1 AND p.active=1", (hv(token),)).fetchone()
        if not row: raise HTTPException(401, "invalid user session")
        if row["expires_at"] <= now():
            c.execute("UPDATE user_sessions SET active=0 WHERE token_hash=?", (hv(token),)); raise HTTPException(401, "session expired")
        return row

def send_mail(to, subject, text):
    host=os.getenv("AI3_SMTP_HOST", "").strip()
    if not host: return False
    port=int(os.getenv("AI3_SMTP_PORT", "587")); user=os.getenv("AI3_SMTP_USER", ""); password=os.getenv("AI3_SMTP_PASSWORD", "")
    sender=os.getenv("AI3_SMTP_FROM", user).strip()
    msg=EmailMessage(); msg["From"]=sender; msg["To"]=to; msg["Subject"]=subject; msg.set_content(text)
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        if user: s.login(user, password)
        s.send_message(msg)
    return True

def install(app: FastAPI):
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS email_verifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS password_resets(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS identity_verifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,provider TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',reference TEXT,created_at TEXT NOT NULL,verified_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_email_verify_hash ON email_verifications(token_hash);
        CREATE INDEX IF NOT EXISTS idx_reset_hash ON password_resets(token_hash);
        """)

    class ResetRequest(BaseModel): email: str = Field(min_length=3, max_length=320)
    class ResetComplete(BaseModel): token: str = Field(min_length=20, max_length=512); password: str = Field(min_length=12, max_length=256)
    class IdentityCallback(BaseModel): user_id: int = Field(gt=0); reference: str = Field(min_length=1, max_length=256); status: str = Field(pattern="^(verified|rejected|pending)$"); signature: str = Field(min_length=32, max_length=128)

    @app.get("/v1/user/security")
    def security_status(x_ai3_user_session: Optional[str]=Header(default=None)):
        u=user_from_session(x_ai3_user_session)
        with db() as c:
            ev=bool(c.execute("SELECT 1 FROM email_verifications WHERE user_id=? AND used_at IS NOT NULL ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone())
            ident=c.execute("SELECT provider,status,created_at,verified_at FROM identity_verifications WHERE user_id=? ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
        return {"email": u["email"], "email_verified": ev, "identity": dict(ident) if ident else {"status":"unverified"}, "identity_provider_configured": bool(IDENTITY_PROVIDER_URL), "smtp_configured": bool(os.getenv("AI3_SMTP_HOST"))}

    @app.post("/v1/auth/email/verify/request")
    def request_email_verification(x_ai3_user_session: Optional[str]=Header(default=None)):
        u=user_from_session(x_ai3_user_session)
        if not u["email"]: raise HTTPException(400,"account has no email address")
        raw="ai3_verify_"+secrets.token_urlsafe(40); exp=datetime.now(timezone.utc)+timedelta(hours=VERIFY_HOURS)
        with db() as c: c.execute("INSERT INTO email_verifications(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",(u["id"],hv(raw),exp.isoformat(),now()))
        link=f"{BASE_URL}/web/verify-email.html?token={raw}" if BASE_URL else raw
        sent=send_mail(u["email"],"AI3 – E-Mail bestätigen",f"Bestätige deine AI3-E-Mail-Adresse:\n\n{link}\n\nDer Link ist {VERIFY_HOURS} Stunden gültig.")
        return {"ok":True,"sent":sent,"expires_at":exp.isoformat(),"message":"verification requested"}

    @app.post("/v1/auth/email/verify")
    def verify_email(token: str):
        with db() as c:
            row=c.execute("SELECT * FROM email_verifications WHERE token_hash=? AND used_at IS NULL",(hv(token),)).fetchone()
            if not row or row["expires_at"]<=now(): raise HTTPException(400,"invalid or expired verification token")
            c.execute("UPDATE email_verifications SET used_at=? WHERE id=?",(now(),row["id"]))
        return {"ok":True,"verified":True}

    @app.post("/v1/auth/password-reset/request")
    def password_reset_request(body: ResetRequest):
        # Deliberately identical public response to prevent account enumeration.
        with db() as c: u=c.execute("SELECT id,email FROM users WHERE lower(email)=lower(?) AND active=1",(body.email.strip(),)).fetchone()
        if u:
            raw="ai3_reset_"+secrets.token_urlsafe(40); exp=datetime.now(timezone.utc)+timedelta(minutes=RESET_MINUTES)
            with db() as c: c.execute("INSERT INTO password_resets(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",(u["id"],hv(raw),exp.isoformat(),now()))
            link=f"{BASE_URL}/web/reset-password.html?token={raw}" if BASE_URL else raw
            try: send_mail(u["email"],"AI3 – Passwort zurücksetzen",f"Passwort zurücksetzen:\n\n{link}\n\nDer Link ist {RESET_MINUTES} Minuten gültig.")
            except Exception: pass
        return {"ok":True,"message":"If the account exists, reset instructions have been sent."}

    @app.post("/v1/auth/password-reset/complete")
    def password_reset_complete(body: ResetComplete):
        from app.user_accounts import hash_password
        with db() as c:
            r=c.execute("SELECT * FROM password_resets WHERE token_hash=? AND used_at IS NULL",(hv(body.token),)).fetchone()
            if not r or r["expires_at"]<=now(): raise HTTPException(400,"invalid or expired reset token")
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(body.password),r["user_id"]))
            c.execute("UPDATE password_resets SET used_at=? WHERE id=?",(now(),r["id"]))
            c.execute("UPDATE user_sessions SET active=0 WHERE user_id=?",(r["user_id"],))
        return {"ok":True,"message":"password changed; please log in again"}

    @app.post("/v1/user/identity/start")
    def identity_start(x_ai3_user_session: Optional[str]=Header(default=None)):
        u=user_from_session(x_ai3_user_session)
        if not IDENTITY_PROVIDER_URL: raise HTTPException(503,"identity provider is not configured")
        reference="ai3_id_"+secrets.token_urlsafe(24)
        with db() as c: c.execute("INSERT INTO identity_verifications(user_id,provider,status,reference,created_at) VALUES(?,?,?,?,?)",(u["id"],IDENTITY_PROVIDER_URL,"pending",reference,now()))
        callback=f"{BASE_URL}/v1/user/identity/callback"
        return {"status":"pending","provider":IDENTITY_PROVIDER_URL,"reference":reference,"callback":callback,"redirect":IDENTITY_PROVIDER_URL+"?"+urlencode({"reference":reference,"callback":callback})}

    @app.post("/v1/user/identity/callback")
    def identity_callback(body: IdentityCallback):
        if not IDENTITY_CALLBACK_SECRET: raise HTTPException(503,"identity callback secret is not configured")
        payload=f"{body.user_id}:{body.reference}:{body.status}".encode(); expected=hmac.new(IDENTITY_CALLBACK_SECRET.encode(),payload,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,body.signature): raise HTTPException(403,"invalid identity callback signature")
        verified_at=now() if body.status=="verified" else None
        with db() as c: c.execute("UPDATE identity_verifications SET status=?,verified_at=? WHERE user_id=? AND reference=?",(body.status,verified_at,body.user_id,body.reference))
        return {"ok":True,"status":body.status}
