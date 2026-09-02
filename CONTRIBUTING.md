# Contributing to Rasputin

Thank you for helping build a safer, more capable local AI operations
environment.

> Rasputin is licensed under AGPL-3.0-or-later and currently publishes Windows
> preview builds. The long-term contributor-signing policy is still awaiting
> maintainer approval. Third-party source imports require recorded provenance
> and license review.

## Start here

1. Read `docs/CODEX_ONBOARDING.md` for the current architecture, runtime paths,
   verification commands, and project rules.
2. Search existing issues and pull requests before beginning substantial work.
3. Open a design discussion before changing security boundaries, persistence
   schemas, public APIs, model routing, connectors, or supported runtimes.
4. Keep pull requests focused. Separate unrelated refactors and generated
   artifacts.

## Development workflow

```powershell
npm.cmd install
npm.cmd run build
$env:PYTHONHOME=$null
$env:PYTHONPATH=$null
.\.venv\Scripts\python.exe -m unittest tests.testBackendSmoke tests.testMultiUser
npm.cmd run desktop:test
```

Use the isolated verification workflow in `.agents/skills/verify/SKILL.md` for
browser-visible changes. Runtime data must stay outside the repository.

## Pull requests

Include:

- The user problem and resulting behavior.
- Files and security boundaries affected.
- Tests run and their results.
- Screenshots for material interface changes.
- Migration or rollback notes when stored data changes.
- Upstream provenance for external ideas, dependencies, or source.

Do not:

- Commit credentials, runtime databases, model files, local workspaces, or
  generated frontend output.
- Stage unrelated user changes.
- Weaken approval, workspace, owner, or network boundaries for convenience.
- Copy upstream code without following `docs/UPSTREAM_ADOPTION_POLICY.md`.

## Upstream work

Record proposed source or dependency adoption in
`docs/upstream/ADOPTION_REGISTER.md`. Direct source adoption requires a
compatible Rasputin license and preserved upstream notices.

## Review priorities

Maintainers review in this order:

1. Safety, privacy, and data-boundary correctness.
2. Observable runtime behavior.
3. Tests and failure handling.
4. Compatibility and migration impact.
5. Usability and documentation.
6. Code style.

## Community conduct

Participation is governed by `CODE_OF_CONDUCT.md`.
