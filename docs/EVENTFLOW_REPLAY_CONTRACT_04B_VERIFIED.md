# Reprovant 04B — Verified External Worker Evidence

**Verified date:** 2026-11-01
**GitHub Actions run:** https://github.com/kaanbartubozkurt/reprovant/actions/runs/41331192111
**Reprovant run commit:** `6ff1a7e416ce9b458138f645d7a34e4934c3a795`
**Pinned external Eventflow revision:** `c08455d626d5e1c316d932c4da0652086fb1b19e`
**Source:** `juneja-varun/eventflow` (educational example)

## Results verified from the two uploaded GitHub Actions artifacts

| Check | Upstream source | Guarded source |
| --- | --- | --- |
| Workflow job | Success | Success |
| Outer classifier | `VERIFIED_RED_CONTROL` | `VERIFIED_GUARDED_GREEN` |
| Replay contract | `RED` | `GREEN` |
| State before repeat dispatch | `shipped` | `shipped` |
| State after repeat dispatch | `confirmed` | `shipped` |
| `order_confirmed` count before | 1 | 1 |
| `order_confirmed` count after | 2 | 1 |
| Both first and second tasks reported `SUCCESS` | Yes | Yes |
| Two distinct task IDs attested | Yes | Yes |
| Independent non-eager Celery worker attested | Yes | Yes |
| Upstream modified files | None | `orders/tasks.py` |

**Upstream artifact:** `eventflow-replay-contract-04b-upstream`, ID `13093611459`
**Guarded artifact:** `eventflow-replay-contract-04b-guarded`, ID `13093565849`

Both jobs ran with separate disposable PostgreSQL 16 + Redis 7 services and an actual Celery worker. Both artifacts contain `report.json`, worker logs, source hash, source change list, and provenance.

## Interpretation

- The original upstream code was observed regressing an order from `shipped` to `confirmed` after **manual** repeat dispatch and emitting a second observed `order.confirmed` event.
- The narrow guarded modification preserved `shipped` and the single observed confirmation event during the same scenario.
- The application-neutral Reprovant replay-contract v0 evaluator distinguished the two outcomes as `RED` and `GREEN`.
- This is new integration evidence **for the reusable evaluator on the external app**, not a newly discovered failure; the existing 03A and 03B experiments had already established the behavior.

## Boundaries and next decision

This does **not** verify natural broker redelivery, lost ACK, worker death, end-to-end exactly-once delivery, all delayed Redis events, arbitrary application support, production safety, customer authorization, paid demand, or an advantage over application-specific pytest tests.

The Eventflow adapter and runner remain application-specific integration work. Before declaring a product advantage, compare their total engineering and review effort against an ordinary pytest baseline on the same acceptance condition, and validate reusable parts in a **second independent owner-authorized application**.

GitHub Actions showed non-failing Node.js runtime deprecation and runner-image migration notices. They are maintenance signals, not failed 04B acceptance checks.
