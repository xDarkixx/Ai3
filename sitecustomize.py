import os

if os.getenv("AI3_ENABLE_ADVANCED_SECURITY", "0") == "1":
    try:
        from app.main import app
        from app.advanced_security import install

        install(app)
    except Exception:
        # Keep Python startup usable; the application startup will report normal errors.
        pass
