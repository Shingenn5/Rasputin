import React from "react";
import { Loader2 } from "lucide-react";

/* ─────────────────────────────────────────────
   Button with built-in loading state

   A thin wrapper over the existing .w2-button styling that adds a
   `loading` prop: while loading, the leading icon is swapped for a
   spinner, the button is disabled, and an optional loadingLabel
   replaces the text. Keeps every existing class/style hook intact so
   it's a drop-in for `<button className="w2-button ...">`.

   Usage:
     <Button primary loading={deploying} loadingLabel="Deploying…" icon={<Zap size={14} />} onClick={...}>
       Deploy
     </Button>
   ───────────────────────────────────────────── */

export function Button({
  children,
  loading = false,
  loadingLabel,
  icon,
  primary = false,
  className = "",
  disabled = false,
  type = "button",
  spinnerSize = 14,
  ...rest
}) {
  const classes = [
    "w2-button",
    primary ? "primary" : "",
    loading ? "is-loading" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading
        ? <Loader2 size={spinnerSize} className="ras-spin" aria-hidden="true" />
        : icon}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
