import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const app = fs.readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");
const warsatView = fs.readFileSync(new URL("../frontend-src/src/features/warsat/WarsatView.jsx", import.meta.url), "utf8");
const warsatApi = fs.readFileSync(new URL("../backend/api/warsat_api.py", import.meta.url), "utf8");

test("Assistant model requests load, create, select, and expose fixed view props", () => {
  assert.match(app, /api\("\/api\/assistant\/model-requests"\)/);
  assert.match(app, /postJson\("\/api\/assistant\/model-requests", payload\)/);
  assert.match(app, /\/api\/assistant\/model-requests\/\$\{encodeURIComponent\(resolvedRequestId\)\}\/select/);
  assert.match(app, /modelRequests=\{assistantModelRequests\}/);
  assert.match(app, /requestModel=\{requestAssistantModel\}/);
  assert.match(app, /prepareModelRequest=\{prepareAssistantModelRequest\}/);
  assert.match(app, /openModels=\{\(\) => go\("models"\)\}/);
});

test("Selected recommendation preserves profile and uses the normal WarSat plan path", () => {
  assert.match(app, /selectedRequest\?\.recommendations\?\.find/);
  assert.match(app, /\.\.\.planSeed/);
  assert.match(app, /protocolId,/);
  assert.match(app, /role: candidate\.role/);
  assert.match(app, /strengthProfile: assistantProfileToWarsatStrengthProfile\(profile\)/);
  assert.match(app, /\["fast", "fastest", "fastest_practical"\]/);
  assert.match(app, /maximum_quality/);
  assert.match(app, /assistantRequestId: resolvedRequestId/);
});

test("WarSat plan preserves assistant correlation and shows its source", () => {
  assert.match(warsatApi, /assistant_request_id: str \| None = None/);
  assert.match(warsatApi, /plan\["assistantRequestId"\] = req\.assistant_request_id/);
  assert.match(app, /assistantRequestId: options\.assistantRequestId/);
  assert.match(app, /assistantRequestId: warsatPlan\.assistantRequestId/);
  assert.match(warsatView, /plan\.assistantRequestId/);
  assert.match(warsatView, /Requested by Personal Assistant/);
});

test("Only selected verification after final registration selects the model", () => {
  assert.match(app, /deployment\.status === "registered" && deployment\.modelKey && assistantRequestId/);
  assert.match(app, /\/api\/assistant\/model-requests\/\$\{encodeURIComponent\(assistantRequestId\)\}\/verify/);
  assert.match(app, /\{ modelKey: deployment\.modelKey \}/);
  assert.match(app, /verification\?\.status === "selected"/);
  assert.match(app, /setSelectedModel\(deployment\.modelKey\)/);
  assert.doesNotMatch(app, /deployment\.status === "starting"[\s\S]{0,500}setSelectedModel\(deployment\.modelKey\)/);
  assert.doesNotMatch(app, /deployment\.status === "failed"[\s\S]{0,500}setSelectedModel\(deployment\.modelKey\)/);
  assert.doesNotMatch(app, /verification\.status === "unqualified"[\s\S]{0,300}setSelectedModel\(deployment\.modelKey\)/);
});
