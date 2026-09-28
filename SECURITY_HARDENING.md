# Security changes for the existing service

The service still uses API keys. Give each browser/client its **own** key via
`AGENT_API_KEYS` in the cloud secret store, for example
`{"client_a":"<random-secret-a>","client_b":"<random-secret-b>"}`. Generate
each value with a cryptographic random generator. Keep `AGENT_API_KEY` for the
operator only; never distribute it to customers. Change or remove a client's
key in the secret store to revoke access.

The default `STRICT_API_IDENTITY=false` preserves the lab requirement:
`X-User-Id` selects the identity when the owner key is used. Set
`STRICT_API_IDENTITY=true` **only for a separate commercial deployment** to
ignore that header and bind the owner key to `owner`. Dedicated client keys are
always bound to their configured identity. In strict mode, new conversations
use separate `history:v2:`, `ratelimit:v2:` and `cost:v2:` namespaces. Old Redis history was indexed by
client-supplied IDs, so ownership cannot be proven; do not automatically assign
or delete it.

The browser keeps its key only in memory and sends requests to its own origin.
Reloading the page clears the key. This reduces persistence but does not make
browser-held keys immune to XSS or browser compromise. The service sends CSP,
HSTS and MIME-sniffing protection headers. For a full customer login product,
replace browser API keys with OIDC and server-side sessions.
If the old UI stored a key in `sessionStorage`, close that browser tab and
rotate the key if it was shared or exposed; this change does not read the old
entry.

Redis is bound only to the host loopback interface by Docker Compose, so local
Python exercises still work without exposing port 6379 publicly. In cloud deployment,
confirm Redis remains private and that backups and provider-level spending
limits/alerts are enabled. The application reserves estimated cost before the
AI call and keeps that reservation when the provider outcome is uncertain;
reconcile such reservations with the provider bill. Verify the configured
DeepSeek token prices after any provider pricing change.

Run `pytest -q tests/test_security_hardening.py` and the original CP1–CP5
checks. Keep the lab deployment in lab mode to satisfy the exercise contract;
use strict mode only after staging validation for a separate customer service.
No secret values belong in Git, logs or docs.
