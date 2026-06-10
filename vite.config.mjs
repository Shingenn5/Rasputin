import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "frontend-src",
  base: "/static/",
  plugins: [react()],
  build: {
    outDir: "../frontend",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            if (id.includes("/src/preview/")) return "preview";
            if (id.includes("/src/features/runtime/")) return "feature-runtime";
            if (id.includes("/src/features/models/")) return "feature-models";
            if (id.includes("/src/features/workspaces/")) return "feature-workspaces";
            if (id.includes("/src/features/tasks/")) return "feature-tasks";
            return undefined;
          }
          return "vendor";
        },
      },
    },
  },
});
