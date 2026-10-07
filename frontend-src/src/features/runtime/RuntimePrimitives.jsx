import React from "react";

export function PageHeader({ title, text, action }) {
  return (
    <header className="page-header ras-runtime-hero">
      <div className="ras-runtime-hero-copy">
        <span className="ras-runtime-kicker"><i aria-hidden="true" /> Local intelligence / {title}</span>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      <div className="ras-runtime-hero-side">
        <span className="ras-runtime-orbit" aria-hidden="true"><i /><b /></span>
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
