import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In dev, Vite serves the UI on :5173 and proxies /api to the backend on :8000.
// In Docker, nginx does the same job (see nginx.conf.template).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  // The lazy 3D viewer chunk is mostly three.js (~560 kB); the main bundle stays small.
  build: { chunkSizeWarningLimit: 700 },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
