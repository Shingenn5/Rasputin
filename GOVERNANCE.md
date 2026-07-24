# Rasputin Governance

## Current project stage

Rasputin is maintainer-led while it prepares for its first public open-source
release. This document records the initial decision process and should evolve
with the contributor community.

## Roles

### Maintainer

The maintainer:

- Sets product direction and release scope.
- Approves security-boundary and architecture changes.
- Maintains the project license and selects the contribution-signing policy.
- Reviews or delegates pull requests.
- Coordinates vulnerability response and releases.

### Contributors

Contributors may propose features, fixes, documentation, tests, integrations,
and design changes. Sustained contributors may be granted triage or review
responsibilities after demonstrating sound technical judgment and respect for
the project's safety model.

## Decisions

Routine changes are decided through pull-request review. Cross-cutting decisions
use a public architecture decision record or roadmap update covering:

- Problem and constraints.
- Alternatives considered.
- Security and privacy effects.
- Compatibility and migration.
- Acceptance evidence.
- Reversal strategy.

The maintainer has final responsibility during the current stage. Material
disagreement should be documented rather than erased from the decision record.

## Releases

A release requires:

- Passing release gates for supported runtimes.
- A public changelog.
- Known limitations.
- Dependency and attribution review.
- Security and repository-safety checks.
- Reproducible source corresponding to distributed artifacts.

## Upstream relationships

Rasputin will credit upstream work, preserve required notices, and contribute
generally useful fixes back when practical. See
`docs/UPSTREAM_ADOPTION_POLICY.md`.

## Pending governance decisions

- DCO versus CLA.
- Maintainer succession and additional maintainers.
- Versioning and support windows.
- Funding, paid support, or hosted-service policy.
