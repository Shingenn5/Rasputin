import test from "node:test";
import assert from "node:assert/strict";
import { formatGenerationMetrics } from "../frontend-src/src/lib/generationMetrics.js";

test("slow historical requests never render a rounded zero or pretend to have decode timings", () => {
  const view = formatGenerationMetrics({ tokensPerSecond: 0.04, outputTokens: 2 });
  assert.equal(view.tokensPerSecond, "0.04 tok/s (estimated)");
  assert.equal(view.decodeSpeed, "Unavailable");
  assert.equal(view.firstToken, "Unavailable");
  assert.equal(formatGenerationMetrics({ tokensPerSecond: 0.001 }).tokensPerSecond, "<0.01 tok/s (estimated)");
});

test("native decode speed and first-token delay remain independent of request throughput", () => {
  const view = formatGenerationMetrics({ tokensPerSecond: 0.04, outputTokens: 2, tokenCountSource: "exact", lastDecodeTokensPerSecond: 11.21, lastTimeToFirstTokenSeconds: 1.656, lastPromptSeconds: 1.502, lastGenerationSeconds: 3.708 });
  assert.equal(view.decodeSpeed, "11.2 tok/s");
  assert.equal(view.firstToken, "1.66 s");
  assert.equal(view.promptTime, "1.50 s");
  assert.equal(view.requestTime, "3.71 s");
  assert.equal(view.tokensPerSecond, "0.04 tok/s (exact)");
  assert.equal(view.outputTokens, "2");
});

test("absent, invalid and zero rates are unavailable", () => {
  for (const value of [null, undefined, 0, -1, NaN, Infinity, "bad"]) {
    const view = formatGenerationMetrics({ tokensPerSecond: value, lastDecodeTokensPerSecond: value });
    assert.equal(view.tokensPerSecond, "Unavailable");
    assert.equal(view.decodeSpeed, "Unavailable");
  }
});
