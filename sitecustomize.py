import os

if os.getenv("AI3_ENABLE_ADVANCED_SECURITY", "0") == "1":
    try:
        from app.main import app
        from app.advanced_security import install as install_security
        from app.rate_limit import install as install_rate_limit
        from app.runtime_controls import install as install_runtime_controls

        install_security(app)
        install_runtime_controls(app)
        install_rate_limit(app)
    except Exception:
        # Keep Python startup usable; the application startup will report normal errors.
        pass
