import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the backend so the SPA is same-origin in dev,
// mirroring how nginx serves it in the container.
//
// The target must point at a *running READY ROOM backend*. The default
// (http://localhost:8000) matches a backend started directly with uvicorn.
// When the backend runs inside Compose its port is not published to the host,
// so either publish it or point this at the nginx origin (http://localhost:8080)
// — override with VITE_API_PROXY_TARGET (see frontend/.env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";
  const proxy = {
    "/api": {
      target,
      changeOrigin: true,
    },
  };

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy,
    },
    // `vite preview` serves the production build; without a proxy its /api/*
    // calls would 404. Reuse the same target so preview can exercise capture.
    preview: {
      host: "0.0.0.0",
      port: 4173,
      proxy,
    },
    build: {
      outDir: "dist",
      sourcemap: false,
    },
  };
});
