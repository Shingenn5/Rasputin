import test from "node:test";
import assert from "node:assert/strict";

import {
  PROMPT_RECIPES,
  RECIPE_MODES,
  buildRecipeObjective,
  featuredRecipes,
  missingRecipeFields,
  recipeAvailability,
  recipesForMode,
} from "../frontend-src/src/features/chat/promptRecipes.js";

test("every Rasputin mode has five distinct prompt recipes", () => {
  assert.deepEqual(RECIPE_MODES, ["chat", "analyze", "research", "code", "write", "organize", "review"]);
  for (const mode of RECIPE_MODES) {
    assert.equal(recipesForMode(mode).length, 5, `${mode} should have five recipes`);
  }
  assert.equal(new Set(PROMPT_RECIPES.map((item) => `${item.mode}:${item.id}`)).size, PROMPT_RECIPES.length);
});

test("featured recipes give each mode a discoverable entry point", () => {
  assert.deepEqual(
    featuredRecipes().map((item) => item.mode).sort(),
    [...RECIPE_MODES].sort(),
  );
});

test("recipe objectives substitute fields and omit empty optional label lines", () => {
  const item = recipesForMode("analyze").find((recipe) => recipe.id === "summarize-workspace");
  assert.ok(item);
  assert.equal(buildRecipeObjective(item, {}),
    "Analyze the active workspace. Summarize its purpose, major areas, important files, current state, obvious risks, and the most useful next actions. Cite workspace evidence for material claims.");
  assert.match(buildRecipeObjective(item, { focus: "security boundaries" }), /Focus: security boundaries$/);
});

test("required recipe fields are reported until completed", () => {
  const item = recipesForMode("code").find((recipe) => recipe.id === "add-feature");
  assert.deepEqual(missingRecipeFields(item, {} ).map((itemField) => itemField.id), ["feature", "acceptance"]);
  assert.deepEqual(missingRecipeFields(item, { feature: "Add recipes", acceptance: " " }).map((itemField) => itemField.id), ["acceptance"]);
  assert.deepEqual(missingRecipeFields(item, { feature: "Add recipes", acceptance: "Tests pass" }), []);
});

test("capability gates explain why a recipe cannot run", () => {
  const codeRecipe = recipesForMode("code")[0];
  const researchRecipe = recipesForMode("research")[0];
  const chatOnlyModel = { key: "chat-only", managed: true, toolSupport: "chat" };
  const parserModel = { key: "parser", managed: true, toolSupport: "chat", toolCallParser: "json" };
  const localUnmanagedModel = { key: "local", managed: false, toolSupport: "chat" };

  assert.match(recipeAvailability(codeRecipe, { model: chatOnlyModel }).reason, /chat-only/i);
  assert.equal(recipeAvailability(codeRecipe, { model: parserModel }).available, true);
  assert.equal(recipeAvailability(codeRecipe, { model: localUnmanagedModel }).available, true);
  assert.match(recipeAvailability(researchRecipe, { model: parserModel, allowWebSearch: false }).reason, /Web search is disabled/);
  assert.match(recipeAvailability(codeRecipe, { model: null }).reason, /No model is routed/);
});
