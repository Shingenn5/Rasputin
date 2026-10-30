import React from "react";

export function PageHeader({ title, text, action }) {
  return (
    <header className="page-header ras-runtime-hero">
      <div className="ras-runtime-hero-copy">
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      <div className="ras-runtime-hero-side">
        {action && <div className="ras-runtime-action">{action}</div>}
      </div>
    </header>
  );
}

export function formatRuntimeTime(value) {
  if (!value) return "Unknown";
  const numeric = Number(value);
  const date = new Date(numeric > 10_000_000_000 ? numeric : numeric * 1000);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}
