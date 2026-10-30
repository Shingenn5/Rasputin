# Rasputin information architecture

Direction confirmed October 30, 2026: retain Rasputin's broader workstation capabilities, grouped more clearly. Borrow task separation and progressive disclosure from Unsloth and LM Studio while preserving Rasputin's homepage identity, composer, native runtime ownership, and safety boundaries.

## Navigation model

| Area | User task | Current destinations |
|---|---|---|
| Workspace | Have conversations and return to saved work | Chat, Library; project selection and recent chats remain directly available |
| Models | Find, download, inspect, and use models | Model Hub, Training |
| Automation | Delegate work and manage recurring activity | Assistant, Scheduled |
| Developer | Integrate local inference with other software | API |
| Settings | Configure the workstation | Existing Settings sections |

Existing specialist routes remain reachable through More and existing command/navigation paths. Route identifiers and access checks remain stable. This first slice does not reparent all specialist features or turn the existing API-key screen into a complete developer workspace.

## Model Hub

The two primary destinations are **Discover** and **My Models**. The distinction is acquisition versus inventory, rather than downloaded files versus running processes. Loading a model is a state transition, not a separate primary information category.

- Discover preserves catalog search, exact GGUF variant selection, compatibility information, downloads, and links to installed models.
- My Models presents compact selectable rows with identity, format, size, and state. Actions belong in the selected model's details, avoiding repeated Load buttons and normal-state explanations across the row and inspector.
- The desktop detail panel starts wider. On screens at or below 1100 px, selecting a model opens its detail surface; Back returns focus to the selected row. The inventory is not stacked above an entire settings inspector.
- Normal ready and unloaded states use compact status. Blocked states retain recovery explanations and controls. Healthy external connections retain their editable settings under a disclosure.
- **Model tools** provides Runtime monitor, Share models, and Connections & settings. Download-folder management lives with those settings. These are explicit reachable secondary tasks, not removed capabilities.
- Primary tab navigation and Model tools remain keyboard accessible, including when a secondary tool is selected.

## Next migration slices

1. Apply the same focused detail behavior to Discover and consolidate its browse/search toolbar without changing exact-file download semantics.
2. Build a complete Developer destination around existing API access and model-serving controls. Preserve authentication, endpoint ownership, protocol readiness, and approval boundaries; do not merely rename the API-key screen.
3. Group specialist automation, skills, agents, history, and approval routes by their actual tasks rather than leaving them permanently in a generic More list. Keep permission-filtered access and saved routes working.
4. Unify per-model load settings and response settings across Model Hub and Chat without restructuring Chat or removing its composer pill.

Each slice should have its own reversible commit and live desktop/tablet/phone interaction checks. A larger sidebar alone is not an information-architecture migration.

## Reference boundaries

Unsloth's installed 0.1.911-beta frontend was inspected as shipped code: its two main hub destinations, selectable compact results, full detail views, and optional split layout informed this direction. Static analysis does not establish a fresh live usability result.

LM Studio's current [getting-started workflow](https://lmstudio.ai/docs/app/basics) separates Discover, model loading, and Chat. Its [User and Developer modes](https://lmstudio.ai/docs/app/user-interface/modes) show progressive disclosure of advanced controls. Rasputin is adopting those task boundaries without adding a new global mode switch in this slice.

## Verification scope

Browser fixtures cover model state and runtime responses; authentication, rendering, routing, keyboard interaction, load-dialog submission, and responsive layout use the running isolated source application. Fixture-backed load submission is not real model inference or installed-app verification. The installed application is not changed by this source branch.
