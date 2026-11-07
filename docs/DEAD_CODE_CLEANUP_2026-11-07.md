# Dead-code cleanup — 2026-11-07

## Scope and outcome

Audited 146 frontend modules and 129 backend Python files using import graphs,
binding analysis, Python AST inspection, and repository-wide references. Checked
tests, scripts, configuration, route registration, and worker entrypoints before
removing candidates. This is a bounded audit, not proof that every remaining
declaration is used at runtime.

Removed 30 unused declarations, 85 unused import bindings, one unreferenced input
component file, and 28 orphaned CSS rules. The cleanup and two test-contract
adjustments remove a net 302 lines before this report. The remaining 145 frontend
modules are reachable from application, preview, or worker entrypoints.

Examples include the unused StudioModelDetail and GraphNodeCard components,
unused Card section exports, navigation/prompt constants, saveDeploymentPolicy,
and backend helpers _model_settings_error, _skill_path, rm_model,
supported_modes, _capability_list, save_memory, and demo_tool_call. Active Card,
Badge, CountUp, registered APIs, re-exports, and referenced legacy adapters remain.
Vite aliases and the Pyodide worker were resolved before classifying modules.
The active Discover inspector's studio-model-capabilities styling remains.

The secondary-view test no longer requires CSS for the deleted detail component.
The catalog test permits the background field already present in the load payload.
Neither adjustment changes production behavior.

## Verification

Checks on a clean HEAD snapshot with only this cleanup applied:

- Production frontend build: passed; existing large-chunk warning remains.
- JavaScript and desktop lifecycle/update tests: 168 passed, 0 failed, 2 skipped
  (signing-dependent checks).
- Backend smoke: 168 passed. Settings API: 5 passed. Skill policy: 4 passed.
  Memory restart: 2 passed. Load-profile pytest suite: 13 passed.
- Native model acquisition: 9 passed, 1 error. The error in
  test_partial_load_profile_retains_saved_cpu_preference was reproduced with
  unchanged HEAD registry code: a mocked store returns a string where a mapping
  is expected when recording the load outcome.
- Live authenticated browser checks for all deferred pages and failed-chunk
  recovery: 2 passed. The settings-draft check fails on unchanged HEAD too;
  its draft value resets to /app/workspace. With existing working-tree settings
  changes included, all 3 startup-resource browser checks pass.
- Static comparison found no newly unbound JavaScript references.

Live verification caught an import-editing regression that removed used names
sharing a line with an unused import. Those names were restored before the final
build, JavaScript suite, and browser checks above.

Existing unrelated staged and unstaged changes were excluded from this commit.
Their broader test failures are not represented as cleanup passes. The installed
desktop application was not replaced or restarted.

## Performance interpretation

This removes maintenance noise and unused CSS. It does not establish a startup or
RAM improvement: the frontend bundler already eliminates many unused JavaScript
exports. Startup and memory improvements require separate measurements of the
processes and code that actually execute.
