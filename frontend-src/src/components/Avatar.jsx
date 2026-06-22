import React from "react";
import { Bot, Cpu, Sparkles, Brain, Boxes } from "lucide-react";

const SIZES = { sm: 22, md: 28, lg: 34 };

function hashString(value) {
  let hash = 0;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function initialsFrom(name) {
  const cleaned = String(name || "").trim();
  if (!cleaned) return "?";
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Pick a per-provider icon from a model name / key heuristic.
function providerIcon(label) {
  const text = String(label || "").toLowerCase();
  if (/(llama|meta)/.test(text)) return Boxes;
  if (/(gpt|openai|o1|o3)/.test(text)) return Sparkles;
  if (/(claude|anthropic|opus|sonnet|haiku)/.test(text)) return Brain;
  if (/(mistral|mixtral|qwen|gemma|phi|deepseek)/.test(text)) return Cpu;
  return Bot;
}

/**
 * Lightweight initials-on-gradient avatar.
 * - kind="user": gradient + initials.
 * - kind="model": per-provider lucide icon on a gradient tuned by model name.
 */
export function Avatar({ name, kind = "user", size = "sm", title }) {
  const px = SIZES[size] || SIZES.sm;
  const hue = hashString(name) % 360;
  const style = {
    width: px,
    height: px,
    "--ras-avatar-hue": hue,
  };
  const label = title || name || (kind === "model" ? "Model" : "User");

  if (kind === "model") {
    const Icon = providerIcon(name);
    return (
      <span
        className="ras-avatar ras-avatar-model"
        style={style}
        role="img"
        aria-label={label}
        title={label}
      >
        <Icon size={Math.round(px * 0.52)} aria-hidden="true" />
      </span>
    );
  }

  return (
    <span
      className="ras-avatar ras-avatar-user"
      style={style}
      role="img"
      aria-label={label}
      title={label}
    >
      {initialsFrom(name)}
    </span>
  );
}

export default Avatar;
