# Rasputin privacy policy

Updated November 3, 2026. Maintained by the Rasputin project at
<https://github.com/Shingenn5/Rasputin>.

## Local processing and storage

Rasputin is a Windows AI workstation. Local model inference runs on your computer.
Application state can include conversations, tasks, preferences, workspace
registrations, model paths, downloaded models, configured service credentials,
and diagnostic/audit records. These are stored on your computer. Workspace tools
can read or change files according to the permissions and approvals you grant.
Local storage is not a promise of encryption against other users or programs
that already have access to your Windows account or data directories.

## Network features

- Model catalogs, model downloads and runtime downloads contact their hosting
  services, including Hugging Face and GitHub. Search requests, requested files
  and ordinary connection information such as your IP address reach those services.
- When enabled and used, remote model providers receive the prompts, context,
  files or tool results included in a request. Web search, Telegram and MCP
  integrations can also transfer information to the destinations you configure
  or invoke. Review each integration and workspace permission before use.
- Microsoft Store installations receive updates through Microsoft Store. They do
  not use Rasputin's GitHub NSIS update client. Signed standalone NSIS installations
  can check GitHub for updates automatically after startup and periodically;
  unsigned test installers do not enable that update channel.

Privacy Lock controls remote model access. It does not disable all networking,
including catalog queries, downloads or operating-system Store updates.

Third-party processing is governed by the relevant provider's policies, including
[Microsoft](https://privacy.microsoft.com/privacystatement),
[GitHub](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement),
[Hugging Face](https://huggingface.co/privacy), and services you configure.

## Retention, removal and support

Local information remains until you remove it or the feature that owns it performs
its documented cleanup. Downloaded models and workspace files may live outside
application-managed storage. Removing the application is not a reliable way to
erase all such files. Close Rasputin before manually managing its data directories.

If you choose to share logs, screenshots or issue reports, review them for private
content first. Public GitHub issues are public. Use the repository's
[security reporting instructions](SECURITY.md) for security-sensitive reports.
For privacy questions, contact the maintainer through the
[project repository](https://github.com/Shingenn5/Rasputin).
