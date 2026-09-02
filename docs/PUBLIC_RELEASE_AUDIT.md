# Rasputin Public Release Audit

> **Audit started:** July 24, 2026
> **Audit refreshed:** September 1, 2026
> **Branch:** `main`
> **Status:** Public preview repository; local safety checks pass; stable release clearance remains open

## Executive result

The current tracked tree passes Rasputin's repository safety check and contains
no tracked runtime data, generated build output, private-key files, databases,
or local model weights.

The repository is public and licensed under AGPL-3.0-or-later. Windows x64
Desktop is the supported preview surface. Preview publication does not equal
stable-release clearance: contribution policy, dependency inventory, signing,
update delivery, and successful remote security checks remain open.

## Current-tree checks

| Check | Result |
|---|---|
| `scripts/check-repo-safety.ps1` | Pass |
| Tracked files | 375 |
| Tracked `data/`, build, distribution, virtualenv, Playwright, or `node_modules` paths | 0 |
| Tracked private-key, certificate, database, or log extensions | 0 |
| Tracked local screenshots covered by the audit patterns | 0 |
| Tracked `.env` files | `.env.example` only |
| Tracked model weights | 0 |
| Tracked file larger than 5 MB | 0 |
| Git object database | Approximately 7 MB total (`6.57 MiB` packed plus loose objects) |

`backend/models/secrets.py` matched the filename audit because it is the
application's secret-storage implementation, not a secret file.

## History checks

Three server log paths existed in the first repository commit:

- `server.err.log`
- `server.node.log`
- `server.out.log`

All three blobs are zero bytes, so the inspected historical copies contain no
log content. They should still be included in any final history-cleanliness
review so future maintainers understand why the paths appeared.

A history-wide filename-only scan for common high-confidence secret formats
found no matches for:

- PEM/OpenSSH private-key headers.
- AWS access-key IDs.
- GitHub tokens.
- OpenAI-style secret keys.
- Slack tokens.
- Google API keys.

This heuristic scan is not a substitute for Gitleaks or an equivalent dedicated
scanner.

## Repository identity

| Item | Current value |
|---|---|
| Remote | `https://github.com/Shingenn5/Rasputin.git` |
| Package author | `Shingenn5` |

The README and installers consistently reference the current GitHub repository.

## Tooling gaps

None of these dedicated scanners were installed during the initial audit:

- Gitleaks.
- TruffleHog.
- detect-secrets.

The `.github/workflows/repository-safety.yml` workflow adds
full-history Gitleaks scanning on pushes, pull requests, and manual runs, plus
GitHub dependency review for pull requests. Earlier Windows-hosted runs failed
while the Gitleaks action fetched an unavailable Windows archive; the workflow
now uses Ubuntu and needs a successful remote run after publication. Before a
stable release:

1. Run and review the new workflow remotely; local heuristic checks do not
   substitute for its first successful full-history scan.
2. Generate a dependency license inventory for Python, npm, bundled native engines, and the
   git submodule.
3. Add dependency vulnerability scanning.
4. Decide whether generated installers receive an SBOM and provenance
   attestation.
5. Confirm that public issue attachments and test fixtures cannot enter
   workspace/runtime data paths.

## Decisions blocking a supported stable release

1. DCO versus CLA contribution policy.
2. Copyright and maintainer governance.
3. Code signing and automatic update-channel policy.
4. Vulnerability-reporting contact and response-time commitments.
5. Which AGPL-compatible Odysseus source adoptions are worth their maintenance
   cost.

## Current clearance

| Area | Status |
|---|---|
| Current tracked tree | Provisionally clear |
| High-confidence history heuristic | Provisionally clear |
| Dedicated full-history secret scan | Workflow host fixed locally; successful remote run pending |
| Dependency vulnerability review | Workflow added; first pull-request run pending |
| Dependency license inventory | Pending |
| Vulnerability scan | Pending |
| Project license | AGPL-3.0-or-later selected and added |
| Public governance documents | Initial set added; contribution-signing policy pending |
| Feature baseline | In progress; see `RASPUTIN_IMPLEMENTATION_LEDGER.md` and `RASPUTIN_V1_RELEASE_CONTRACT.md` |

Do not rewrite history, publish a stable release, or import Odysseus source
without recorded provenance and compatibility review.
