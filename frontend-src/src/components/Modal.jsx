/**
 * Modal — reusable accessible modal dialog primitive for Rasputin.
 *
 * Features:
 *  - role="dialog" + aria-modal, labelled by the supplied title.
 *  - Focus trap while open (Tab / Shift+Tab cycle within the panel).
 *  - Focus restoration to the previously focused element on close.
 *  - Escape closes; backdrop click closes (panel clicks do not).
 *  - Rendered into document.body via a React portal so it escapes any
 *    overflow/stacking context of the trigger.
 *  - Enter/exit animation via CSS classes; follows Rasputin's explicit
 *    Interface Motion preference through the global motion scope.
 *
 * Vanilla CSS only — see the `.ras-modal*` block in rasputin.css.
 *
 * @param {object}   props
 * @param {boolean}  props.open               Whether the modal is visible.
 * @param {Function} props.onClose            Called on Escape / backdrop / close button.
 * @param {React.ReactNode} [props.title]     Accessible title (rendered in the header).
 * @param {React.ReactNode} props.children    Body content.
 * @param {"sm"|"md"|"lg"|"xl"} [props.size]  Panel width preset. Default "md".
 * @param {boolean}  [props.showClose=true]   Render the built-in close button.
 * @param {object}   [props.initialFocusRef]  Element to focus first when opening.
 * @param {object}   [props.returnFocusRef]   Element to restore focus to on close.
 * @param {string}   [props.className]        Extra class names for the panel.
 * @param {string}   [props.labelledBy]       id of an existing label (overrides title labelling).
 */
import React, { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useFocusTrap } from "./useFocusTrap.js";

export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
  showClose = true,
  initialFocusRef,
  returnFocusRef,
  className = "",
  labelledBy,
  ...rest
}) {
  // Keep the node mounted briefly during the exit animation.
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);
  const autoTitleId = useId();
  const titleId = labelledBy || (title ? `ras-modal-title-${autoTitleId}` : undefined);

  const containerRef = useFocusTrap({
    active: open && mounted,
    onClose,
    initialFocusRef,
    returnFocusRef,
  });

  useEffect(() => {
    let raf;
    let timer;
    if (open) {
      setMounted(true);
      // Next frame so the enter transition runs from the closed state.
      raf = window.requestAnimationFrame(() => setVisible(true));
    } else if (mounted) {
      setVisible(false);
      timer = window.setTimeout(() => setMounted(false), 200);
    }
    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      if (timer) window.clearTimeout(timer);
    };
  }, [open, mounted]);

  // Lock body scroll while open.
  useEffect(() => {
    if (!mounted) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mounted]);

  if (!mounted || typeof document === "undefined") return null;

  function onBackdropMouseDown(event) {
    // Only close when the press starts on the backdrop itself, so a drag that
    // ends on the backdrop (text selection inside the panel) does not close it.
    if (event.target === event.currentTarget && typeof onClose === "function") {
      onClose();
    }
  }

  return createPortal(
    <div
      className={`ras-modal-layer${visible ? " is-open" : ""}`}
      role="presentation"
      onMouseDown={onBackdropMouseDown}
    >
      <div className="ras-modal-backdrop" aria-hidden="true" />
      <div
        ref={containerRef}
        className={`ras-modal ras-modal-${size}${className ? ` ${className}` : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        {...rest}
      >
        {(title || showClose) && (
          <header className="ras-modal-header">
            {title ? (
              <h2 className="ras-modal-title" id={titleId}>
                {title}
              </h2>
            ) : (
              <span />
            )}
            {showClose && (
              <button
                type="button"
                className="ras-modal-close"
                aria-label="Close dialog"
                onClick={onClose}
              >
                <X size={18} />
              </button>
            )}
          </header>
        )}
        <div className="ras-modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

export default Modal;
