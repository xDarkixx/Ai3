# AI3 Security & Privacy

AI3 is designed for self-hosted, privacy-first operation. No software can honestly guarantee that nobody can ever steal data, but AI3 now protects stored chat content with authenticated encryption and adds application-layer abuse/DDoS mitigation.

## Encrypted chat storage

When a non-streaming `/v1/chat/completions` request succeeds, AI3 stores the conversation exchange encrypted at rest:

- AES-256-GCM is used for confidentiality and integrity.
- A fresh random nonce is generated for every stored exchange.
- Chat plaintext is not stored in SQLite.
- The encryption key is stored outside the database through a Docker secret file by default.
- The key is never committed to Git and `secrets/` is ignored by Git.
- Each encrypted record is bound to its principal and conversation ID with authenticated associated data.
- A stolen database file alone is therefore not enough to decrypt the stored chats.
- `GET /v1/chat/history` returns only the authenticated principal's own history.
- `DELETE /v1/chat/history` deletes the authenticated principal's stored history.
- Streaming responses are not persisted by the automatic history capture.
- Chat history is capped by `AI3_MAX_CHAT_STORAGE_BYTES` (default 2 MB per exchange).

The setup script automatically creates `secrets/ai3_data_encryption_key` with restrictive permissions. **Back up this key separately from the database**. If the key is lost, encrypted chat history cannot be recovered. If the key is suspected to be compromised, rotate the key using a planned decrypt/re-encrypt migration; do not simply replace the key or old chats become unreadable.

OWASP recommends authenticated encryption such as AES-GCM and separation of encryption keys from encrypted data. urlOWASP Cryptographic Storage guidancehttps://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html

## Privacy by default

With `AI3_PRIVACY_MODE=1` (the default):

- Raw bearer tokens are never stored; only a SHA-256 hash is stored.
- Admin passwords are stored as salted scrypt hashes, never plaintext.
- Usage records contain metadata only: endpoint, principal ID, status code, latency and timestamp.
- `/v1/*` responses are marked `Cache-Control: no-store`.
- The SQLite database is set to permission `0600` where the filesystem supports it.
- Security headers are added to HTTP responses.
- AI3 does not write prompts, responses or tokens to application logs.

AI3 temporarily holds the request in memory while forwarding it to the selected model backend. The configured upstream model provider can have its own logging or retention policy; local Ollama inference keeps inference inside the server.

## Application-layer DDoS protection

AI3 includes a small first line of defense for internet-facing API abuse:

- Per-IP request rate limit: `AI3_DDOS_IP_RPM` (default 120/minute).
- Per-IP concurrent request limit: `AI3_DDOS_MAX_CONCURRENT_PER_IP` (default 20).
- Maximum request body size: `AI3_MAX_REQUEST_BYTES` (default 2,000,000 bytes).
- Excess traffic receives HTTP `429` with `Retry-After` instead of being forwarded to the model.
- Oversized requests receive HTTP `413`.
- The limiter is bounded in memory and cleans stale client entries.

This is **not** a replacement for upstream DDoS protection. For a public server, combine AI3 with a firewall and a properly configured reverse proxy/CDN or DDoS protection service. A volumetric attack that saturates the network connection cannot be stopped by application code after it reaches the host.

## Important deployment rule

For an internet-facing installation, put AI3 behind HTTPS/TLS and a firewall or reverse proxy. Do not expose the Ollama management port publicly. The bundled API management service is bound to localhost by default.

Keep these values secret:

- `AI3_ADMIN_KEY`
- `AI3_ADMIN_PASSWORD`
- generated `ai3_...` access tokens
- the chat encryption key
- any optional upstream `AI3_LLM_API_KEY`

Never commit `.env`, real tokens, passwords, API keys, encryption keys or database backups containing private information.

## Token safety

If a token is exposed, revoke it immediately and create a replacement. Prefer short-lived tokens where practical and use token rotation for long-lived agents.

## Backups

The database may contain encrypted chat ciphertext, account configuration and usage metadata. Protect backup files like the database itself. **Back up the encryption key separately and with stronger access controls than the database whenever possible.**

## Limits

Set request and daily limits for shared/public installations. `0` means unlimited in AI3's runtime limit configuration. The DDoS guard intentionally has a non-zero default because completely disabling abuse protection is unsafe for a public endpoint.

## What this does not protect against

AI3 cannot protect data from a fully compromised host, a malicious administrator with access to the encryption secret, malware on a client device, a stolen key, or a model provider that independently stores submitted data. For stronger protection, combine AI3 with full-disk encryption, OS hardening, HTTPS, restricted network access, regular updates and protected backups.
