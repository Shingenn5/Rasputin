import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

/* ─────────────────────────────────────────────
   Toast notification system

   Stacked, individually-timed, dismissible toasts that replace the
   single-message global status bar as the app's feedback channel.

   Usage:
     const toast = useToast();
     toast.success("Model imported.");
     toast.error("Deploy failed.");
     toast.info("Working...");

   Each call returns the toast id; toast.dismiss(id) closes it early.
   ───────────────────────────────────────────── */

const ToastContext = createContext(null);

const VARIANT_META = {
  success: { icon: CheckCircle2, role: "status", live: "polite", duration: 4000 },
  info: { icon: Info, role: "status", live: "polite", duration: 4500 },
  error: { icon: AlertTriangle, role: "alert", live: "assertive", duration: 0 }, // sticky
};

const MAX_VISIBLE = 4;
let _idSeq = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
    const handle = timers.current.get(id);
    if (handle) {
      window.clearTimeout(handle);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback((message, variant = "info", opts = {}) => {
    if (!message) return null;
    const meta = VARIANT_META[variant] || VARIANT_META.info;
    const id = ++_idSeq;
    setToasts((list) => {
      const next = [...list, { id, message: String(message), variant }];
      // Cap the queue: drop the oldest beyond MAX_VISIBLE.
      return next.length > MAX_VISIBLE ? next.slice(next.length - MAX_VISIBLE) : next;
    });
    const duration = opts.duration ?? meta.duration;
    if (duration > 0) {
      const handle = window.setTimeout(() => dismiss(id), duration);
      timers.current.set(id, handle);
    }
    return id;
  }, [dismiss]);

  // Clean up any outstanding timers on unmount.
  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((handle) => window.clearTimeout(handle));
      map.clear();
    };
  }, []);

  const api = useMemo(() => ({
    push,
    dismiss,
    success: (msg, opts) => push(msg, "success", opts),
    error: (msg, opts) => push(msg, "error", opts),
    info: (msg, opts) => push(msg, "info", opts),
  }), [push, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fail soft: a no-op API if used outside the provider, so callers
    // never crash the app over a missing toast.
    return { push: () => null, dismiss: () => {}, success: () => null, error: () => null, info: () => null };
  }
  return ctx;
}

function ToastViewport({ toasts, dismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="ras-toast-viewport" aria-label="Notifications">
      {toasts.map((t) => {
        const meta = VARIANT_META[t.variant] || VARIANT_META.info;
        const Icon = meta.icon;
        return (
          <div
            key={t.id}
            className={`ras-toast ras-toast--${t.variant}`}
            role={meta.role}
            aria-live={meta.live}
          >
            <span className="ras-toast__icon" aria-hidden="true">
              <Icon size={16} />
            </span>
            <span className="ras-toast__message">{t.message}</span>
            <button
              type="button"
              className="ras-toast__dismiss"
              aria-label="Dismiss notification"
              onClick={() => dismiss(t.id)}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
