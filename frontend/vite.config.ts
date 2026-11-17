import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In dev, Vite serves the UI on :5173 and proxies /api to the backend on :8000.
// In Docker, nginx does the same job (see nginx.conf.template).
// `--mode demo` builds the static demo instead (D-059): no backend, the recorded snapshot
// in demo/ is served as the public folder, and a relative base works under any path.
export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    plugins: [react()],
    base: demo ? "./" : "/",
    publicDir: demo ? "demo" : "public",
    define: demo ? { "import.meta.env.VITE_DEMO": JSON.stringify("1") } : {},
    server: {
      port: 5173,
      proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
    },
    // The lazy 3D viewer chunk is mostly three.js (~560 kB); the main bundle stays small.
    build: { chunkSizeWarningLimit: 700, outDir: demo ? "dist-demo" : "dist" },
    test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
  };
});
