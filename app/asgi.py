"""Production ASGI entrypoint with all optional AI3 gateway modules installed."""
from app.main import app
from app.pki import install as install_pki

install_pki(app)
