import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// dev-only proxy; in docker/production nginx does this (see nginx.conf)
export default defineConfig(({ mode }) => {
  // 127.0.0.1, not localhost: Node 17+ resolves localhost to ::1 first.
  //
  // Overridable through VITE_API_TARGET (a .env.local will do) so the dev
  // server can be pointed at a second API — one with accounts turned on, say
  // — without having to stop the usual one first.
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": target,
        "/images": target,
      },
    },
  };
});
