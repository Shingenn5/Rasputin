# Rasputin → SaaS business: gap analysis & options

*2026-07-12. A menu, not a plan. The point of this doc is to lay out the landscape of
what turning Rasputin into a SaaS company involves, so you can decide what you actually
want to build. Nothing here is committed. Items are tagged with a rough **effort**
(S/M/L/XL) and a **tier** (Foundational / Differentiating / Scale / Later) to help you
prioritize — not to tell you the order.*

---

## How to read this

- **Foundational** = you basically can't sell a multi-customer SaaS without it.
- **Differentiating** = this is where Rasputin wins or loses vs competitors; your moat.
- **Scale** = needed once you have paying customers, not before.
- **Later** = real, but don't spend cycles now.

Skim the **strategic decisions** first — several downstream items only make sense after
you've answered those. Then browse the gap categories and mark what resonates.

---

## Your direction (decided 2026-07-12)

You've answered most of the strategic 5, and they point to a **focused self-hosted product**,
not generic hosted SaaS:

- **Customers** → orgs that can't let data leave their servers (regulated / security-sensitive)
  + dev teams cutting API cost by self-hosting.
- **Models** → run **open-source models locally on the customer's own hardware**; zero API cost,
  nothing leaves their network. WarSat's local orchestration becomes *the* product.
- **Deployment** (implied) → **self-hosted / on-prem** is the primary model.
- **Open-core** → repo stays fully private; free-vs-paid decided later.
- **Wedge** (crystallizing) → *"Capable AI on your own hardware — nothing leaves your network,
  zero API bill."*

**What this changes.** A cleaner, more defensible product that plays straight to Rasputin's
existing strengths (dual-mode, WarSat, security, no data egress).

*Gets lighter or deferred* — each customer runs their own instance on their own hardware, and you
never hold their data:
- Multi-tenant DB / isolation-at-scale (A) → shrinks to team/org support *within* one deployment.
- Hosted scaling + GPU-inference hosting (D) → the customer's burden, not yours.
- Usage-metered billing (C) → replaced by **license keys / per-seat or per-server licensing**.
- Compliance data-liability (E) → drops sharply; *you don't hold their data* is itself the pitch.

*Becomes central* — what this product lives or dies on:
1. **Local open-source model serving that's genuinely good** — WarSat routing, quantization,
   performance on the customer's GPUs/CPUs, model acquisition/management. The core value.
2. **A great self-hosted install/deploy experience** — Phase 5 (installer + server image) is no
   longer "later," it's the product's front door.
3. **Licensing + entitlements for self-hosted** — license keys, seat/server enforcement that works
   on-prem / offline.
4. **Team/org features within a deployment** — shared workspaces, roles, knowledge (the ACV lever).
5. **Security as documented, provable guarantees** — your Phase 3/4 sandbox work + "nothing leaves
   your network," turned into a security page / whitepaper.

