# Upstream Adoption Policy

Rasputin benefits from open-source software and should make that relationship
transparent, reviewable, and sustainable.

## Before adopting upstream work

Every proposal must identify:

- The user problem being solved.
- The upstream project, repository, commit, and relevant paths.
- Whether the proposal adopts an idea, protocol, dependency, or source code.
- The upstream license and Rasputin compatibility decision.
- Expected security, maintenance, migration, and bundle impact.
- Why reuse is better than an existing Rasputin component or a smaller library.
- Acceptance tests and a removal or replacement strategy.

## Source-code imports

Source imports require:

1. An approved Rasputin project license.
2. A compatible upstream license.
3. Preserved copyright, license, and modification notices.
4. A bounded commit containing the import and provenance record.
5. Rasputin-facing tests and documentation.
6. An entry in `docs/upstream/ADOPTION_REGISTER.md`.

Do not flatten upstream history into an unattributed “refactor.” Translation to
another programming language is still an adaptation and follows the same rules.

## Dependencies

Dependencies are reviewed on their own merits. Record:

- Direct and transitive license concerns.
- Release and maintenance activity.
- Known vulnerabilities and security posture.
- Runtime privileges and network access.
- Package and installer impact.

Prefer maintained, focused libraries over importing an application's internal
subsystem.

## Product inspiration

Abstract product ideas can be independently implemented. The design record
should still name important inspiration and explain how the Rasputin outcome
differs. This keeps the project honest and helps contributors understand the
decision.

## Contributing upstream

When a fix is generally useful to an upstream project:

- Open a focused issue or pull request when practical.
- Avoid Rasputin-specific dependencies.
- Link the contribution from the adoption register.
- Respect upstream contribution and signing requirements.

## Review checklist

- [ ] Provenance is recorded.
- [ ] License compatibility is recorded.
- [ ] Required notices are present.
- [ ] Security and permissions are reviewed.
- [ ] Existing Rasputin architecture was considered.
- [ ] Acceptance tests pass.
- [ ] Documentation describes the resulting behavior.
- [ ] Upstream contribution was considered.
