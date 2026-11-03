# GitHub Actions delivery and desktop updates

Rasputin uses [CI and Windows delivery](../.github/workflows/ci.yml) to run routine
verification without an agent supervising each command. Source checks, installer
artifacts, published releases, and installed upgrades remain different evidence.

## What runs automatically

| Trigger | Result |
| --- | --- |
| Push to `codex/**`, or a pull request | Repository path/secret-history checks, dependency review on PRs, Windows source regressions, authenticated browser fixtures, desktop lifecycle/updater tests |
| Push to `main` | The same checks, followed by an unsigned Windows NSIS installer, checksums, updater metadata/blockmap, and a frozen-backend smoke check |
| Manual **CI and Windows delivery**, `main`, `release: true` | The same gates, a signed installer with signature/publisher verification, then a **draft** GitHub Release targeting the exact tested commit |
| Publish the reviewed draft in GitHub Releases | Makes the stable installer and `latest.yml` visible to signed installed clients |

Failed or cancelled prerequisite jobs block packaging and release creation. Workflow
artifacts are retained by GitHub Actions; browser evidence is retained for seven days.
Build jobs have read-only repository access; only the draft-release job can write releases.
Fork PRs never run packaging or receive signing secrets. The existing source and safety
workflows are reusable jobs, so the delivery workflow does not duplicate their checks.

The pipeline runs the current `verify_source_regressions.py` suite, not every possible
hardware or UI test. It never downloads a model or claims GPU, voice, clean-machine,
installed-upgrade, or real coding-mission certification. The packaged smoke check starts
the frozen backend with its production supervisor and temporary data, checks health and
the packaged frontend, then stops its owned process and removes its test data.

## One-time GitHub setup

1. Merge the pipeline changes into `main`. Configure branch protection/rulesets to require
   the source and repository safety jobs shown on a completed run; require dependency
   review for PRs too. Keep direct pushes to `main` restricted. Workflow files cannot
   enforce repository branch protection by themselves.
2. Create a GitHub Actions environment named **release**. Restrict deployment branches
   to `main`; add required reviewers if approval before signing is desired.
3. In that environment, add secrets **CSC_LINK** (base64-encoded PFX or a supported
   certificate source) and **CSC_KEY_PASSWORD**. Set variable **WINDOWS_PUBLISHER_NAME**
   to the certificate's exact publisher common name. These are electron-builder's PFX
   signing inputs; hardware-backed/cloud signing needs its own signing integration.
   Never commit a certificate, password, or GitHub token. Clients use the public release
   feed and carry no GitHub credentials.
4. Bump `package.json` and `package-lock.json` to an unused stable `x.y.z` version before
   each release. Run the delivery workflow on `main` with `release` checked. Missing
   credentials, invalid signatures, publisher mismatches, or reused version tags fail
   the release. Inspect the draft assets and validation run, then publish the draft.

No signing credentials or branch protection are provisioned by this code change.
Routine unsigned CI installers are never uploaded to the public release channel.
The draft contains the versioned installer, SHA-256 checksums, stable download aliases,
`latest.yml`, and differential `.blockmap`. Do not edit those assets after publishing.

## How the application updates

The main Electron process loads the bundled `electron-updater` resource for packaged
Windows installs. It requires a publisher name in the generated `app-update.yml` before
enabling updates. This matters because electron-updater 6 otherwise skips signature
verification when no publisher is configured. Publisher verification remains enabled;
the desktop verifier also rejects updates if PowerShell cannot verify the signature,
instead of accepting electron-updater 6's compatibility fallback.
The update feed is fixed to `Shingenn5/Rasputin` on GitHub, with prereleases and downgrades
disabled. No renderer API can select a different feed or invoke installation.

A signed install checks after 30 seconds and every six hours. It downloads a newer stable
release automatically. The tray menu also offers **Check for updates** and **Restart to
install update**. A native dialog defaults to **Later**. Ordinary app quit does not install
a pending update. On explicit confirmation, the app stops only its owned Desktop Runtime
before asking NSIS to replace the app and relaunch it. Existing installer behavior preserves
application data and external models. The confirmation asks users to finish running tasks;
it does not detect task completion or certify crash-safe task resumption.

An unsigned CI build displays **Updates unavailable — signed install required**. Source
Native Host and repository Electron development sessions do not check for updates.
Failures remain retryable from the tray without exposing raw errors or credentials.

**Bootstrap limitation:** existing releases have no updater. Install the first signed
updater-enabled release manually once. Subsequent stable signed versions can use this
channel. A real signed N → N+1 install/restart/data-preservation rehearsal is still required
before calling the update channel certified. There is no automatic rollback; if a release
is bad, withdraw it and publish a corrected higher version, or manually reinstall a known
good package after quitting the application and preserving/backing up its data.

## Local checks

```powershell
npm.cmd run desktop:check
npm.cmd run desktop:test
.\.venv\Scripts\python.exe scripts\verify_docs.py
npm.cmd run desktop:package
node scripts/verify-update-artifacts.cjs
node scripts/smoke-packaged-desktop.cjs dist/electron/win-unpacked/resources
```

For signed local packaging, supply the same signing inputs privately and pass
`--config.forceCodeSigning=true` and `--config.win.publisherName=<publisher>` to the
packaging command. Packaging or passing a mocked updater test does not prove a signed
update was downloaded, trusted, or installed on a clean Windows machine.
