# AI3 Security & Privacy

AI3 is designed for self-hosted, privacy-first operation. No software can honestly guarantee that nobody can ever steal data, but AI3 reduces the amount of sensitive data it stores and adds basic protections.

## Privacy by default

With `AI3_PRIVACY_MODE=1` (the default):

- Chat request bodies are not written to the AI3 database.
- Chat response bodies are not written to the AI3 database.
- Raw bearer tokens are never stored; only a SHA-256 hash is stored.
- Admin passwords are stored as salted scrypt hashes, never plaintext.
- Usage records contain metadata only: endpoint, principal ID, status code, latency and timestamp.
- `/v1/*` responses are marked `Cache-Control: no-store`.
- The SQLite database is set to permission `0600` where the filesystem supports it.
- Security headers are added to HTTP responses.

AI3 temporarily holds the request in memory while forwarding it to the selected model backend. The configured upstream model provider can have its own logging or retention policy; local Ollama inference keeps inference inside the server.

## Important deployment rule

For an internet-facing installation, put AI3 behind HTTPS/TLS and a firewall or reverse proxy. Do not expose the Ollama management port publicly. The bundled API management service is bound to localhost by default.

Keep these values secret:

- `AI3_ADMIN_KEY`
- `AI3_ADMIN_PASSWORD`
- generated `ai3_...` access tokens
- any optional upstream `AI3_LLM_API_KEY`

Never commit `.env`, real tokens, passwords, API keys or database backups containing private information.

## Token safety

If a token is exposed, revoke it immediately and create a replacement. Prefer short-lived tokens where practical and use token rotation for long-lived agents.

## Backups

Backups can contain account configuration and usage metadata. Protect backup files like the database itself. If encrypted backups are required, use an encrypted filesystem or an established encrypted backup solution rather than inventing custom cryptography in the application.

## Limits

Set request and daily limits for shared/public installations. `0` means unlimited in AI3's runtime limit configuration.

## What this does not protect against

AI3 cannot protect data from a fully compromised host, a malicious administrator with filesystem access, a stolen server disk without encryption, malware on a client device, or a model provider that independently stores submitted data. For stronger protection, combine AI3 with full-disk encryption, OS hardening, HTTPS, restricted network access, regular updates and protected backups.

The privacy approach follows the general OWASP recommendation to avoid logging credentials, access tokens and sensitive personal data and to protect log integrity and access.