/**
 * Drawer — accessible side-drawer primitive for Rasputin.
 *
 * Shares the focus-trap / a11y behaviour of <Modal> but slides in from the
 * edge (right by default) instead of centring. Rendered into document.body
 * via a React portal.
 *
 * Two usage shapes:
 *  1. Convenience: pass `title` + `children` and the Drawer renders its own
 *     header (with a close button) and a scrollable body.
 *  2. Bare shell: pass `bare` and provide your own internal chrome. The Drawer
 *     then only supplies the backdrop, slide animation, portal, focus trap,
 *     Escape/backdrop close and ARIA wiring on the panel element. This is what
 *     TaskDetailsDrawer uses so it keeps its bespoke header/tabs and test ids.
 *
 * Honors Rasputin's explicit Interface Motion preference.
 *
 * @param {object}   props
 * @param {boolean}  props.open               Whether the drawer is visible.
 * @param {Function} props.onClose            Called on Escape / backdrop / close button.
 * @param {React.ReactNode} [props.title]     Header title (non-bare mode).
 * @param {React.ReactNode} props.children    Drawer content.
 * @param {"right"|"left"} [props.side]       Edge to slide from. Default "right".
 * @param {"sm"|"md"|"lg"} [props.size]       Panel width preset. Default "md".
 * @param {boolean}  [props.bare=false]       Skip built-in header/body chrome.
 * @param {boolean}  [props.showClose=true]   Render the built-in close button (non-bare).
 * @param {string}   [props.labelledBy]       id of the element labelling the dialog.
 * @param {object}   [props.initialFocusRef]  Element to focus first when opening.
 * @param {object}   [props.returnFocusRef]   Element to restore focus to on close.
 * @param {string}   [props.className]        Extra class names for the panel.
 * @param {object}   [props.panelProps]       Extra props spread onto the panel (e.g. data-testid).
 */
import React, { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useFocusTrap } from "./useFocusTrap.js";

export function Drawer({
  open,
  onClose,
  title,
  children,
  side = "right",
  size = "md",
  bare = false,
  showClose = true,
  labelledBy,
  initialFocusRef,
  returnFocusRef,
  className = "",
  panelProps = {},
}) {
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);
  const autoTitleId = useId();
  const titleId = labelledBy || (title ? `ras-drawer-title-${autoTitleId}` : undefined);

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
      raf = window.requestAnimationFrame(() => setVisible(true));
    } else if (mounted) {
      setVisible(false);
      timer = window.setTimeout(() => setMounted(false), 220);
    }
    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      if (timer) window.clearTimeout(timer);
    };
  }, [open, mounted]);

  useEffect(() => {
    if (!mounted) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mounted]);

  if (!mounted || typeof document === "undefined") return null;

  const { className: extraPanelClass = "", ...restPanelProps } = panelProps;

  return createPortal(
    <div
      className={`ras-drawer-layer${visible ? " is-open" : ""}`}
      role="presentation"
    >
      <div className="ras-drawer-backdrop" aria-hidden="true" onMouseDown={() => onClose?.()} />
      <div
        ref={containerRef}
        className={
          `ras-drawer ras-drawer-${side} ras-drawer-${size}` +
          `${className ? ` ${className}` : ""}${extraPanelClass ? ` ${extraPanelClass}` : ""}`
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        {...restPanelProps}
      >
        {bare ? (
          children
        ) : (
          <>
            {(title || showClose) && (
              <header className="ras-drawer-header">
                {title ? (
                  <h2 className="ras-drawer-title" id={titleId}>
                    {title}
                  </h2>
                ) : (
                  <span />
                )}
                {showClose && (
                  <button
                    type="button"
                    className="ras-drawer-close"
                    aria-label="Close drawer"
                    onClick={onClose}
                  >
                    <X size={18} />
                  </button>
                )}
              </header>
            )}
            <div className="ras-drawer-body">{children}</div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default Drawer;
