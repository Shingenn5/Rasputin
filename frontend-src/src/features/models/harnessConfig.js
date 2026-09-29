// Chat Completions adapters: keep credentials out of copied config files.
export function harnessConfigs(baseUrl, model) {
  if (!baseUrl || !model?.id) return null;
  const context = Math.max(512, Number(model.contextWindow) || 4096);
  const output = Math.min(4096, Math.floor(context / 4));
  return {
    opencode: JSON.stringify({
      $schema: "https://opencode.ai/config.json",
      model: `rasputin/${model.id}`,
      provider: {
        rasputin: {
          npm: "@ai-sdk/openai-compatible",
          name: "Rasputin",
          options: { baseURL: baseUrl, apiKey: "{env:RASPUTIN_API_KEY}" },
          models: { [model.id]: { name: model.name || model.id, limit: { context, output } } },
        },
      },
    }, null, 2),
    pi: JSON.stringify({
      providers: {
        rasputin: {
          baseUrl,
          api: "openai-completions",
          apiKey: "$RASPUTIN_API_KEY",
          authHeader: true,
          compat: { supportsDeveloperRole: false, supportsReasoningEffort: false },
          models: [{ id: model.id, name: model.name || model.id, reasoning: false,
            input: ["text"], contextWindow: context, maxTokens: output,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
        },
      },
    }, null, 2),
  };
}
