"""German Online-Ausweis integration helper.

AI3 acts as the relying-party application. The cryptographic eID-server and
its authorisation certificate/private key remain a separate hardened service.
This module deliberately never implements or fakes eID verification itself.
"""
import os
from urllib.parse import quote
from fastapi import FastAPI, Header, HTTPException

EID_SERVER_URL = os.getenv("AI3_EID_SERVER_URL", "").rstrip("/")
TC_TOKEN_URL = os.getenv("AI3_EID_TC_TOKEN_URL", "").strip()


def install(app: FastAPI):
    @app.get("/v1/eid/config")
    def eid_config():
        return {
            "enabled": bool(EID_SERVER_URL and TC_TOKEN_URL),
            "provider": "German Online-Ausweis / AusweisApp",
            "eid_server_configured": bool(EID_SERVER_URL),
            "tc_token_url_configured": bool(TC_TOKEN_URL),
            "desktop_client_url": "http://127.0.0.1:24727/eID-Client",
            "mobile_client_url": "eid://127.0.0.1:24727/eID-Client",
        }

    @app.get("/v1/eid/client-url")
    def eid_client_url():
        if not TC_TOKEN_URL:
            raise HTTPException(503, "German eID is not configured: AI3_EID_TC_TOKEN_URL is missing")
        return {
            "desktop": "http://127.0.0.1:24727/eID-Client?tcTokenURL=" + quote(TC_TOKEN_URL, safe=""),
            "mobile": "eid://127.0.0.1:24727/eID-Client?tcTokenURL=" + quote(TC_TOKEN_URL, safe=""),
            "tc_token_url": TC_TOKEN_URL,
            "eID_server": EID_SERVER_URL,
        }

    return app
