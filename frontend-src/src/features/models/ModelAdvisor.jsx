import {
  Cloud,
  Database,
  Gauge,
  Play,
  RefreshCw,
} from "lucide-react";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { Card } from "@/components/ui/card.jsx";
import { advisorProfileSlots } from "./advisorSelection.js";

function AdvisorRecommendationCard({ slot, winner, prepareCatalogModelForWarsat, desktopOnly = false, primary = false }) {
  const item = winner?.item;
  const profile = winner?.profile;
  const blockers = profile?.blockers || [];
  const blocked = !profile || blockers.length > 0 || profile?.raw?.status === "blocked";
  const modelName = item?.name || profile?.modelRef || "No model selected";
  const runtimeOption = item?.runtimeOptions?.find((option) => option?.protocolId === profile?.protocolId);
  const runtimeLabel = runtimeOption?.label || item?.runtime || "Warsat runtime";
  const deviceLabel = profile
    ? (profile.placement?.label || profile.placementMode || "Hardware placement")
      + (profile.deviceIds?.length ? " (" + profile.deviceIds.join(", ") + ")" : "")
    : "Waiting for advisor";
  const contextLabel = profile?.contextWindow ? Number(profile.contextWindow).toLocaleString() + " tokens" : "Automatic/default";
  const why = blocked
    ? "This profile is shown for transparency but cannot be deployed until its blockers are resolved."
    : profile.evidenceLabel === "Measured"
      ? "Fresh measured evidence supports this model and runtime on the available hardware."
      : profile.evidenceLabel === "Estimated"
        ? "This is a catalog-based fit estimate; benchmark it locally before relying on peak speed."
        : "No measured or catalog estimate is available yet, so treat this as exploratory.";
  return (
    <Card data-testid={"advisor-recommendation-" + slot.key} className={"flex h-full flex-col gap-3 p-4 " + (primary ? "border-primary/50 bg-primary/5" : "")}>
      <div className="models-card-heading flex min-w-0 items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-primary">{primary ? "Best match for your computer" : slot.label}</div>
          <h3 className="mt-1 text-base font-semibold">{modelName}</h3>
        </div>
        <Badge variant={blocked ? "down" : profile?.evidenceLabel === "Measured" ? "up" : "muted"}>
          {profile?.evidenceLabel || "Unverified"}
        </Badge>
      </div>
      <p className="m-0 text-xs text-muted-foreground">{slot.goal}</p>
      {!profile && (
        <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-xs text-muted-foreground">
          No profile is available yet. The advisor will retry when a deployable, unblocked catalog candidate and hardware snapshot are ready.
        </div>
      )}
      {profile && (
        <>
          <details className="model-recommendation-details rounded-lg border border-border bg-muted/20 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-foreground">Technical details</summary>
            <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
            <div><strong className="text-foreground">Runtime / protocol:</strong> {runtimeLabel} · {profile.protocolId || "Unspecified"}</div>
            <div><strong className="text-foreground">GPU placement:</strong> {deviceLabel}</div>
            <div><strong className="text-foreground">Context:</strong> {contextLabel}</div>
            <div>
              <strong className="text-foreground">Measured TPS / TTFT:</strong>{" "}
              {profile.measuredTps == null ? "unavailable" : profile.measuredTps + " TPS"}
              {" · "}
              {profile.measuredTtft == null ? "unavailable" : profile.measuredTtft + " ms TTFT"}
            </div>
            </div>
          </details>
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <strong className="text-foreground">Why this recommendation:</strong> {why}
            {Number.isFinite(profile.profileScore) && <span> Profile score: {profile.profileScore.toFixed(1)}.</span>}
          </div>
          {blockers.length > 0 && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              <strong>Blocked:</strong> {blockers.join(" ")}
            </div>
          )}
          {profile.warnings?.length > 0 && (
            <div className="text-xs text-amber-400">{profile.warnings.join(" ")}</div>
          )}
        </>
      )}
      <div className="mt-auto flex items-center gap-2">
        <UIButton
          size="sm"
          type="button"
          disabled={blocked}
          title={blocked ? blockers.join(" ") || "This recommendation is not deployable." : undefined}
          onClick={() => {
            const planSeed = profile.planSeed || {};
            prepareCatalogModelForWarsat?.(item, {
              ...planSeed,
              strengthProfile: slot.backendProfile,
              protocolId: planSeed.protocolId || profile.protocolId,
              contextWindow: planSeed.contextWindow || profile.contextWindow || undefined,
              toolCallParser: planSeed.toolCallParser || profile.toolCallParser || undefined,
            });
          }}
        >
          <Play size={12} /> {desktopOnly ? "Download GGUF" : "Review WarSat plan"}
        </UIButton>
        {blocked && <span className="text-[0.7rem] text-muted-foreground">Resolve blockers first</span>}
      </div>
    </Card>
  );
}

