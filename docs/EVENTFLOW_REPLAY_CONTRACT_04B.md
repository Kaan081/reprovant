# Eventflow 04B: replay-contract integration (manual live-worker experiment)

**Status: implementation prepared; NOT live-verified until GitHub Actions workflow_dispatch evidence exists.** Do not describe this as external proof until the real workflow completes and both artifacts are inspected.

## What this changes

This integrates the `pipeline_acceptance.replay_contract` v0 engine from PR #13 with the same **pinned** external educational application and real-worker architecture used by 03A/03B. It does not rewrite, re-run automatically, or modify old 03A/03B experiments. The source is checked out at `juneja-varun/eventflow` SHA `c08455d626d5e1c316d932c4da0652086fb1b19e`.

A **manual** workflow has two isolated GitHub-hosted jobs. Each uses its own disposable PostgreSQL 16, Redis 7, Celery worker (non-eager), and Django app. Only the guarded job modifies a disposable external checkout, replacing `orders/tasks.py` with the already-attributed guarded demonstration from 03B.

1. Confirm source SHA, expected changed-path set, disposable environment, worker ping and non-eager mode.
2. Subscribe to Redis pub/sub; run the first task and verify SUCCESS, `confirmed` state and exactly **one** observed `order.confirmed` event.
3. Advance the order to `shipped` using a conditional update; read the baseline with the new `ReplayAdapter`.
4. Send the **second** Celery task explicitly, await successful completion, observe the status and new confirmation events.
5. The `ReplayContract` verifies that state is preserved and `order.confirmed` event count does not grow.
6. A separate classifier requires **both** worker attestation and precisely the expected snapshot/check shape: original source `VERIFIED_RED_CONTROL`, guarded source `VERIFIED_GUARDED_GREEN`. All other outcomes fail closed.

The adapter reuses existing 03A pinned revision, worker ping, Redis event collection and safe disposable environment helper functions. It uses no new runtime dependency and does not touch customer/production infrastructure. It **does not** independently attest sandbox isolation beyond the checked environment/provenance, and a fixed event-listening window does not prove absence of delayed events.

## What this is NOT

- This is a manually induced *second task delivery*, not actual broker redelivery after ACK loss or worker crash.
- Neither Redis pub/sub nor database writes are atomically guaranteed end to end.
- `RED`/`GREEN` here demonstrate only one observed state invariant for one external demo and one source-specific adapter.
- This is not an SDK that discovers arbitrary bugs, nor proof of product differentiation or commercial demand.
- The two jobs use separate isolated databases, so results are controlled but not literally the same running application state.

## Commands (only AFTER merging the PR containing the workflow)

```powershell
gh workflow run external-eventflow-replay-contract-04b.yml --repo kaanbartubozkurt/reprovant --ref main
gh run list --repo kaanbartubozkurt/reprovant --workflow external-eventflow-replay-contract-04b.yml --limit 3
# Use the actual NEW 04B run ID, then:
gh run watch <run-id> --repo kaanbartubozkurt/reprovant --exit-status
```

Do not claim 04B success without both job results and their separately uploaded `eventflow-replay-contract-04b-upstream` and `eventflow-replay-contract-04b-guarded` evidence artifacts. If either is inconclusive, report that limitation; do not greenwash an earlier 03A/03B success.

## Next business gate

Compare **total** setup, adapter and review hours against a conventional, app-specific pytest baseline on the same task. A generic evaluator is not a meaningful differentiator if the per-application adapter remains the hard part. The next independent owner-approved application remains an unverified goal.
