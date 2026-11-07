# Reprovant — Python worker failure-acceptance experiments

> **Research case study — not a commercial product, automatic validator, or production certification.** `reprovant` is the repository/working brand; the existing installed distribution and `pipeline_acceptance` Python imports are unchanged.

**Verified external results (2026-11-01):** baseline [02A](https://github.com/Kaan081/reprovant/actions/runs/41316392717) used **ordinary pytest** and disposable PostgreSQL on an educational ETL application (**4/4 PASS**). Eventflow [03A](https://github.com/Kaan081/reprovant/actions/runs/41318068548) showed a state regression and duplicate event on **manual task re-enqueue** through a real Celery worker; Eventflow [03B](https://github.com/Kaan081/reprovant/actions/runs/41319161073) showed a narrow guarded GREEN using standard Django ORM behavior. **None of these proves automated issue discovery, production redelivery after ACK loss, a paid customer, or an advantage over AI + pytest.**

Read the [external evidence case study](docs/REPROVANT_EVIDENCE_CASE_STUDY.md), [third-party attribution and license notice](docs/THIRD_PARTY_NOTICES.md), and [publication audit checklist](docs/PUBLIC_RELEASE_GATE.md) for outstanding release checks.

**License:** Original/author-owned Reprovant materials are available under [Apache License 2.0](LICENSE). The Eventflow-derived example in `experiments/eventflow_guarded/tasks_guarded.py` retains its upstream **MIT** attribution and license terms; see [third-party notices](docs/THIRD_PARTY_NOTICES.md). This is a research portfolio and not a production-safety certification or a claim of ownership over upstream code.

---

## Archived v0.2.1 synthetic experiment and local usage

> **Status: Technical experiment, NOT a product, customer-validated solution, subscription, production repair, or certification.**

An intentionally broken Python worker model and a corrected implementation using SQLAlchemy Core and SQL database primitives. It demonstrates three real *failure shapes* in a synthetic, disposable environment:

| Failure | Legacy (deliberately broken) | Guarded baseline |
|---|---|---|
| Commit succeeds, ACK lost, task redelivered | Durable effect duplicated | DB uniqueness + `ON CONFLICT DO NOTHING` gives one effect |
| Stale worker updates after `SUCCEEDED` | Terminal state becomes `RUNNING` | Conditional update preserves `SUCCEEDED` |
| Bad dataset fails validation | Previously good dataset replaced | Validate before transaction; no durable changes |

The corrected implementation is **standard PostgreSQL/SQLAlchemy engineering**, not yet evidence that a paid standalone tool is necessary. There is no automated client-code adapter or proven saving versus a developer writing their own pytest tests.

## Quick start (runs now, no Docker required)

Python 3.10+, SQLite-backed local smoke test:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
python -m pipeline_acceptance.demo --output proof-report.json
```

The test suite includes the original 8 SQLite behavior tests, one PostgreSQL-only concurrency test (skipped unless explicitly enabled), and security regression tests. Counts can change; trust the actual test output. By default, the tests use SQLite **when `PIPELINE_TEST_DSN` is unset**. Setting `PIPELINE_TEST_DSN` explicitly opts the entire pytest session into disposable PostgreSQL (including the startup preflight). Unlike `demo.py`, pytest uses this environment variable directly.

To see pre-fix bugs as **three expected failing tests**:

```bash
python -m pytest -q tests/legacy_red_cases.py
# Expected exit code: 1, because three assertions demonstrate broken behavior.
```

## Security hardening and PostgreSQL integration (actual target)

See [SECURITY.md](SECURITY.md) for the security boundary and [market comparison](docs/MARKET_POSITION.md) for the product decision. The `.env`, `*.env`, nested forms, private keys, logs and dumps are ignored by Git/Docker; old tracked files need manual untracking/rotation. Never commit secrets.

**PostgreSQL is intentionally allowed only on a disposable local endpoint**: `acceptance` role / database, localhost port `54329`. No remote or production DSNs. CLI secrets in arguments are prohibited; use environment variables. You need Docker Desktop/Compose and Python + psycopg. This experiment creates an isolated random schema then removes it; only run it on an empty disposable database.

### Troubleshooting: missing Docker / database unreachable

v0.2.1 checks the disposable local PostgreSQL service **once** when PostgreSQL is explicitly requested. If Docker is absent or the port is closed, pytest stops with one clear preflight message instead of accumulating per-test connection timeouts. `--postgres` demo likewise fails fast. No database credentials are printed by this preflight. This is an ergonomics fix, **not a business differentiator**.

If Docker is not running, clear the opt-in first:

```powershell
Remove-Item Env:PIPELINE_TEST_DSN -ErrorAction SilentlyContinue
.\.venv\Scripts\python -m pytest -q
```

Only enable PostgreSQL **after** `docker compose up -d --wait postgres` succeeds. If you changed a password after starting a disposable container, tear it down and recreate it with the new password; don't assume changing the environment variable changes the existing database role.

PowerShell, execute in this project directory:

```powershell
# New secret for each disposable local database; keep it out of files and shell history.
$env:PIPELINE_DB_PASSWORD = py -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up -d --wait postgres
.\.venv\Scripts\python -m pip install -e '.[test,postgres]'
$env:PIPELINE_TEST_DSN = "postgresql+psycopg://acceptance:$($env:PIPELINE_DB_PASSWORD)@localhost:54329/acceptance"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pipeline_acceptance.demo --postgres --output proof-report.json
docker compose down
Remove-Item Env:PIPELINE_TEST_DSN
Remove-Item Env:PIPELINE_DB_PASSWORD
```

Bash, macOS/Linux:

```bash
export PIPELINE_DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d --wait postgres
python -m pip install -e '.[test,postgres]'
export PIPELINE_TEST_DSN="postgresql+psycopg://acceptance:${PIPELINE_DB_PASSWORD}@localhost:54329/acceptance"
python -m pytest -q
python -m pipeline_acceptance.demo --postgres --output proof-report.json
docker compose down
unset PIPELINE_TEST_DSN PIPELINE_DB_PASSWORD
```

**If a command fails**, first tear down the disposable container and remove the two environment variables; avoid `docker compose config` in shared logs because it can reveal interpolated secrets. The database uses temporary storage only. This still **does not prove** production safety. PostgreSQL CI jobs and external test workflows have been reported by the repository owner as successful; this archived local quick start is not evidence of production acceptance.

## Artifact details / what proof means

- `tests/legacy_red_cases.py`: intentionally failing tests, not included by default.
- `tests/test_guarded.py`: invariant tests for the guarded implementation.
- `tests/test_security.py`: no-remote-DSN/secret hygiene guardrails, CLI opt-in, bound SQL parameters.
- `SECURITY.md`: threat and configuration boundaries.
- `docs/MARKET_POSITION.md`: competitor baseline and differentiation gates.
- `src/pipeline_acceptance/demo.py`: comparable before/after scenarios; emits JSON with backend, observed values, and evidence scope.
- `compose.yaml`: ephemeral PostgreSQL database; nothing deployed into an existing application.

**Limitations:** Replay-contract GREEN verifies only before/after state and effect counts; `dispatch_completed` does not prove broker delivery or worker execution (`worker_execution_verified` stays false in v0). Synthetic job and dataset model, simplified ACK simulation, no real queue transport, no external side-effect compensation, no crash during COMMIT, no distributed transaction, no multi-tenant/production integration, no real customer data, no performance benchmark. Logical idempotency keys must come from domain rules. Key conflicts fail closed. Validation is a synthetic caller-provided flag, NOT a real dataset validator. Race behavior needs genuine PostgreSQL run. External non-database effects are out of scope.

## Business gate (still HOLD)

Do **not** pitch this as a proven product. Next independent evidence required:
1. Find two distinct real Python+PostgreSQL applications with the *same* expensive failure family.
2. Check whether existing pytest/SQLAlchemy patterns already solve it in similar time.
3. Obtain one authorized sandbox evaluation and, ideally, a funded narrow pilot.

If the work is bespoke, sell a bounded engineering service instead of an imagined reusable platform.

## Real worker process termination: isolated acceptance experiment

The previous `demo.py` uses a synthetic exception. The new `crash_harness.py`
starts a **separate Python process** and has the parent **kill that child** at a
checkpoint. The parent independently queries the disposable database **after**
termination, then replays the job. The known-broken legacy implementation is also run as a **negative control** in pytest: it MUST fail the post-commit replay invariant (2 effects, not 1). The two checkpoints are:

- **Before commit:** an uncommitted insert + status update must roll back; replay creates exactly one effect.
- **After commit, before any ACK:** one durable effect survives; replay does not duplicate it.

Run locally without Docker:

```powershell
.\.venv\Scripts\python -m pipeline_acceptance.crash_harness --output crash-proof-report.json
.\.venv\Scripts\python -m pytest -q
```

With an explicitly configured disposable PostgreSQL test service:

```powershell
.\.venv\Scripts\python -m pipeline_acceptance.crash_harness --postgres --output crash-proof-report.json
```

Security/limits: parent kills **only the child it created**, uses temp-file markers
for deterministic checkpoints, never puts PostgreSQL DSNs/passwords in CLI args,
and checks results via a new DB connection. This is NOT a generic fault-injection
framework, crash-during-COMMIT test, queue ACK implementation, external-payment
exactly-once guarantee, cross-platform production guarantee, or proven advantage
over pytest/AI agents. PostgreSQL integration must pass in CI before claiming it.
