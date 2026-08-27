import React from "react";

// These are intentionally small, code-native marks. Keeping them in the bundle means
// the model browser still identifies a lab when it is offline or behind a firewall.
const BRAND_RULES = [
  { id: "qwen", label: "Qwen / Alibaba Cloud", match: /qwen|alibaba|tongyi/ },
  { id: "deepseek", label: "DeepSeek", match: /deepseek/ },
  { id: "meta", label: "Meta", match: /meta|llama/ },
  { id: "mistral", label: "Mistral AI", match: /mistral|mixtral/ },
  { id: "google", label: "Google DeepMind", match: /deepmind|google|gemma|gemini/ },
  { id: "microsoft", label: "Microsoft", match: /microsoft|phi-/ },
  { id: "openai", label: "OpenAI", match: /openai|gpt-|o1|o3/ },
  { id: "anthropic", label: "Anthropic", match: /anthropic|claude/ },
  { id: "huggingface", label: "Hugging Face", match: /huggingface|hugging face/ },
  { id: "nvidia", label: "NVIDIA", match: /nvidia|nemotron/ },
];

function publisherText(item) {
  const modelId = String(item?.modelId || item?.model || item?.id || item?.name || item?.key || "");
  const metadata = item?.metadata || item?.modelInfo || {};
  return [
    item?.publisher,
    item?.provider,
    item?.developer,
    item?.developerName,
    item?.trainer,
    item?.author,
    item?.organization,
    item?.org,
    item?.lab,
    metadata.publisher,
    metadata.provider,
    metadata.developer,
    metadata.author,
    modelId.split("/")[0],
    modelId,
  ].filter(Boolean).join(" ");
}

export function publisherBrand(item) {
  const source = publisherText(item).toLowerCase();
  const known = BRAND_RULES.find((brand) => brand.match.test(source));
  if (known) return known;
  const publisher = String(item?.publisher || item?.provider || item?.developer || source.split("/")[0] || "Local");
  return { id: "local", label: publisher, match: null };
}

