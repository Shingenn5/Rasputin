import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "frontend-src",
  base: "/static/",
  plugins: [react()],
  build: {
    outDir: "../frontend",
    emptyOutDir: true,
  },
});
