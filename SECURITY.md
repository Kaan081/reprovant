# Security model — v0.2 experimental package

This is **not** a production-safe agent or an authorization/security boundary. It runs deliberately destructive SQL operations only inside new, randomly named schemas. Never give it production credentials or an existing shared database endpoint.

## Defaults and tested controls

- PostgreSQL requires `PIPELINE_TEST_DSN` **and** explicit CLI `--postgres`; the DSN is no longer a command-line argument. Use a process-local environment variable or secret manager; do not paste passwords into source, chat, screenshots, CI logs or shell history. Environment variables may still be visible to local admins/process-inspection tools.
- The v0.2 DSN allowlist is only `postgresql+psycopg://acceptance:<password>@localhost:54329/acceptance` (or loopback IP); rejects remote hosts, other roles, other DBs, nonstandard ports, URL query options and other SQLAlchemy drivers. This prevents common accidental target mistakes but does **not** prove a hostile local service is disposable.
- Compose binds only IPv4 loopback, initializes an ephemeral tmpfs-backed database, requires an externally supplied random password and has no embedded reusable credential; `docker compose down` deletes container. Compose security flags are defense-in-depth, not host isolation guarantees.
- SQL operations use SQLAlchemy bound parameters. Only an untrusted SQL identifier *generated internally* from UUID hex is interpolated for schema creation/destruction.
- PostgreSQL connection timeout = 5s, statement timeout = 10s and lock timeout = 3s, with SQL parameter hiding. These are safeguards for development tests, not a complete resource/billing limit.
- Reports have a documented synthetic schema, exclude connection URLs and credentials by construction. Atomic write uses private temporary file permissions on POSIX; Windows filesystem ACLs still govern access. Do not assume customer payloads can be written safely into reports.
- `.gitignore` and `.dockerignore` block `.env`, `*.env`, nested variants, credentials, private keys, dumps, logs, virtual environments, build/test output. **Ignore rules do not untrack previously committed files** and do not stop a forced `git add -f`. Scan Git history separately.
- Only project-owned disposable objects are created. No client filesystem scan, arbitrary SQL execution, network crawler, `eval`, pickle loading or production mutations.

## Still needed before handling external/corporate data

External authz and human consent; sandbox provisioning; privilege-separated DB roles; proof of isolation from adversarial input; dependency pinning/lockfiles and supply-chain scans; log/trace redaction; PII retention policy; signing/attestation of provenance; safe customer-code adapters; concurrent PostgreSQL integration; threat-model review; independent pen-test where appropriate. No public deployment or production credentials.

## Operational preflight

1. Work only in a dedicated disposable directory on a trusted workstation.
2. Check `git status --short` / `git ls-files` for any tracked secrets; rotate any leaked value.
3. Generate a fresh strong `PIPELINE_DB_PASSWORD` and keep it out of code and Git history.
4. Start Docker Compose only after confirming bound port 54329 is unused.
5. Set `PIPELINE_TEST_DSN` in the **current** process; remove it after testing.
6. Review the resulting evidence; do not share third-party data or connection details.
