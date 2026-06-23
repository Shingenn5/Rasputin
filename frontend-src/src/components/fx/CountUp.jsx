import React, { useEffect, useRef, useState } from "react";

/* Animated number that counts up to `value` on mount/change.
   Supports a numeric value with optional prefix/suffix; falls back to
   rendering non-numeric values (e.g. "Locked") as-is. */
export function CountUp({ value, duration = 900, decimals = 0, prefix = "", suffix = "", className }) {
  const numeric = typeof value === "number" ? value : Number(String(value).replace(/[^0-9.-]/g, ""));
  const isNumeric = Number.isFinite(numeric) && /[0-9]/.test(String(value));
  const [display, setDisplay] = useState(isNumeric ? 0 : value);
  const raf = useRef(null);

  useEffect(() => {
    if (!isNumeric) { setDisplay(value); return undefined; }
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setDisplay(numeric); return undefined; }
    const start = performance.now();
    const from = 0;
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setDisplay(from + (numeric - from) * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => raf.current && cancelAnimationFrame(raf.current);
  }, [numeric, isNumeric, value, duration]);

  const text = isNumeric
    ? `${prefix}${Number(display).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`
    : display;

  return <span className={className}>{text}</span>;
}
