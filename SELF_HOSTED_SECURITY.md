# AI3 — Self-Hosted Verification & PKI

AI3 can run without a paid AI API, paid KYC service, eID service or EUDI service.

## AI3 Own Verification

The verification workflow is entirely inside the AI3 installation:

1. User opens **AI3 Own Verification** in the account area.
2. User submits allowed evidence (ID images and, when required by the operator, a selfie).
3. Evidence is encrypted with the AI3 32-byte data-encryption key before it is stored.
4. The host reviews the case through authenticated admin endpoints.
5. The case can be marked `pending`, `verified` or `rejected`.
6. Evidence can be purged automatically/manually according to `AI3_VERIFICATION_RETENTION_DAYS`.

This is **operator verification**, not a government-certified identity assertion. AI3 does not claim that a document review is equivalent to a state identity service.

No eID, EUDI Wallet, AusweisApp or external identity/KYC provider is contacted by this implementation.

## Private AI3 PKI

AI3 creates a private EC P-256 root CA under `AI3_PKI_DIR`. The CA private key is encrypted with the same 32-byte AI3 data key and stored with restrictive filesystem permissions.

The PKI can issue:

- `server` certificates for internal AI3 services
- `client` certificates for authenticated clients
- `agent` certificates for AI3 agents

Admin endpoints provide certificate listing, issuance and revocation. The root certificate is available at `GET /v1/pki/ca` so trusted AI3 clients can install it.

The private AI3 CA is **not** a public browser trust anchor. For public HTTPS, use a free public DV certificate such as Let's Encrypt or a certificate supplied by your existing infrastructure. Let's Encrypt certificates are free and automatically renewable; the private key remains on the server. See the official documentation: https://letsencrypt.org/de/

## Cost model

The software components above do not require a commercial identity provider or paid certificate authority. A completely self-hosted deployment can therefore avoid recurring software/KYC/certificate fees. Actual operating costs can still include electricity, hardware, Internet access, a domain, backups, email/SMS delivery, or other infrastructure chosen by the operator.

## Important production rules

- Never commit `.env`, AI3 data keys, CA keys or issued private keys.
- Keep `/data/pki` and `/data` on encrypted storage where practical.
- Back up the AI3 data key separately; losing it makes encrypted data and the encrypted CA key unrecoverable.
- Put public AI3 behind a hardened reverse proxy/firewall and HTTPS.
- Do not expose admin endpoints directly to the public Internet.
- Define a lawful retention/deletion policy before collecting identity evidence.
