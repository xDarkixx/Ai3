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
        from app.user_accounts import install as install_user_accounts
        install_security(app)
        install_runtime_controls(app)
        install_user_accounts(app)
        install_rate_limit(app)
except Exception:
    pass
