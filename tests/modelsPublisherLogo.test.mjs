import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../frontend-src/src/features/models/PublisherLogo.jsx", import.meta.url), "utf8");

test("publisher logo resolves developer and trainer metadata", () => {
  for (const field of ["developer", "developerName", "trainer", "author", "organization", "org", "lab"]) {
    assert.ok(source.includes(`item?.${field}`), `publisher matching should inspect ${field}`);
  }
  for (const brand of ["qwen", "deepseek", "meta", "mistral", "google", "microsoft", "openai", "anthropic", "huggingface", "nvidia"]) {
    assert.ok(source.includes(`id: "${brand}"`), `missing bundled ${brand} mark`);
  }
});

test("known publisher marks render bundled SVGs and fallback stays deterministic", () => {
  assert.ok(source.includes("function Mark({ id })"));
  assert.ok(source.includes("return <svg {...props}>"));
  assert.ok(source.includes("data-brand={brand.id}"));
  assert.ok(source.includes('brand.id === "local"'));
  assert.ok(!source.includes("glyph:"));
});
