# AI Agent Baseline / Buyer Gate — product hypothesis, not validation

**Status (2026-11-01): HOLD on product commercialization.** The current suite is a synthetic failure-shape demonstration, *not* a general-purpose worker validator and not an independent business oracle. The corrected behavior is conventional SQLAlchemy/PostgreSQL practice.

## Competitive baseline (do not assert "AI cannot do this")

- AI coding agents can read code, run tests, repair bugs, and submit PRs; some can orchestrate databases when given access. An agent on its own may write the same acceptance tests.
- Celery documents ACK/retry/idempotency semantics; Temporal and DBOS provide durable workflow primitives. Testcontainers gives real DB integration fixtures. Antithesis explicitly offers automated fault injection and deterministic replay, including an agent-assisted workflow. All are substantial baselines, not strawmen.
- A proposed niche is an **existing application running custom/legacy Python workers with PostgreSQL**, for which migration to a durable workflow framework is unwanted or impractical, and an independent, reviewable acceptance gate is needed.

## Which buyers and triggers are plausible?

**Buyer hypothesis:** agency or in-house lead maintaining multiple Python+PostgreSQL worker systems, with recurring duplicate business effects, stale terminal state, or ambiguous commit/replay after deployment. Buyer needs an **independent, repeatable PASS/FAIL/INCONCLUSIVE report** for a named business invariant.

**Triggers to interview about:** a recent incident or release regression, duplicated customer-visible effects, an unresolved incident with no reliable reproducer, audit/client-delivery acceptance needing evidence, or multiple upgrades requiring repeatable regression gates.

**Do not assume:** cost of a similar engineering job implies software-license demand. If a customer already uses Temporal/DBOS well or an agent+pytest can do the whole task quickly, this niche may be absent.

## Experiment with a fair agent baseline

Pick two **independent, legally permitted** codebases reproducing the *same narrow failure family*, not our own intentionally broken demo alone. Give both arms the same source, environment, budget, time cap, bug description, access to tooling, and acceptance criteria.

- **A:** competent engineer + a coding agent + ordinary pytest, SQLAlchemy, Postgres/Testcontainers. Agent may write and run any needed tests.
- **B:** same engineer/agent/tooling + a *reusable* acceptance runner or adapters we would build. Do not count B's initial one-off implementation time as free.
- **Independent oracle:** the real app owner specifies the business invariant and externally observable outcomes; the agent cannot self-certify by writing both the code and a permissive test that marks itself green.
- **Fault matrix:** normal success, DB commit then worker termination before ACK, replay of same logical event, two competing workers, stale writer after terminal state, validation failure before durable update. Record *actual process death* separately from simulated exceptions, and report tests not run.
- **Measure:** minutes to first reproducible failing case; total engineering minutes incl. environment/setup/adapters; unique real bugs found; false positives; clean rerun rate; CI time; lines of repo integration code; maintenance on a second structurally different app. Track both developer and machine/agent cost.
- **Evidence contract:** target repo revision, worker entrypoint, Postgres version, artifact hashes, scenario matrix, operator-provided invariant, reproduction command, stdout/stderr redacted, all failures, and explicit PASS/FAIL/INCONCLUSIVE per scenario.

### Hypothesis gates (thresholds are targets, not observed data)

- **Technical gate:** two independent real-code reproductions, not only toy model; no hidden requirement for production credentials; no accidental production mutation.
- **Differentiation gate:** target >=30% less total human effort **including setup and adapter writing** than A, or a material reproducible failure class that A misses, with no increase in unacceptable false positives. If a normal agent+pytest performs as well, KILL reusable-tool hypothesis or offer only a scoped service.
- **Buyer gate:** at least two actual maintainer calls with recent incident examples and an existing budget/time cost; one owner-approved sanitized pilot; stronger evidence is an explicit *paid* pilot and a named acceptance criterion. Do not count positive generic feedback as purchasing intent.

## What might customers buy first?

Sell a **bounded verification engagement**, not "an AI-proof reliability engine": for one named worker, identify replay/duplicate-effect risk, build a safe sandbox reproduction, verify after-fix evidence, deliver a report and a reproducible acceptance test. Agree on business semantics, rights, scope, confidentiality, and payment **before touching real customer source**. Do not claim production certification or automated repair.

**No published pricing or promised ROI** here: ask the buyer's current cost of repeated incidents and its outsourcing budget first. If they will not pay to solve this failure family, the software-product gate remains closed.

## Sources (read before implementation)
- Celery task acknowledgments: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- DBOS transactions: https://docs.dbos.dev/python/tutorials/transaction-tutorial
- Temporal Python testing: https://docs.temporal.io/develop/python/best-practices/testing-suite
- Testcontainers Python/PostgreSQL: https://docs.docker.com/guides/testcontainers-python-getting-started/
- Antithesis fault injection/replay: https://antithesis.com/docs/introduction/how_antithesis_works/
- GitHub Copilot agents: https://docs.github.com/en/copilot/responsible-use/agents
