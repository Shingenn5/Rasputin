# Security Policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or exposed secret.

Until a dedicated security contact is published, use the repository's private
GitHub Security Advisory reporting flow. Include:

- Affected version or commit.
- Runtime mode: native, Docker, or desktop.
- Reproduction steps.
- Expected and observed security boundary.
- Potential impact.
- Any safe proof of concept.

Do not include real credentials, private workspace contents, or personal data.

## Response expectations

The maintainer will acknowledge a valid private report, assess affected
versions and mitigations, and coordinate disclosure after a fix or containment
plan exists. Exact response-time commitments will be published with the first
supported public release.

## Security boundaries

High-risk areas include:

- Workspace and owner isolation.
- File, shell, Git, Docker, and connector approvals.
- Authentication, sessions, recovery, and secret storage.
- Model and tool prompt injection.
- Remote endpoints and network destinations.
- Archive extraction, uploads, and path traversal.
- Desktop/backend process ownership.
- Generated installers and update channels.

## Supported versions

No public version is designated as supported yet. This section will be updated
before the first public release.

## Public-release safety

See `docs/PUBLIC_RELEASE_AUDIT.md` for the current repository-clearance status.
