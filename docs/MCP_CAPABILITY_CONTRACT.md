# MCP capability contract

Rasputin exposes a versioned, fail-closed capability contract for the tools it
can discover and invoke. This is the boundary between model-authored tool
requests and the local Tool Relay policy.

## Discovery

`GET /api/tools` returns the operator-facing catalog. Its `contract` object is
currently:

```json
{
  "name": "rasputin.mcp.capabilities",
  "version": "1.0",
  "schemaVersion": "json-schema-2020-12",
  "discoveryMode": "fail_closed"
}
```

Each entry includes the existing risk, permission, approval, and JSON input
schema fields plus:

- `contractVersion` and `schemaVersion`: the contract and input-schema versions;
- `source`: `internal_tool_relay` or `external_mcp`;
- `discoverable`: whether the entry is visible in the catalog;
- `available` / `callable`: whether the current policy permits invocation;
- `availability`: `callable` or `blocked`;
- `disabledReason`: a safe operator-facing explanation when blocked.

The complete `tools` list deliberately keeps blocked entries so the UI can
explain policy decisions. `callableTools` is the filtered discovery surface for
clients that need only tools they can invoke now.

## Model-facing tool schemas

Planning and execution phases use the same callable-only filter through
`backend.mcp.tools.callable_definitions`. Permission flags, implementation
state, unattended-mode allowlisting, Trusted Dev workspace requirements, and
input-schema validity are evaluated before a definition is offered to a model.
The runtime still re-checks the policy when a call arrives; discovery is not a
replacement for execution-time authorization.

## External MCP tools

External tools remain unavailable until all of the following are true:

1. the MCP server registration is approved and enabled;
2. the tool is classified with an allowed risk and permission flag;
3. the current security and unattended policies allow the call.

Unclassified tools are still discoverable to an operator, but are marked
`callable: false` with `disabledReason: Tool classification required.`. In
unattended mode, external MCP tools remain blocked by default.

When the contract changes incompatibly, increment `CAPABILITY_CONTRACT_VERSION`
in `backend/mcp/tools.py` and update this document and the regression tests in
`tests/testBackendSmoke.py`.

## Local safety certification

Run the isolated certification command before changing MCP policy or routing:

```powershell
C:\Users\elliott\OneDrive\Documents\WrapperProject\.venv\Scripts\python.exe scripts\certify_mcp_safety.py
```

The report proves callable-only discovery, an allowlisted read-only route, a
shell-like command rejection, a dry-run mutation preview, a file-write
approval preview, and the corresponding redacted audit events. It uses a
temporary data directory and fixture workspace; it does not start an external
MCP server, execute a host command, write a fixture file, or contact a remote
endpoint. A passing report is policy-boundary evidence, not permission to
remove the approval gate.
