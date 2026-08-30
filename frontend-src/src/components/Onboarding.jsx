/**
 * Onboarding.jsx — Phase 7 first-run guided flow.
 *
 * Shows when no chat model is ready and the `rasputin-onboarded`
 * localStorage flag is unset. Walks a new operator through what Rasputin is
 * and how to download or import a GGUF model and load it in the native runtime.
 *
 * Self-contained, accessible lightweight overlay — no external Modal dependency.
 * - role="dialog" + aria-modal, Escape skips, primary action is focused on open.
 * - Backdrop dims the rest of the UI; namespaced `.ras-onboarding*` classes.
 * - Reduced motion follows the explicit Interface Motion preference.
 *
 * Fail-soft: any render/handler issue degrades to simply not blocking the app.
 */
import React, { useEffect, useRef, useState } from "react";

const STEPS = [
  {
    kicker: "Welcome",
    title: "Welcome to Rasputin",
    body: "Rasputin runs local AI models on your own hardware. Download a GGUF model from Discover Models, load it with the built-in llama.cpp runtime, and start chatting.",
  },
  {
    kicker: "Step 1",
    title: "Get your first model ready",
    body: "Open Discover Models, choose a model and a compatible GGUF variant, then download it. When the download finishes, select Load model. Already have a GGUF file? Open My Models to import it.",
  },
];

/**
 * @param {object} props
 * @param {() => void} props.onDiscoverModels - Navigate to Discover Models.
 * @param {() => void} props.onOpenRegistry - Navigate to the Models registry.
 * @param {() => void} props.onConnectLocalEndpoint - Navigate to local endpoint setup.
 * @param {() => void} props.onEnableTestingMode - Enable the safe dry-run route.
 * @param {() => void} props.onDismiss - Skip/complete: sets the onboarded flag.
 */
export function Onboarding({
  hasSeededModels = false,
  onDiscoverModels,
  onOpenRegistry,
  onConnectLocalEndpoint,
  onEnableTestingMode,
  onDismiss,
}) {
  const [step, setStep] = useState(0);
  const primaryRef = useRef(null);
  const dialogRef = useRef(null);
  const returnFocusRef = useRef(null);

  const isLastStep = step >= STEPS.length - 1;
  const current = STEPS[step] || STEPS[0];

  // Focus the primary action on open and when the step changes, then restore
  // focus to the trigger when the dialog is dismissed.
  useEffect(() => {
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const node = primaryRef.current;
    const frame = requestAnimationFrame(() => node?.focus?.());
    return () => {
      cancelAnimationFrame(frame);
      const previous = returnFocusRef.current;
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, []);

  useEffect(() => {
    const node = primaryRef.current;
    if (node) requestAnimationFrame(() => node.focus?.());
  }, [step]);

  // Escape skips the flow.
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Tab") {
        const focusable = Array.from(dialogRef.current?.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) || []);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
      if (event.key === "Escape") {
        event.stopPropagation();
        onDismiss?.();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onDismiss]);

  function handlePrimary() {
    if (!isLastStep) {
      setStep((value) => Math.min(value + 1, STEPS.length - 1));
      return;
    }
    onDiscoverModels?.();
  }

  return (
    <div className="ras-onboarding-layer" role="presentation">
      <button
        type="button"
        className="ras-onboarding-backdrop"
        aria-label="Skip onboarding"
        tabIndex={-1}
        onClick={() => onDismiss?.()}
      />
      <div
        ref={dialogRef}
        className="ras-onboarding-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ras-onboarding-title"
        aria-describedby="ras-onboarding-body"
      >
        <div className="ras-onboarding-progress" aria-hidden="true">
          {STEPS.map((item, index) => (
            <span
              key={item.kicker}
              className={`ras-onboarding-dot${index === step ? " is-active" : ""}${index < step ? " is-done" : ""}`}
            />
          ))}
        </div>
        <p className="ras-onboarding-kicker">{current.kicker}</p>
        <h1 id="ras-onboarding-title" className="ras-onboarding-title">{current.title}</h1>
        <p id="ras-onboarding-body" className="ras-onboarding-body">
          {step === 1 && hasSeededModels
            ? "A model is registered, but no chat model is ready yet. Open My Models to load an imported GGUF, or use Discover Models to download one. You can also connect an existing local endpoint."
            : current.body}
        </p>

        {isLastStep ? (
          <div className="ras-onboarding-actions">
            <button type="button" ref={primaryRef} className="btn btn-primary ras-onboarding-action" onClick={handlePrimary}>
              Discover Models
            </button>
            <button type="button" className="btn btn-outline-secondary ras-onboarding-action" onClick={() => onOpenRegistry?.()}>
              Open My Models
            </button>
            <button type="button" className="btn btn-outline-secondary ras-onboarding-action" onClick={() => onConnectLocalEndpoint?.()}>
              Connect local endpoint
            </button>
            <button type="button" className="btn btn-outline-secondary ras-onboarding-action" onClick={() => onEnableTestingMode?.()}>
              Enable Testing Mode
            </button>
          </div>
        ) : (
          <div className="ras-onboarding-actions">
            <button type="button" ref={primaryRef} className="btn btn-primary ras-onboarding-action" onClick={handlePrimary}>
              Get started
            </button>
          </div>
        )}

        <button type="button" className="ras-onboarding-skip" onClick={() => onDismiss?.()}>
          Skip for now
        </button>
      </div>
    </div>
  );
}
