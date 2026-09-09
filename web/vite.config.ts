import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { coastTrainPlugin } from "./vite-train-api";

const dir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), coastTrainPlugin()],
  resolve: {
    alias: {
      "@sih26168/nav-core": resolve(dir, "../core/ts/src/index.ts"),
    },
  },
  server: {
    port: 26168,
    // Default: localhost only. Set COAST_LAN=1 for phone/LAN access (0.0.0.0).
    host: process.env.COAST_LAN === "1" ? "0.0.0.0" : "localhost",
    strictPort: true,
  },
});
