import { create } from "zustand";

export const useSettingsStore = create((set, get) => ({
  // ── State Domains ──
  general: {},
  runtime: {},
  security: {},
  deployments: {},
  integrations: {},
  resources: {},
  notifications: {},
  audit: {},
  diagnostics: {},

  // ── UI / Meta State ──
  loading: false,
  errors: {},

  // ── Actions ──
  setLoading: (isLoading) => set({ loading: isLoading }),
  
  setError: (domain, errorMsg) => set((state) => ({
    errors: { ...state.errors, [domain]: errorMsg }
  })),

  clearError: (domain) => set((state) => {
    const newErrors = { ...state.errors };
    delete newErrors[domain];
    return { errors: newErrors };
  }),

  // Update a specific domain's settings
  updateDomainSettings: (domain, newSettings) => set((state) => ({
    [domain]: { ...state[domain], ...newSettings }
  })),

  // Replace a specific domain's settings entirely
  setDomainSettings: (domain, settings) => set({
    [domain]: settings
  }),

  // Bulk update all settings (e.g., after loading from backend)
  setAllSettings: (fullState) => set((state) => ({
    ...state,
    ...fullState
  })),
}));
