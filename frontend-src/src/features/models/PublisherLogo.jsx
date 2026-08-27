import React from "react";

const BRAND_RULES = [
  { id: "qwen", label: "Qwen", glyph: "Q", match: /qwen|alibaba|tongyi/ },
  { id: "deepseek", label: "DeepSeek", glyph: "D", match: /deepseek/ },
  { id: "meta", label: "Meta", glyph: "∞", match: /meta|llama/ },
  { id: "mistral", label: "Mistral AI", glyph: "M", match: /mistral|mixtral/ },
  { id: "google", label: "Google", glyph: "G", match: /google|gemma|gemini/ },
  { id: "microsoft", label: "Microsoft", glyph: "⊞", match: /microsoft|phi-/ },
  { id: "openai", label: "OpenAI", glyph: "◉", match: /openai|gpt-|o1|o3/ },
  { id: "anthropic", label: "Anthropic", glyph: "AI", match: /anthropic|claude/ },
  { id: "huggingface", label: "Hugging Face", glyph: "🤗", match: /huggingface|hugging face/ },
  { id: "nvidia", label: "NVIDIA", glyph: "N", match: /nvidia|nemotron/ },
];

function publisherText(item) {
  const modelId = String(item?.modelId || item?.model || item?.id || item?.name || item?.key || "");
  return [item?.publisher, item?.provider, modelId.split("/")[0], modelId].filter(Boolean).join(" ");
}

export function publisherBrand(item) {
  const source = publisherText(item).toLowerCase();
  const known = BRAND_RULES.find((brand) => brand.match.test(source));
  if (known) return known;
  const publisher = String(item?.publisher || item?.provider || source.split("/")[0] || "Local");
  return { id: "local", label: publisher, glyph: publisher.slice(0, 2).toUpperCase() || "AI" };
}

export function PublisherLogo({ item, size = "md" }) {
  const brand = publisherBrand(item);
  return (
    <span
      className={`model-publisher-logo is-${brand.id} size-${size}`}
      role="img"
      aria-label={`${brand.label} logo`}
      title={brand.label}
    >
      <span aria-hidden="true">{brand.glyph}</span>
    </span>
  );
}

export default PublisherLogo;
