# SignPath Foundation setup and application packet

This is the selected free/open-source signing route. Integration code and templates do
not constitute Foundation approval. The account, certificate, publisher name and real
signed upgrade remain unverified until setup and a production signing run complete.

## Application facts to review

| Field | Project information |
| --- | --- |
| Project | Rasputin Desktop |
| Repository/homepage | https://github.com/Shingenn5/Rasputin |
| Download page | https://github.com/Shingenn5/Rasputin#install-and-run (links to GitHub release assets) |
| License | AGPL-3.0-or-later; public source and `LICENSE` in the repository |
| Maintainer / proposed approver | GitHub account `Shingenn5` |
| Contact name and email | The maintainer must supply and confirm these in the application |
| Signing policy | `CODE_SIGNING_POLICY.md` in this repository; link the merged public version |
| Build system | GitHub Actions, GitHub-hosted Windows runner; `.github/workflows/ci.yml` and `windows-installer.yml` |
| Artifacts | Branded Electron app, PyInstaller backend, then Windows NSIS installer |
| Network/privacy | Automatic GitHub update checks, model/runtime downloads, and operator-enabled integrations; disclosed in the signing policy |
| Current status | Public Windows previews exist; signing integration prepared; Foundation application not submitted by this change |

Project description: Rasputin is a local-first Windows AI workstation for native GGUF
inference and governed agentic coding. Users browse/download model variants, run them
through hardware-selected llama.cpp, and work with chats and approved local workspaces.
The desktop application bundles its Electron host, React frontend and Python backend;
end users do not need the build toolchain. Filesystem and execution capabilities remain
subject to operator permissions, workspace boundaries and approval controls.

Before submitting the official [application](https://signpath.org/apply), confirm:

- The maintainer's contact details and MFA on GitHub and SignPath.
- The [Foundation conditions](https://signpath.org/terms), including open-source-only
  components, public releases/documentation, project reputation and manual approval.
- The licenses/provenance of every bundled dependency and the proposed signing scope.
  Being AGPL-licensed and publicly released makes Rasputin a candidate, not automatically
  eligible. The Foundation decides whether the project and wrappers qualify.
- A merged, publicly accessible signing policy linked from the homepage/download page.
- The intended approver can respond to two signing requests during a release run.

No application is submitted, email sent, account created or terms accepted by this code.
The application packet is ready for the maintainer's review and completion.

## After Foundation acceptance

1. Create/link the SignPath project to `Shingenn5/Rasputin` and the GitHub.com trusted
   build system. Install/authorize the SignPath GitHub App if required by its setup.
2. Configure a signing policy with manual approval by the designated approver. Restrict
   it to this repository, the release workflow and protected `main`, on GitHub-hosted
   runners. Do not permit arbitrary user-supplied artifacts or a broad PE wildcard.
3. Import [application.xml](../.github/signpath/application.xml) and
   [installer.xml](../.github/signpath/installer.xml) as separate artifact configurations.
   Suggested slugs: `rasputin-app-v1` and `rasputin-installer-v1`. Both require the
   `version` parameter. Confirm these XML templates in the SignPath portal; local XML
   parsing is not server-side schema or policy acceptance.
   Electron stores Windows ProductVersion with a fourth zero (`x.y.z.0`); the
   application template binds that form to release `x.y.z`, while the backend and
   installer use `x.y.z`. Confirm the Foundation accepts this normalization.
4. In the GitHub **release** environment, add:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `SIGNPATH_API_TOKEN` | Restricted signing submitter token supplied after account setup |
| Variable | `SIGNPATH_ORGANIZATION_ID` | Approved SignPath organization ID |
| Variable | `SIGNPATH_PROJECT_SLUG` | Project slug, suggested `rasputin` |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG` | Manually approved release policy slug |
| Variable | `SIGNPATH_APP_ARTIFACT_CONFIGURATION_SLUG` | Approved application configuration slug |
| Variable | `SIGNPATH_INSTALLER_ARTIFACT_CONFIGURATION_SLUG` | Approved installer configuration slug |
| Variable | `WINDOWS_PUBLISHER_NAME` | Exact common name of the Foundation certificate, verified from its actual certificate |

No exportable PFX or certificate password is used. SignPath retains its signing key.
Do not invent an organization ID, publisher name or token to get a release past the gate.

## Release flow

Run **CI and Windows delivery** on `main` with `release` checked and an unused stable
version. The workflow requires all configured values before spending time on packaging.

1. Build an unpacked application and stage only `Rasputin.exe` and `rasputin-backend.exe`.
   The backend embeds the same product name/version as the application.
2. Upload those exact files as a GitHub artifact. The pinned official SignPath action
   submits the artifact ID, waits up to 30 minutes for approval, then downloads the return.
3. Validate every returned signature/publisher before copying any returned executable.
4. Build NSIS from that prepackaged application. Upstream NSIS helpers/uninstaller are
   not submitted for signing; this limitation is explicit in the signing policy.
5. Upload the versioned installer as a second GitHub artifact. Approve its SignPath request.
6. Verify the returned installer and regenerate its blockmap/SHA-512 manifest. Verify
   the feed, metadata and frozen runtime; then create SHA-256 checksums and stable aliases.
7. Prepare a draft release from the tested commit. Include a **Code signing policy** link
   and accurate signed/unsigned status in the release description before publication.

Signing failures, rejected/late approvals, unexpected returned files, invalid signatures,
publisher mismatches and missing configuration fail the release. Unsigned routine CI
installers remain available as workflow artifacts and are never promoted to the update feed.

The staged app/update configuration is not a distributable release until signature
verification completes. Do not publish intermediate unsigned application artifacts.

## Verification boundary

Local fixture tests cover file selection, rejection of invalid signed returns, and
regeneration of update metadata after bytes change. An unsigned packaging rehearsal can
check application version resources and prepackaged NSIS assembly. Neither proves the
Foundation has approved the templates, issued a certificate, or signed an artifact.

Before enabling the channel for users, complete an actual signed release and a signed
N-to-N+1 installed upgrade with persistent-data checks. Existing releases need one manual
bootstrap upgrade. Signing and publishing do not install an update on this workstation.

References: [official GitHub integration](https://docs.signpath.io/trusted-build-systems/github),
[artifact configuration reference](https://docs.signpath.io/artifact-configuration/reference).
