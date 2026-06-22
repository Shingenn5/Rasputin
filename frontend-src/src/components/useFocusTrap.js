/**
 * useFocusTrap — shared accessibility behaviour for modal-like overlays.
 *
 * Responsibilities while `active` is true:
 *  - Remember the element that had focus before the overlay opened.
 *  - Move focus into the overlay container (preferring an explicit initial
 *    target, then the first focusable child, then the container itself).
 *  - Trap Tab / Shift+Tab so focus cycles within the container.
 *  - Close on Escape (delegates to the provided `onClose`).
 *  - Restore focus to the previously focused element when deactivated.
 *
 * Fail-soft: every DOM access is guarded so a missing ref or detached node
 * never throws during render/unmount races.
 *
 * @param {object}   opts
 * @param {boolean}  opts.active        Whether the trap is engaged.
 * @param {Function} opts.onClose       Called when Escape is pressed.
 * @param {object}   [opts.initialFocusRef] Ref to focus first when opening.
 * @param {object}   [opts.returnFocusRef]  Ref to restore focus to on close
 *                                           (falls back to the element focused
 *                                           before opening).
 * @returns {object} React ref to attach to the overlay container element.
 */
import { useCallback, useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "audio[controls]",
  "video[controls]",
  "[contenteditable]:not([contenteditable='false'])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function getFocusable(container) {
  if (!container) return [];
  const nodes = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR));
  return nodes.filter((node) => {
    if (node.hasAttribute("disabled")) return false;
    if (node.getAttribute("aria-hidden") === "true") return false;
    // Skip elements that are not rendered (display:none / detached).
    return node.offsetWidth > 0 || node.offsetHeight > 0 || node.getClientRects().length > 0;
  });
}

export function useFocusTrap({ active, onClose, initialFocusRef, returnFocusRef }) {
  const containerRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        if (typeof onClose === "function") onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const container = containerRef.current;
      if (!container) return;
      const focusable = getFocusable(container);
      if (focusable.length === 0) {
        // Keep focus pinned to the container itself.
        event.preventDefault();
        if (typeof container.focus === "function") container.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeEl = document.activeElement;
      if (event.shiftKey) {
        if (activeEl === first || !container.contains(activeEl)) {
          event.preventDefault();
          last.focus();
        }
      } else if (activeEl === last || !container.contains(activeEl)) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!active) return undefined;

    // Remember where focus was so we can restore it on close.
    previouslyFocusedRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const container = containerRef.current;
    // Defer initial focus a tick so portal children are mounted.
    const focusTimer = window.setTimeout(() => {
      const explicit = initialFocusRef?.current;
      if (explicit && typeof explicit.focus === "function") {
        explicit.focus();
        return;
      }
      const focusable = getFocusable(container);
      if (focusable.length) {
        focusable[0].focus();
      } else if (container && typeof container.focus === "function") {
        container.focus();
      }
    }, 0);

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKeyDown, true);
      // Restore focus to the caller-provided ref or the remembered element.
      const restoreTarget = returnFocusRef?.current || previouslyFocusedRef.current;
      if (restoreTarget && typeof restoreTarget.focus === "function") {
        // Defer so we don't fight the element that is unmounting.
        window.setTimeout(() => {
          try {
            restoreTarget.focus();
          } catch {
            /* element detached — ignore */
          }
        }, 0);
      }
    };
    // initialFocusRef / returnFocusRef are stable refs; intentionally omitted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, handleKeyDown]);

  return containerRef;
}

export default useFocusTrap;
