"""Self-hosted EUDI Wallet identity verification bridge.

AI3 does not invent or self-sign identities. The verifier endpoint and trust
validator run as containers owned by the operator. Verification is based on
OpenID4VP and the EUDI reference implementation.
"""
import os
import secrets
from urllib.parse import quote

import httpx
from fastapi import FastAPI, Header, HTTPException

VERIFIER_URL = os.getenv("AI3_EUDI_VERIFIER_URL", "http://eudi-verifier:8080").rstrip("/")
PUBLIC_URL = os.getenv("AI3_EUDI_PUBLIC_URL", "").rstrip("/")


def install(app: FastAPI):
    @app.get("/v1/eudi/config")
    def config():
        return {
            "enabled": bool(PUBLIC_URL),
            "mode": "self-hosted",
            "protocol": "OpenID4VP",
            "verifier": "AI3 self-hosted EUDI verifier",
            "trust_validator": "AI3 self-hosted EUDI trust validator",
            "public_url_configured": bool(PUBLIC_URL),
            "verifier_url_configured": bool(VERIFIER_URL),
            "commercial_provider_required": False,
        }

    @app.post("/v1/user/identity/eudi/start")
    async def start_eudi(x_ai3_user_session: str | None = Header(default=None)):
        if not x_ai3_user_session:
            raise HTTPException(401, "user session required")
        if not PUBLIC_URL:
            raise HTTPException(503, "AI3_EUDI_PUBLIC_URL is not configured")
        nonce = secrets.token_urlsafe(32)
        credential_id = "ai3-pid"
        payload = {
            "dcql_query": {
                "credentials": [{
                    "id": credential_id,
                    "format": "mso_mdoc",
                    "meta": {"doctype_value": "eu.europa.ec.eudi.pid.1"},
                    "claims": [
                        {"path": ["eu.europa.ec.eudi.pid.1", "family_name"]},
                        {"path": ["eu.europa.ec.eudi.pid.1", "given_name"]},
                    ],
                }],
                "credential_sets": [{
                    "options": [[credential_id]],
                    "purpose": "Verify the AI3 account holder's identity",
                }],
            },
            "nonce": nonce,
            "jar_mode": "by_reference",
            "request_uri_method": "post",
            "profile": "openid4vp",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{VERIFIER_URL}/ui/presentations/v2", json=payload)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "self-hosted EUDI verifier unavailable") from exc
        tx = result.get("transaction_id")
        if not tx:
            raise HTTPException(502, "EUDI verifier returned no transaction")
        # The verifier is configured with the same public base URL. Its returned
        # request_uri therefore already contains the correct public /eudi path.
        request_uri = result.get("request_uri") or result.get("authorization_request_uri")
        return {
            "ok": True,
            "transaction_id": tx,
            "request_uri": request_uri,
            "request_uri_method": result.get("request_uri_method", "post"),
            "privacy": "Only the claims requested by AI3 are presented; AI3 does not store ID photos or PINs.",
        }

    @app.get("/v1/user/identity/eudi/{transaction_id}")
    async def eudi_result(transaction_id: str, x_ai3_user_session: str | None = Header(default=None)):
        if not x_ai3_user_session:
            raise HTTPException(401, "user session required")
        if not transaction_id or len(transaction_id) > 512:
            raise HTTPException(400, "invalid transaction id")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{VERIFIER_URL}/ui/presentations/{quote(transaction_id, safe='')}")
                if response.status_code == 404:
                    raise HTTPException(404, "EUDI transaction not found")
                response.raise_for_status()
                data = response.json()
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "self-hosted EUDI verifier unavailable") from exc
        return {"ok": True, "verified": isinstance(data, list) and bool(data), "result": data}

    return app
