import assert from "node:assert/strict";
import test from "node:test";
import { harnessConfigs } from "../frontend-src/src/features/models/harnessConfig.js";

test("harness configs use gateway model IDs, Chat Completions and environment credentials", () => {
  const configs = harnessConfigs("http://127.0.0.1:8899/v1", { id: "auto-coder-123", name: "Coder", contextWindow: 32768 });
  const opencode = JSON.parse(configs.opencode);
  assert.equal(opencode.model, "rasputin/auto-coder-123");
  assert.equal(opencode.provider.rasputin.options.baseURL, "http://127.0.0.1:8899/v1");
  assert.equal(opencode.provider.rasputin.npm, "@ai-sdk/openai-compatible");
  assert.equal(opencode.provider.rasputin.options.apiKey, "{env:RASPUTIN_API_KEY}");
  assert.equal(opencode.provider.rasputin.models["auto-coder-123"].limit.context, 32768);
  const pi = JSON.parse(configs.pi).providers.rasputin;
  assert.equal(pi.api, "openai-completions");
  assert.equal(pi.apiKey, "$RASPUTIN_API_KEY");
  assert.equal(pi.models[0].id, "auto-coder-123");
  assert.equal(pi.models[0].maxTokens, 4096);
});

test("missing models cannot produce configs and unknown context is bounded conservatively", () => {
  assert.equal(harnessConfigs("http://localhost/v1", null), null);
  const config = JSON.parse(harnessConfigs("http://localhost/v1", { id: "coder" }).pi);
  assert.equal(config.providers.rasputin.models[0].contextWindow, 4096);
});
