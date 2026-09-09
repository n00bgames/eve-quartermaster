import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({
  root: fileURLToPath(new URL("../../", import.meta.url)),
  plugins: [react()],
  cacheDir: fileURLToPath(new URL("../../.pi-test-cache", import.meta.url)),
  server: {host:"127.0.0.1",port:18482,strictPort:true,proxy:{"/api":"http://127.0.0.1:18481"}},
});
