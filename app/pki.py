"""Self-hosted AI3 PKI.

Creates an encrypted-at-rest private CA key, signs short-lived service/client
certificates, and exposes verification metadata. The CA is private to AI3 and
is not a public browser trust anchor.
"""
import os, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DB_PATH=os.getenv("AI3_DB","/data/ai3.db")
PKI_DIR=Path(os.getenv("AI3_PKI_DIR","/data/pki")); KEY_FILE=PKI_DIR/"ca.key.enc"; CERT_FILE=PKI_DIR/"ca.crt"
ENC_KEY_FILE=os.getenv("AI3_DATA_ENCRYPTION_KEY_FILE","/run/secrets/ai3_data_key")

def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".",exist_ok=True); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def now(): return datetime.now(timezone.utc)
def data_key():
    raw=Path(ENC_KEY_FILE).read_bytes().strip() if ENC_KEY_FILE and os.path.exists(ENC_KEY_FILE) else os.getenv("AI3_DATA_ENCRYPTION_KEY","").encode()
    if len(raw)!=32: raise RuntimeError("AI3 data encryption key must be exactly 32 bytes")
    return raw

def protect(raw:bytes):
    nonce=os.urandom(12); return nonce+AESGCM(data_key()).encrypt(nonce,raw,b"AI3-CA")
def unprotect(blob:bytes): return AESGCM(data_key()).decrypt(blob[:12],blob[12:],b"AI3-CA")

def ensure_ca():
    PKI_DIR.mkdir(parents=True,exist_ok=True); os.chmod(PKI_DIR,0o700)
    if KEY_FILE.exists() and CERT_FILE.exists(): return
    key=ec.generate_private_key(ec.SECP256R1()); subject=x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME,"AI3"),x509.NameAttribute(NameOID.COMMON_NAME,"AI3 Root CA")])
    usage=x509.KeyUsage(digital_signature=True,key_encipherment=False,key_cert_sign=True,crl_sign=True,key_agreement=False,data_encipherment=False,content_commitment=False,encipher_only=False,decipher_only=False)
    cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now()-timedelta(minutes=1)).not_valid_after(now()+timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=1),critical=True).add_extension(usage,critical=True).sign(key,hashes.SHA256())
    KEY_FILE.write_bytes(protect(key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())))
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM)); os.chmod(KEY_FILE,0o600); os.chmod(CERT_FILE,0o644)

def ca_objects():
    ensure_ca(); key=serialization.load_der_private_key(unprotect(KEY_FILE.read_bytes()),password=None); cert=x509.load_pem_x509_certificate(CERT_FILE.read_bytes()); return key,cert

def install(app:FastAPI):
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS ai3_certificates(id INTEGER PRIMARY KEY AUTOINCREMENT,serial TEXT UNIQUE NOT NULL,subject TEXT NOT NULL,kind TEXT NOT NULL,cert_pem TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,revoked_at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ai3_cert_serial ON ai3_certificates(serial)")
    try: ensure_ca()
    except Exception: pass
    class CertRequest(BaseModel):
        common_name:str=Field(min_length=1,max_length=128,pattern=r"^[A-Za-z0-9._:@/-]+$")
        kind:str=Field(default="client",pattern=r"^(server|client|agent)$")
        days:int=Field(default=90,ge=1,le=825)
    @app.get("/v1/pki/ca")
    def ca_info():
        try: _,cert=ca_objects()
        except Exception: raise HTTPException(503,"AI3 PKI is not initialized")
        return {"name":"AI3 Root CA","serial":format(cert.serial_number,"x"),"not_after":cert.not_valid_after_utc.isoformat(),"certificate_pem":cert.public_bytes(serialization.Encoding.PEM).decode()}
    @app.post("/v1/admin/pki/certificates")
    def issue(body:CertRequest,x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        try: ca_key,ca_cert=ca_objects()
        except Exception as e: raise HTTPException(503,str(e))
        key=ec.generate_private_key(ec.SECP256R1()); subject=x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME,"AI3"),x509.NameAttribute(NameOID.COMMON_NAME,body.common_name)])
        builder=x509.CertificateBuilder().subject_name(subject).issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now()-timedelta(minutes=1)).not_valid_after(now()+timedelta(days=body.days)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        usage=ExtendedKeyUsageOID.SERVER_AUTH if body.kind=="server" else ExtendedKeyUsageOID.CLIENT_AUTH
        cert=builder.add_extension(x509.ExtendedKeyUsage([usage]),critical=False).sign(ca_key,hashes.SHA256())
        pem=cert.public_bytes(serialization.Encoding.PEM).decode(); private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
        with db() as c: c.execute("INSERT INTO ai3_certificates(serial,subject,kind,cert_pem,created_at,expires_at) VALUES(?,?,?,?,?,?)",(str(cert.serial_number),body.common_name,body.kind, pem,now().isoformat(),cert.not_valid_after_utc.isoformat()))
        return {"certificate":pem,"private_key":private,"ca_certificate":ca_cert.public_bytes(serialization.Encoding.PEM).decode(),"serial":str(cert.serial_number),"expires_at":cert.not_valid_after_utc.isoformat()}
    @app.post("/v1/admin/pki/revoke/{serial}")
    def revoke(serial:str,x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        with db() as c: cur=c.execute("UPDATE ai3_certificates SET revoked_at=? WHERE serial=? AND revoked_at IS NULL",(now().isoformat(),serial))
        if cur.rowcount!=1: raise HTTPException(404,"certificate not found or already revoked")
        return {"ok":True,"revoked":serial}
    @app.get("/v1/admin/pki/certificates")
    def list_certs(x_ai3_admin_key:str|None=Header(default=None),x_ai3_admin_session:str|None=Header(default=None)):
        from app.main import require_admin
        require_admin(x_ai3_admin_key,x_ai3_admin_session)
        with db() as c: rows=c.execute("SELECT serial,subject,kind,created_at,expires_at,revoked_at FROM ai3_certificates ORDER BY id DESC").fetchall()
        return {"certificates":[dict(r) for r in rows]}
