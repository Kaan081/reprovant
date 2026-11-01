# Public release gate — must be completed BEFORE changing repository visibility

**Current status:** NOT CLEARED. This document is a checklist, not evidence that the private repo or its history is safe to publish.

## Identity and scope

- [ ] Check the proposed **Reprovant** name for GitHub, PyPI, trademarks and domains; availability not guaranteed by preliminary search.
- [ ] Keep Python `pipeline_acceptance` import and package entry points unchanged. Repository rename is cosmetic, not a package migration.
- [ ] Decide whether to add a license for original code (there is no root LICENSE in the archived v0.2.1 snapshot); do not assume permission to distribute third-party source.
- [ ] Ensure README lists the verified 02A / 03A / 03B results and their scope limitations.

## Security & privacy

- [ ] On the **actual current local Git clone**, fetch all refs and scan **entire reachable Git history**, not only HEAD, for secrets (`gitleaks git . --log-opts=--all --redact` or equivalent). Rotate credentials if ever committed; removal from HEAD alone does not remove history.
- [ ] Inspect all tracked and historical filenames for `.env`, credentials, dumps, local evidence, logs, private keys, `.zip` and customer data.
- [ ] Review GitHub Actions **all previous runs, uploaded artifacts, workflow/job logs**, branch/tag history, and PR comments for sensitive data. On private→public, GitHub says prior Actions history/logs become visible to everyone.
- [ ] Review collaborator permissions, branch protection, package/release assets, GitHub Pages, readmes/linked URLs, third-party license conditions, and repo rulesets. Any removed push rulesets must be reconsidered after visibility change.
- [ ] Check no claims imply production certification, automatic diagnosis, commercial customers, or ACK-loss proof.

## Release order (only AFTER every gate is independently approved)

1. Land docs-only case-study PR while repo is still private; run existing CI. Commit only the files intentionally selected, **never** `git add -A` from a working tree with artifacts.
2. Rename repo with `gh repo rename reprovant -R Kaan081/python-pipeline-acceptance`, then `git remote set-url origin https://github.com/Kaan081/reprovant.git`.
3. Confirm redirected historical evidence links and check the CI workflows after rename. GitHub redirects most repo links but has exceptions for published Actions and GitHub Pages.
4. Re-run privacy review. **Only then**, if approved, change to public in GitHub Settings → Danger Zone → Change visibility. This is a deliberate visibility/security decision, not an automatic next step.
5. Verify public README and permissions externally; public repository is a case study, not a product launch.

## If any historical secret or proprietary artifact is found

**STOP** public conversion. Do not paste the secret into chats or issue comments. Rotate/revoke the credential, determine exposure and affected refs/logs, and decide whether to clean history safely or create a new clean public showcase repository. Deleting the file now, or ignoring it, does not erase Git history.
