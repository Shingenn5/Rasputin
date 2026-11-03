# Code signing policy

**Status:** SignPath Foundation integration is being prepared. No application approval,
Foundation certificate, or successfully signed Rasputin release is claimed. Existing
public releases remain unsigned until their release notes explicitly state otherwise.

If the project is accepted, the signing attribution will be:

Free code signing provided by [SignPath.io](https://signpath.io), certificate by
[SignPath Foundation](https://signpath.org).

## People and approval

- Maintainer, committer and reviewer: [Shingenn5](https://github.com/Shingenn5).
- Signing approver: [Shingenn5](https://github.com/Shingenn5).
- GitHub and SignPath accounts participating in signing must use multi-factor
  authentication. Account MFA setup still needs confirmation by its owner.
- Every signing request requires manual approval in SignPath. The two-stage release
  flow requests approval for the application executables and then for the installer.
- Contributors' pull requests must be reviewed before signing. Source, workflow and
  dependency changes are covered by the repository's required GitHub Actions checks.

The Foundation may require additional reviewers, controls or packaging changes before
acceptance. Its [terms](https://signpath.org/terms) govern the service.

## What is submitted for signing

Only stable Windows release artifacts built by GitHub-hosted runners from the protected
`main` branch of [Shingenn5/Rasputin](https://github.com/Shingenn5/Rasputin):

- `Rasputin.exe`: the Rasputin-branded Electron application executable.
- `rasputin-backend.exe`: the frozen Python backend built from this repository.
- `Rasputin-Setup-<version>.exe`: the NSIS installer containing those application files.

The artifact configurations restrict file names, product name and product version.
Coverage of the Electron/PyInstaller application wrappers is subject to Foundation
review. Upstream runtimes, model weights, downloaded tools, third-party DLLs and NSIS
helper binaries are not re-signed as Rasputin-owned software. The generated NSIS
uninstaller remains unsigned in this integration; full-package signing is not claimed.

Signed returns must have a valid Windows Authenticode signature from the configured
publisher. The pipeline regenerates the installer blockmap, SHA-512 update metadata and
SHA-256 download checksums after signing. Only validated artifacts reach a draft release;
publishing the release is a separate maintainer action. No PR build requests signatures.

## Privacy and network behavior

Rasputin stores application state, chats, workspaces and model registrations locally by
default. Native inference runs on the user's machine. Network features include:

- Automatic update checks contact GitHub after startup and periodically. GitHub receives
  ordinary connection metadata. Update downloads retrieve public GitHub release assets.
- Model/catalog searches and requested downloads contact their model hosts, including
  Hugging Face and GitHub. Hardware-selected runtime downloads contact the published host.
- Remote model providers, web tools, Telegram and MCP integrations can transfer task or
  workspace information when the operator enables and uses those features. Their
  destinations and access depend on the operator's configuration and permissions.

See [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement),
[Hugging Face's privacy policy](https://huggingface.co/privacy), and the policies of any
additional services the operator configures. Privacy Lock controls remote model use;
it does not disable application update checks or operator-requested downloads.

## Verification and reports

Published download/release pages must link this policy and state whether that specific
release is signed. Users can compare the published SHA-256 checksum and inspect the
file's Digital Signatures tab or `Get-AuthenticodeSignature`. A valid signature does not
prove that every application feature is safe or correct, or guarantee no SmartScreen
warning. Report suspected tampering through the repository's
[security reporting guidance](SECURITY.md).
