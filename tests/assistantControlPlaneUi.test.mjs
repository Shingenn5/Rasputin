import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../frontend-src/src/features/assistant/AssistantView.jsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../frontend-src/src/styles/rasputin.css", import.meta.url), "utf8");

const advancedGroups = [
  "assistant-advanced-diagnostics",
  "assistant-advanced-identity",
  "assistant-advanced-planning",
  "assistant-advanced-model-voice",
  "assistant-advanced-ledger",
  "assistant-advanced-handoffs",
];

test("essential control plane is the default visible surface", () => {
  assert.match(source, /data-testid="assistant-essential-control-plane"/);
  assert.match(source, /data-testid="assistant-workflow-launcher"/);
  assert.match(source, /data-testid="assistant-command-preview"/);
  assert.match(source, /data-testid="assistant-needs-attention"/);
  assert.match(source, /useState\("fast"\)/);
  assert.match(source, /Fastest practical/);
  assert.match(source, /Balanced/);
  assert.match(source, /Largest capable model/);
  assert.match(source, /role="radiogroup" aria-label="Performance profile"/);
});

test("capability setup payloads contain roles, requirements, and the selected profile", () => {
  assert.match(source, /role: "main"/);
  assert.match(source, /role: "coder"/);
  assert.match(source, /role: "researcher"/);
  assert.match(source, /required: \["chat"\]/);
  assert.match(source, /required: \["chat", "code", "tools"\]/);
  assert.match(source, /required: \["chat", "reasoning", "summarize"\]/);
  assert.match(source, /profile: performanceProfile/);
  assert.match(source, /requestModel\?\.\(capability\.requirements\)/);
  assert.match(source, /recommendation_ready/);
  assert.match(source, /candidate_selected/);
  assert.match(source, /selected/);
  assert.match(source, /unqualified/);
  assert.match(source, /blocked/);
  assert.match(source, /firstUnblockedRecommendation/);
  assert.match(source, /prepareModelRequest\?\.\(modelRequestId\(capability\.request\), modelCandidateId\(capability\.recommendation\)\)/);
});

test("TPS is evidence-only and voice stays out of model requests", () => {
  assert.match(source, /Measured TPS evidence/);
  assert.match(source, /Estimated TPS evidence/);
  assert.match(source, /Catalog recommendation only; live compatibility is not verified\./);
  const voiceCard = source.match(/<Col xl=\{4\} md=\{6\} data-testid="assistant-capability-voice">[\s\S]*?<\/Col>/)?.[0];
  assert.ok(voiceCard, "voice essential capability card should exist");
  assert.match(voiceCard, /dedicated local speech models/);
  assert.match(voiceCard, /never sent to WarSat/);
  assert.match(voiceCard, /openModels\?\.\(\)/);
  assert.doesNotMatch(voiceCard, /requestModel|prepareModelRequest/);
});

test("workflow launchers require exact-profile verified readiness", () => {
  assert.match(source, /\(request\.profile \|\| "fast"\) === performanceProfile/);
  assert.doesNotMatch(source, /\) \|\| modelRequestItems\.find/);
  assert.match(source, /workflowReady \? openWorkflow/);
  assert.match(source, /disabled=\{deploymentPending\}/);
  assert.match(source, /WarSat deployment pending/);
});

test("advanced content remains mounted in native closed details groups", () => {
  for (const testId of advancedGroups) {
    const group = source.match(new RegExp(`<details[^>]*data-testid="${testId}"[\\s\\S]*?<\\/details>`))?.[0];
    assert.ok(group, `${testId} should be a native details group`);
    assert.doesNotMatch(group.match(/^<details[^>]*>/)?.[0] || "", /\\bopen\\b/);
    assert.match(group, /<summary>/);
  }
  assert.match(source, /<VoiceConsole \/>/);
  assert.match(source, /data-testid="assistant-identity-card"/);
  assert.match(source, /data-testid="assistant-plan-composer"/);
  assert.match(source, /data-testid="assistant-model-packs"/);
  assert.match(source, /data-testid="assistant-plan-ledger"/);
  assert.match(source, /data-testid="assistant-handoffs"/);
});

test("legacy assistant callbacks and voice testids remain present", () => {
  for (const callback of [
    "createPlan",
    "saveModelPack",
    "reviewPlan",
    "requestHandoff",
    "prepareHandoff",
    "dispatchHandoff",
    "previewVoice",
    "previewCommand",
    "previewContext",
    "saveProfile",
    "createContextCapsule",
    "reviewContextCapsule",
    "openWorkflow",
  ]) {
    assert.match(source, new RegExp(`\\b${callback}\\b`), `${callback} callback should remain wired`);
  }
  for (const testId of [
    "assistant-view",
    "assistant-workflow-launcher",
    "assistant-capability-contracts",
    "assistant-command-preview",
    "assistant-voice-console",
    "assistant-voice-toggle",
    "assistant-voice-audio",
    "assistant-voice-response",
    "assistant-voice-model-readiness",
    "assistant-voice-profile",
    "assistant-plan-composer",
    "assistant-model-packs",
    "assistant-plan-ledger",
    "assistant-handoffs",
  ]) {
    assert.match(source, new RegExp(`data-testid="${testId}"`), `${testId} should remain present`);
  }
});

test("assistant-scoped styles provide visible keyboard focus for summaries and actions", () => {
  assert.match(styles, /\.assistant-dashboard/);
  assert.match(styles, /\.assistant-advanced-group > summary:focus-visible/);
  assert.match(styles, /\.assistant-essential-capability button:focus-visible/);
  assert.match(styles, /\.assistant-advanced-group > summary::before/);
});