function Mark({ id }) {
  const props = { viewBox: "0 0 24 24", fill: "none", xmlns: "http://www.w3.org/2000/svg", focusable: "false", "aria-hidden": "true" };
  switch (id) {
    case "qwen":
      return <svg {...props}><path d="M12 2.5c2.1 0 3.8 1.1 4.8 2.8 2 .3 3.6 1.6 4.2 3.5.6 2-.1 4-1.6 5.3.3 2-.5 4-2.1 5.2-1.6 1.2-3.7 1.3-5.3.4-1.7.9-3.8.8-5.4-.4-1.6-1.2-2.4-3.2-2.1-5.2-1.5-1.3-2.2-3.3-1.6-5.3.6-1.9 2.2-3.2 4.2-3.5C8.2 3.6 9.9 2.5 12 2.5Z" fill="currentColor" opacity=".22"/><path d="M8.1 11.9c1.1-2.2 3.1-3.3 5.4-2.8 1.6.3 2.7 1.4 3 2.8.3 1.8-.7 3.2-2.2 4.1M7.6 12.2c.1 2 1 3.4 2.6 4.3 1.2.7 2.5.6 3.7-.1M8.7 6.4c1.8.3 3.1 1.2 4 2.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>;
    case "deepseek":
      return <svg {...props}><path d="M3.1 13.8c1.2-3.8 4.4-6.2 8.4-6.2 2.7 0 5.1 1 6.8 2.8 1.1-.1 2 .1 2.7.7-.7.4-1.2 1-1.4 1.8 0 3.2-3 5.3-7 5.3H8.7c-2.8 0-4.8-1.6-5.6-4.4Z" fill="currentColor" opacity=".2"/><path d="M3.1 13.8c1.2-3.8 4.4-6.2 8.4-6.2 2.7 0 5.1 1 6.8 2.8 1.1-.1 2 .1 2.7.7-.7.4-1.2 1-1.4 1.8 0 3.2-3 5.3-7 5.3H8.7c-2.8 0-4.8-1.6-5.6-4.4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><circle cx="10" cy="13" r=".9" fill="currentColor"/><circle cx="14" cy="13" r=".9" fill="currentColor"/><path d="M8.7 16c1.7.8 3.3.8 5 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>;
    case "meta":
      return <svg {...props}><path d="M3.5 15.3c0-3.8 1.6-6.2 3.8-6.2 2.2 0 3.1 2.4 4.7 5.1 1.6 2.7 2.5 5.1 4.7 5.1 2.2 0 3.8-2.4 3.8-6.2 0-3.8-1.6-6.2-3.8-6.2-2.2 0-3.1 2.4-4.7 5.1-1.6 2.7-2.5 5.1-4.7 5.1-2.2 0-3.8-2.4-3.8-6.2Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>;
    case "mistral":
      return <svg {...props}><path d="M4 5h16v3H4zM4 10.5h10v3H4zM4 16h16v3H4z" fill="currentColor"/><path d="M17 10.5h3v3h-3z" fill="currentColor" opacity=".5"/></svg>;
    case "google":
      return <svg {...props}><path d="M20.4 12.2c0-.6-.1-1.1-.2-1.7H12v3.2h4.7c-.2 1-.8 1.8-1.7 2.4v2h2.7c1.6-1.5 2.7-3.6 2.7-5.9Z" fill="currentColor"/><path d="M12 20.7c2.3 0 4.2-.8 5.7-2.2l-2.7-2c-.8.5-1.8.8-3 .8-2.3 0-4.2-1.5-4.9-3.6H4.3v2.1c1.5 2.9 4.4 4.9 7.7 4.9Z" fill="currentColor" opacity=".75"/><path d="M7.1 13.7a5.3 5.3 0 0 1 0-3.4V8.2H4.3a8.7 8.7 0 0 0 0 7.6l2.8-2.1Z" fill="currentColor" opacity=".55"/><path d="M12 6.7c1.3 0 2.5.5 3.4 1.4l2.5-2.5C16.2 4.1 14.3 3.3 12 3.3c-3.3 0-6.2 1.9-7.7 4.9l2.8 2.1C7.8 8.2 9.7 6.7 12 6.7Z" fill="currentColor" opacity=".9"/></svg>;
    case "microsoft":
      return <svg {...props}><path d="M3 3h8.3v8.3H3zM12.7 3H21v8.3h-8.3zM3 12.7h8.3V21H3zM12.7 12.7H21V21h-8.3z" fill="currentColor"/></svg>;
    case "openai":
      return <svg {...props}><path d="m12 3.2 3 1.7 3.1-.1 1.6 3-1.1 2.9 1.1 2.9-1.6 3-3.1-.1-3 1.7-3-1.7-3.1.1-1.6-3 1.1-2.9-1.1-2.9 1.6-3 3.1.1 3-1.7Z" stroke="currentColor" strokeWidth="1.45" strokeLinejoin="round"/><path d="m9 7.3 3-1.7 3 1.7v3.4l-3 1.7-3-1.7V7.3Zm0 3.4-3 1.7v3.4l3 1.7 3-1.7m0-3.4 3 1.7v3.4l-3 1.7m0-6.8V17" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round"/></svg>;
    case "anthropic":
      return <svg {...props}><path d="m12 3 8.3 18h-3.8l-1.8-4.2H9.2L7.4 21H3.7L12 3Zm0 5.2-1.7 5.1h3.4L12 8.2Z" fill="currentColor"/></svg>;
    case "huggingface":
      return <svg {...props}><circle cx="12" cy="12" r="8.7" stroke="currentColor" strokeWidth="1.5"/><circle cx="8.7" cy="11" r="1.1" fill="currentColor"/><circle cx="15.3" cy="11" r="1.1" fill="currentColor"/><path d="M7.5 14.2c1.3 2 7.7 2 9 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M7.4 6.5 6 4.2M16.6 6.5 18 4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>;
    case "nvidia":
      return <svg {...props}><path d="M3 10.2c2.5-2.9 6.1-4.1 10-3.2 2.2.5 4 1.6 5.4 3.3-1.6-1-3.5-1.3-5.3-.8-1.8.5-3.3 1.7-4.2 3.4-.5.9-.8 1.8-1 2.8-2.3-.7-4-2.7-4.9-5.5Z" stroke="currentColor" strokeWidth="1.5"/><circle cx="12.4" cy="12.2" r="2.2" stroke="currentColor" strokeWidth="1.5"/><path d="M3 17.7c2.4 1.2 5.1 1.7 7.8 1.3 3.8-.5 6.8-2.9 8.6-6.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>;
    default:
      return null;
  }
}

export function PublisherLogo({ item, size = "md" }) {
  const brand = publisherBrand(item);
  const fallback = brand.label.slice(0, 2).toUpperCase() || "AI";
  return (
    <span
      className={`model-publisher-logo is-${brand.id} size-${size}`}
      data-brand={brand.id}
      role="img"
      aria-label={`${brand.label} logo`}
      title={brand.label}
    >
      <Mark id={brand.id} />
      {brand.id === "local" ? <span aria-hidden="true">{fallback}</span> : null}
    </span>
  );
}

export default PublisherLogo;
