# Public repository audit - historical release gate and remaining checks

**Current status (2026-11-02):** The repository is already **public**. This page preserves the historical publication checklist; unchecked items remain unverified. A public repo and passing CI do **not** certify the full Git/Actions history or suitability for production.

### Verified snapshot — narrow scope

- Security pinning PR [#20](https://github.com/kaanbartubozkurt/reprovant/pull/20) merged at `4044db2`; its post-merge main CI [run](https://github.com/kaanbartubozkurt/reprovant/actions/runs/41404612533) succeeded.
- Owner-run local `gitleaks 8.30.1 git . --log-opts="--all" --redact` found zero findings over 21 reachable commits (~291 KB) on 2026-11-02. This is **not** a review of GitHub Actions logs/artifacts, other clones, unreachable commits, or every possible secret.
- This licensing change is a proposal until its PR is merged: original/author-owned code under Apache-2.0; preserve modified Eventflow MIT notice separately.
- Branch protection was not enabled in the last checked repository settings; check current rules and audit other historical disclosures before any wider claims.

## Identity and scope

- [ ] Check the proposed **Reprovant** name for GitHub, PyPI, trademarks and domains; availability not guaranteed by preliminary search.
- [ ] Keep Python `pipeline_acceptance` import and package entry points unchanged. Repository rename is cosmetic, not a package migration.
- [x] Propose Apache-2.0 for original/author-owned code in a separate licensing PR; preserve the Eventflow MIT attribution for modified `tasks_guarded.py` (review before merge).
- [ ] Ensure README lists the verified 02A / 03A / 03B results and their scope limitations.

## Security & privacy

- [ ] On the **actual current local Git clone**, fetch all refs and scan **entire reachable Git history**, not only HEAD, for secrets (`gitleaks git . --log-opts=--all --redact` or equivalent). Rotate credentials if ever committed; removal from HEAD alone does not remove history.
- [ ] Inspect all tracked and historical filenames for `.env`, credentials, dumps, local evidence, logs, private keys, `.zip` and customer data.
- [ ] Review GitHub Actions **all previous runs, uploaded artifacts, workflow/job logs**, branch/tag history, and PR comments for sensitive data. On private→public, GitHub says prior Actions history/logs become visible to everyone.
- [ ] Review collaborator permissions, branch protection, package/release assets, GitHub Pages, readmes/linked URLs, third-party license conditions, and repo rulesets. Confirm `docs/THIRD_PARTY_NOTICES.md` matches the pinned upstream Eventflow LICENSE. Any removed push rulesets must be reconsidered after visibility change.
- [ ] Check no claims imply production certification, automatic diagnosis, commercial customers, or ACK-loss proof.

## Original pre-publication release plan (historical; steps already occurred)

1. Land docs-only case-study PR while repo is still private; run existing CI. Commit only the files intentionally selected, **never** `git add -A` from a working tree with artifacts.
2. Rename the repository from `python-pipeline-acceptance` to `reprovant`, then set the canonical remote with `git remote set-url origin https://github.com/kaanbartubozkurt/reprovant.git`.
3. Confirm redirected historical evidence links and check the CI workflows after rename. GitHub redirects most repo links but has exceptions for published Actions and GitHub Pages.
4. Re-run privacy review. **Only then**, if approved, change to public in GitHub Settings → Danger Zone → Change visibility. This is a deliberate visibility/security decision, not an automatic next step.
5. Verify public README and permissions externally; public repository is a case study, not a product launch.

## If any historical secret or proprietary artifact is found

**STOP** public conversion. Do not paste the secret into chats or issue comments. Rotate/revoke the credential, determine exposure and affected refs/logs, and decide whether to clean history safely or create a new clean public showcase repository. Deleting the file now, or ignoring it, does not erase Git history.
