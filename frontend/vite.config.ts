import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const staticDir = fileURLToPath(new URL("../static", import.meta.url));
const allowedHosts = (process.env.VITE_ALLOWED_HOSTS ?? "eqm.easyduneadmin.app")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);
const proxyTarget = process.env.VITE_PROXY_API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  publicDir: staticDir,
  server: {
    allowedHosts,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
});