export function GuidedRecommendations({
  advisorState,
  advisorCandidateCount,
  modelCatalogLoading,
  catalogError,
  hardwareProbeState,
  hardwareSnapshot,
  hardwareReady,
  performancePreference,
  automaticBenchmarking,
  onRefresh,
  onBrowseAll,
  onUseSpecificModel,
  prepareCatalogModelForWarsat,
  desktopOnly = false,
}) {
  const loading = ["loading", "hardware-loading", "catalog-loading"].includes(advisorState.status) || modelCatalogLoading;
  const preferredSlotKey = performancePreference === "responsive"
    ? "fast"
    : performancePreference === "maximum_quality" ? "maximumQuality" : "balanced";
  const primarySlot = advisorProfileSlots.find((slot) => slot.key === preferredSlotKey) || advisorProfileSlots[1];
  const alternativeSlots = advisorProfileSlots.filter((slot) => slot.key !== primarySlot.key);
  const statusText = modelCatalogLoading || advisorState.status === "catalog-loading"
    ? "Loading the local model catalog…"
    : advisorState.status === "hardware-loading"
      ? "Waiting for a hardware snapshot before requesting recommendations…"
      : advisorState.status === "hardware-error"
        ? advisorState.reason || "GPU detection failed, so placement is unproven."
        : advisorState.status === "hardware-blocked"
          ? advisorState.reason || "Hardware snapshot received, but deployment is blocked."
          : advisorState.status === "catalog-empty"
            ? advisorState.reason || "The hardware snapshot is ready, but the local model catalog is empty."
            : advisorState.status === "no-deployable-candidates"
              ? advisorState.reason || "No deployable, unblocked catalog candidates are available."
              : advisorState.status === "loading"
                ? "Analyzing up to " + advisorCandidateCount + " deployable candidates…"
                : advisorState.status === "error"
                  ? "The advisor could not complete any candidate request."
                  : advisorCandidateCount
                    ? "Recommendations are ready."
                    : "No deployable, unblocked catalog candidates are available yet.";
  return (
    <section aria-labelledby="guided-recommendations-title" data-testid="guided-recommendations" className="mb-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Gauge size={18} className="text-primary" />
            <h2 id="guided-recommendations-title" className="m-0 text-xl font-semibold">Recommended for this computer</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Start with one best match, choose a specific Hugging Face model, or explore the full catalog.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <UIButton variant="outline" size="sm" type="button" onClick={onRefresh} disabled={loading} aria-label="Refresh model recommendations">
            <RefreshCw size={14} /> {loading ? "Analyzing…" : "Refresh recommendations"}
          </UIButton>
          <UIButton variant="outline" size="sm" type="button" onClick={onUseSpecificModel} data-testid="use-specific-hf-model">
            <Cloud size={14} /> Use a specific Hugging Face model
          </UIButton>
          <UIButton variant="default" size="sm" type="button" onClick={onBrowseAll}>
            <Database size={14} /> Browse full catalog
          </UIButton>
        </div>
      </div>
      <div aria-live="polite" role="status" className="mb-3 text-xs text-muted-foreground">
        {statusText}
        {advisorState.completed != null && advisorState.total ? " " + advisorState.completed + "/" + advisorState.total + " complete." : ""}
        {advisorState.errors?.length > 0 && " " + advisorState.errors.slice(0, 2).join(" ")}
      </div>
      {catalogError && (
        <div role="alert" className="mb-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          Catalog warning: {catalogError}
        </div>
      )}
      {advisorState.status === "hardware-blocked" && (
        <div role="alert" data-testid="hardware-blocked-reasons" className="mb-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          <strong>Hardware snapshot received.</strong> Deployment remains blocked until the following prerequisites are resolved.
          {advisorState.hardwareReasons?.length > 0 && <div className="mt-1"><strong>Blockers:</strong> {advisorState.hardwareReasons.join(" ")}</div>}
          {advisorState.hardwareRecommendations?.length > 0 && <div className="mt-1"><strong>Next steps:</strong> {advisorState.hardwareRecommendations.join(" ")}</div>}
          {advisorState.hardwareChecks?.length > 0 && <div className="mt-1 text-muted-foreground"><strong>Checks:</strong> {advisorState.hardwareChecks.join(" ")}</div>}
        </div>
      )}
      {advisorState.status === "hardware-error" && (
        <div role="alert" className="mb-3 rounded-lg border border-amber-400/40 bg-amber-400/5 px-3 py-2 text-xs text-amber-300">
          {advisorState.reason} Use Refresh recommendations to retry; model cards will remain blocked until hardware or exact runtime evidence is available.
        </div>
      )}
      {advisorState.status === "hardware-loading" && !hardwareSnapshot?.received && !modelCatalogLoading && (
        <div role="alert" className="mb-3 rounded-lg border border-amber-400/40 bg-amber-400/5 px-3 py-2 text-xs text-amber-300">
          {hardwareProbeState?.status === "loading"
            ? "Detecting GPU capacity locally before ranking recommendations…"
            : "Waiting for a hardware snapshot before requesting recommendations…"}
        </div>
      )}
      <div className="mb-3 text-xs text-muted-foreground">
        Default preference: <strong className="text-foreground">{performancePreference}</strong>
        {" · "}
        Automatic benchmarking: <strong className="text-foreground">{automaticBenchmarking ? "on" : "off"}</strong>
      </div>
      <div className="max-w-3xl" data-testid="primary-model-recommendation">
        <AdvisorRecommendationCard
          slot={primarySlot}
          winner={advisorState.profiles?.[primarySlot.key]}
          prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
          desktopOnly={desktopOnly}
          primary
        />
      </div>
      <details className="model-alternatives mt-4 rounded-xl border border-border bg-card p-4" data-testid="model-alternatives">
        <summary className="cursor-pointer text-sm font-semibold">Compare alternatives</summary>
        <p className="mt-2 text-xs text-muted-foreground">Fast, balanced, and maximum-quality options remain available when you want more control.</p>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          {alternativeSlots.map((slot) => (
            <AdvisorRecommendationCard
              key={slot.key}
              slot={slot}
              winner={advisorState.profiles?.[slot.key]}
              prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
              desktopOnly={desktopOnly}
            />
          ))}
        </div>
      </details>
    </section>
  );
}
