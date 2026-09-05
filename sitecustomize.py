import hashlib
import os
import secrets

try:
    from app.main import app
    from app import main

    def _safe_hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        n, r, p = 32768, 8, 1
        digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
        return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"

    def _safe_verify_password(password: str, encoded: str) -> bool:
        try:
            algo, n, r, p, salt_hex, digest_hex = encoded.split("$", 5)
            if algo != "scrypt":
                return False
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32)
            return secrets.compare_digest(digest.hex(), digest_hex)
        except (ValueError, TypeError):
            return False

    main.hash_password = _safe_hash_password
    main.verify_password = _safe_verify_password

    if os.getenv("AI3_ENABLE_ADVANCED_SECURITY", "0") == "1":
        from app.advanced_security import install as install_security
        from app.rate_limit import install as install_rate_limit
        from app.runtime_controls import install as install_runtime_controls
        from app import user_accounts
        user_accounts.hash_password = _safe_hash_password
        user_accounts.verify_password = _safe_verify_password
        install_security(app)
        install_runtime_controls(app)
        user_accounts.install(app)
        install_rate_limit(app)

    # Defense in depth: encrypt stored chat history and add bounded application-layer
    # DDoS/abuse protection. These never log or store raw bearer tokens.
    from app.chat_security import install as install_chat_security
    from app.ddos_protection import install as install_ddos_protection
    install_chat_security(app)
    install_ddos_protection(app)
except Exception:
    pass
