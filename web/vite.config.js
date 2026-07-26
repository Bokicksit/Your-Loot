import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev-only proxy; in docker/production nginx does this (see nginx.conf)
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // 127.0.0.1, not localhost: Node 17+ resolves localhost to ::1 first
      "/api": "http://127.0.0.1:8000",
      "/images": "http://127.0.0.1:8000",
    },
  },
});
