# Microsoft Store and personal CI testing

## Current delivery boundary

GitHub Actions can build personal-test NSIS installers and unsigned AppX packages.
AppX is accepted by the Microsoft Store MSIX submission flow. These are build
artifacts, not a certified Store listing or evidence of an installed upgrade.

On `main`, successful CI builds both packages automatically. On a task branch,
run **CI and Windows delivery** with `test_packages: true` after pushing your changes.
The source and safety gates must pass before packaging. Download artifacts from the
completed run; they include checksums and the Store package includes source-SHA and
identity provenance. Uncommitted workstation edits are not part of a GitHub build.

For immediate personal testing, use `rasputin-windows-installer`. It is unsigned
and requires manual installation. It does not bypass signature checks or enable
the GitHub auto-update channel. The `rasputin-store-test-package` artifact uses the
explicit `Rasputin.LocalTest` identity and is only a packaging rehearsal. It cannot
be uploaded as your reserved Store app or installed normally without signing.
This workflow never generates a certificate or silently adds one to Windows trust.

## One-time Microsoft setup

1. Start at <https://storedeveloper.microsoft.com/> using the new free registration
   flow. Sign in with your own personal Microsoft account and complete the identity
   checks and developer agreement yourself. Do not send ID documents or passwords
   to an agent or put them in the repository.
2. In Partner Center Apps and Games, create an app and reserve its name. On
   **Product management > Product identity**, copy these exact values into GitHub
   repository Actions variables:

   | GitHub variable | Partner Center value |
   | --- | --- |
   | `STORE_IDENTITY_NAME` | Package/Identity/Name |
   | `STORE_PUBLISHER` | Package/Identity/Publisher, including `CN=` |
   | `STORE_PUBLISHER_DISPLAY_NAME` | Package/Properties/PublisherDisplayName |

   These are public package identity fields, not signing secrets. Do not invent
   them from the app name. Submission mode fails if any value is missing.
3. Run **CI and Windows delivery** on `main` with `store_submission: true` and
   `release: false`. Download `rasputin-store-submission`. Upload its `.appx` on
   the submission's Packages page. Microsoft supports this format; a separate
   purchase of a code-signing certificate is not required for Store distribution.
4. Complete the listing, privacy URL, screenshots, age rating, declarations, and
   certification notes. Explain that `runFullTrust` is needed for the packaged
   Python backend, local inference processes, and user-approved workspace access.
   Acceptance of these capabilities and runtime acquisition remains Microsoft's
   decision. Run the Windows App Certification Kit and resolve its findings.
5. Before the **first submission**, select **Private audience** and create a known
   user group containing only the personal Microsoft account you use in the Store.
   Do not choose Public as a shortcut: Microsoft does not let an already-public
   listing become private later. Submit for certification, then install using the
   private listing link after acceptance.

## Updates and verification

Store installs are detected with Electron's `process.windowsStore`. They never load
the GitHub NSIS updater; their tray reports **Updates managed by Microsoft Store**.
The package uses the Store-assigned app identity instead of the NSIS app model ID.
Store-managed updates depend on Windows Store settings and delivery timing; this
is not an immediate per-commit deployment system.

Package versions use `<application major + 1>.<minor>.<patch>.0` because Store requires
a positive major and reserves the fourth component. For example, application
`0.3.5` produces Store package `1.3.5.0`, and `1.0.0` will produce `2.0.0.0`.
This mapping preserves upgrade order without declaring the application 1.0-ready.
Bump `package.json` and `package-lock.json` before each Store update. Rebuilding the
same version does not create a higher-versioned update.

For the first N to N+1 rehearsal, use isolated test data and a small disposable
model. Verify packaged backend startup, loopback UI, runtime download and launch,
model loading/inference/stop, workspace approvals, tray/quit behavior, and relaunch.
Then submit a higher package version to the same private audience. Close Rasputin
fully, acquire the update through Store, and verify version, settings, chats and
model paths survived. Installed NSIS and Store data can be redirected differently
by Windows package virtualization; migration and coexistence are not certified.
Never run them concurrently against the same data directory.

GitHub currently stops at verified downloadable packages. Initial Store submission
and subsequent uploads are manual; no Partner Center API credentials are configured.
Automate package flights after the account, initial submission and upgrade rehearsal
work. Do not mistake CI artifact upload for Store publication.

## References

- [Microsoft signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Free developer onboarding](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/account-types-locations-and-fees)
- [Private audience](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/visibility-options)
- [Accepted package formats](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/upload-app-packages)
- [electron-builder AppX](https://www.electron.build/docs/appx/)