**The one honest tension:** local OSS models are less capable than frontier APIs. This product wins
with customers for whom **data egress is a hard blocker** (frontier APIs aren't an option, so "good
local" beats "no AI") and by using orchestration to close the gap — not with devs who can freely use
GPT/Claude and just want marginally cheaper.

**Revised near-term sequence (self-hosted / local-model path):** local model serving + WarSat quality
→ Phase 5 installer/server image → team/org support in a deployment → on-prem licensing → security-as-
a-product → then integrations/marketplace, and a hosted option only if demand pulls it.

*(The generic sequence further down assumed hosted-SaaS/BYO-key — read it through this lens; where
they conflict, this section wins.)*

---

## Where Rasputin is today (honest snapshot)

**What's real and good:**
- A working local-first AI orchestration app: FastAPI backend, React UI, WarSat model
  orchestration, an MCP tool layer, a workspace/trust model, a coding-agent loop.
- A genuinely strong **security story** — and it's now more than a story: trust modes,
  Privacy Lock, audit logging, and (as of this week) a real **blast-radius-contained host
  shell** (commands run as a low-privilege sandboxed account) and **no-network skill
  sandboxes**. Very few competitors can say this.
- A **dual-mode architecture** (native workstation + Docker server SKU) that already sets
  up a natural free-core / paid-hosted seam.

**What makes it a dev tool, not yet a SaaS:**
- **Single-tenant, single-user.** Auth is one admin account; there is no concept of users,
  orgs, teams, or per-tenant data isolation.
- **Runs on the operator's machine / their own Docker.** There is no hosted offering,
  no cloud deployment story, no scaling.
- **No billing, no accounts, no self-serve onboarding.** Nothing to sign up for or pay for.
- **State is local** (SQLite + a runtime KV). Fine for one machine; not a multi-tenant DB.

None of this is a criticism — it's the normal starting point. The rest of this doc is the
distance from here to a business.

---

## Strategic decisions to make first (these shape everything below)

These aren't build tasks; they're choices only you can make, and most gaps below branch on
them. Related: `commercialization-stance` (turn into a company, not necessarily sell the
software) and `docs/DUAL_MODE_ARCHITECTURE_PLAN.md`.

1. **Who is the customer?** Indie devs? Security-conscious teams? Regulated enterprises
   (finance/health/gov) who *cannot* send code to OpenAI? The last group is where your
   security + local-model story is worth the most — and also the hardest sale (SOC 2, long
   cycles). Pick a wedge; it changes the whole roadmap.

2. **Hosted, self-hosted, or hybrid?** Your dual-mode work supports all three:
   - **Self-hosted / on-prem** (they run the Docker server SKU): fits the security buyer,
     lightest infra burden on you, hardest to meter/bill, slower growth.
   - **Hosted SaaS** (you run it): classic SaaS motion, but you own uptime, scaling, and —
     the big one — **model inference cost**.
   - **Hybrid** (hosted control plane, their compute/models): often the sweet spot for a
     security product, most complex to build.

3. **Who pays for the models?** This is the single biggest cost/margin question.
   - **BYO-key** (customer brings their OpenAI/Anthropic/etc. key): near-zero inference cost
     to you, easy margins, but you're "just orchestration." Fastest to viable.
   - **You host inference** (own/rented GPUs for local models): capital-intensive, hard to
     get margins right, but it's a real moat and fits the "your code never leaves" pitch.
   - **Hybrid / passthrough with markup.** Most SaaS in this space start BYO-key and add
     hosted inference later.

4. **Open-core boundary.** If any of Rasputin is open source, *what* is free vs paid? Common
   line: single-user + core orchestration free/OSS; teams, SSO, hosted, compliance, and
   advanced security = paid. Decide before you publish anything (repo is private now, which
   preserves every option).

5. **What's the one-line wedge?** "The AI coding agent that can't leak your code" is a very
   different product than "multi-model orchestration that cuts your LLM bill." You have
   ingredients for both; leading with one focuses everything.

---

## Gap categories (the actual work)

### A. Identity, accounts & multi-tenancy — **Foundational, XL**
The biggest lift, and the gate to everything. Today: one admin. A SaaS needs:
- User accounts (signup, login, email verify, password reset, MFA). *(M–L)*
- **Organizations / teams** with membership + **roles/permissions** (owner/admin/member). *(L)*
- **Tenant isolation** — every row, workspace, session, secret, and audit entry scoped to a
  tenant, enforced at the data layer, not just the UI. This likely means reworking the
  SQLite/runtime-KV store into a real multi-tenant database (Postgres). *(XL)*
- **SSO / SAML / SCIM** for enterprise (usually gated to a top tier). *(L, later)*
- Open question: retrofit tenancy into the current store, or a clean data-layer rebuild?
  The longer you wait, the more code assumes single-tenant.

### B. Data layer & persistence — **Foundational, L**
SQLite is single-node. Multi-tenant hosted SaaS needs a networked, backed-up, migratable DB
(Postgres is the default). Involves: schema migrations, connection pooling, per-tenant
scoping, backups/restore, and a migration path from the current KV model. Even self-hosted
benefits from this. *(L)*

### C. Billing & monetization — **Foundational (if hosted), M–L**
- Subscription + usage billing (Stripe is the default). *(M)*
- Plan tiers, quotas, and **enforcement** (seats, request/token limits, feature gates). *(M)*
- **Usage metering** — if you host inference or pass model costs through, you must meter
  tokens/requests per tenant accurately. *(M–L)*
- Trials, upgrades/downgrades, dunning, invoices. *(M)*
- Branches entirely on decisions #2/#3 above.

### D. Hosting, infra & scale — **Foundational (if hosted), L–XL**
- Cloud deployment of the backend/frontend (containerized; you already have images). *(M)*
- Horizontal scaling, load balancing, background job workers (agent runs are long-lived —
  they need a queue/worker model, not request threads). *(L)*
- **Model inference hosting** if you go that route: GPU provisioning, autoscaling, cost
  controls, cold-start management. This is its own product. *(XL)*
- IaC, environments (dev/staging/prod), CI/CD, secrets management. *(M–L)*
- Multi-region / data residency (enterprise + GDPR). *(L, later)*

### E. Security & compliance — **Differentiating, L (ongoing)**
This is your strength — lean in, and make it *provable*, not just architectural.
- **SOC 2 Type II** (and later ISO 27001) — table stakes for enterprise; 6–12 month effort
  of controls, policies, and audits. *(L, but calendar-bound — start early if enterprise.)*
- Secrets management (vault, rotation), dependency/vuln scanning, pen tests. *(M, ongoing)*
- Tenant data encryption at rest + in transit; key management; per-tenant isolation proofs.
- Turn the sandbox/Privacy-Lock work into **marketing-grade, documented guarantees** (a
  public security page, a whitepaper). Your Phase 3/4 work is a genuine sales asset. *(S–M)*
- Skill tool-call allowlisting (the residual surface flagged in THREAT_MODEL §6.2). *(M)*

### F. The core product — coding agent & orchestration — **Differentiating, L (ongoing)**
Where you compete with Cursor / Copilot / Codex / Devin / Claude Code.
- **Sharpen the wedge**: your differentiator is security + multi-model orchestration + a
  local option. Make that undeniable rather than trying to out-feature incumbents. *(ongoing)*
- Agent quality: better planning/execution loops, more/better tools, eval harnesses so you
  can *measure* quality and regressions (SWE-bench-style). *(L)*
- **WarSat as a headline product**: cost-aware multi-model routing (cheap model for easy
  steps, premium for hard ones) is a real, quantifiable value prop ("cut your LLM spend
  X%") — possibly a stronger wedge than "another coding agent." *(M–L)*
- IDE integrations (VS Code / JetBrains) if devs are the buyer. *(L)*
- A skill/plugin ecosystem — the sandbox you built makes third-party skills *safe*, which is
  a differentiator for a marketplace. *(L, later)*

### G. Onboarding, UX & self-serve — **Foundational (hosted), M–L**
- Self-serve signup → first value in minutes (no manual setup). *(M)*
- Onboarding flow, templates/examples, empty states, in-app guidance. *(M)*
- Docs site, quickstarts, API reference. *(M, ongoing)*
- Marketing site + pricing page. *(M)*

### H. Reliability & observability — **Scale, M–L**
- Uptime monitoring, error tracking (Sentry-style), structured logging, metrics/dashboards,
  alerting/on-call. *(M)*
- Status page, incident process, SLAs (enterprise). *(M, later)*
- Graceful degradation + rate limiting (you have some guardrails already). *(M)*

### I. Collaboration & team features — **Differentiating/Scale, L**
Shared workspaces, shared sessions/history, commenting, team knowledge/RAG, per-seat
management. Turns a single-player tool into a team product (and raises ACV). *(L)*

### J. API, extensibility & integrations — **Scale, M–L**
Public API + keys, webhooks, integrations (GitHub, Slack, CI), the skill marketplace. Lets
customers build on you and increases stickiness. *(M–L)*

### K. Support & operations — **Scale, M**
Support channels/ticketing, in-app help, admin tooling (impersonation, tenant management,
usage dashboards for *you*), abuse prevention. *(M)*

### L. Go-to-market & business ops — **Foundational (non-code), M**
Positioning, pricing model, landing page, analytics/attribution, legal (ToS, privacy policy,
DPA for enterprise), the LICENSE/CLA decision, and — if you host others' code/data —
serious thought about liability and abuse. *(M, mostly non-engineering.)*

---

## A possible sequencing (one opinionated path — adjust freely)

This assumes a **hosted SaaS, BYO-key first, dev/security-team customer**. Change the
assumptions and the order changes.

1. **Decide the strategic 5 above.** Everything branches here.
2. **Data layer → Postgres + multi-tenancy foundations** (A + B). The longer you wait, the
   more expensive. Do it before the codebase hardens around single-tenant.
3. **Accounts + orgs + auth** (A). Now you can have more than one customer.
4. **Hosting + background workers** (D, minus GPU inference). Get it running in the cloud.
5. **Billing + metering + plan gates** (C). Now you can charge.
6. **Onboarding + marketing site + docs** (G). Now people can find and start.
7. **Security as a product: SOC 2 kickoff + public security page** (E). Start the calendar
   early; lean on the sandbox work you already did.
8. **Sharpen the product wedge** (F) continuously throughout.
9. **Then**: teams (I), API/marketplace (J), observability/support hardening (H, K), hosted
   inference (D-XL) if/when the margins justify it.

**Phase 5 of the existing plan (installer + GHCR image + version UI) feeds the self-hosted
path directly** — if you lead with on-prem/self-hosted for the security buyer, that work is
your product, and the multi-tenant/billing items get lighter or deferred.

---

## Your likely moat (worth protecting in every decision)

Rasputin's defensible edge isn't "another coding agent" — it's **security-grade AI execution
+ multi-model orchestration + a real local/self-host option**. The sandboxing work you just
finished is a concrete, demonstrable asset most competitors lack. Whatever you build next,
the question to keep asking: *does this strengthen the "AI that can't hurt you / can't leak
your code / costs less to run" story, or dilute it by chasing feature parity?*

---

## What I'd want from you to turn this into a real plan

Pick a lane on the **strategic 5** (even tentatively), and I can turn any of these categories
into a concrete, staged implementation plan — the same design-then-review, verify-each-stage
approach we used for the sandbox work. Tell me which section you want to go deep on first.
