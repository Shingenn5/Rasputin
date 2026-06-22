import React from "react";

/* ─────────────────────────────────────────────
   Skeleton loading primitives

   Shimmer placeholders that match the shape of the content they stand
   in for, so loading reads as "content arriving" rather than a blank
   panel. Built on the shared design tokens; respects reduced-motion.

   Usage:
     <Skeleton width="60%" height={14} />
     <SkeletonText lines={3} />
     <SkeletonCard />               // generic card-shaped placeholder
     <SkeletonList count={5} />     // a stack of SkeletonCards
   ───────────────────────────────────────────── */

export function Skeleton({ width, height, radius, style, className = "" }) {
  return (
    <span
      className={`ras-skeleton ${className}`}
      style={{
        width: width ?? "100%",
        height: height ?? 12,
        borderRadius: radius ?? "var(--radius-sm)",
        ...style,
      }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3, gap = "var(--sp-2)" }) {
  return (
    <span className="ras-skeleton-text" style={{ gap }} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height={11}
          // Last line is shorter, like real wrapped text.
          width={i === lines - 1 ? "55%" : "100%"}
        />
      ))}
    </span>
  );
}

export function SkeletonCard() {
  return (
    <div className="ras-skeleton-card" aria-hidden="true">
      <div className="ras-skeleton-card__head">
        <Skeleton width={36} height={36} radius="var(--radius)" />
        <div className="ras-skeleton-card__head-text">
          <Skeleton width="45%" height={13} />
          <Skeleton width="70%" height={10} />
        </div>
      </div>
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonList({ count = 4 }) {
  return (
    <div className="ras-skeleton-list" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
