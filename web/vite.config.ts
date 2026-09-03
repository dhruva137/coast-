import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const dir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@sih26168/nav-core": resolve(dir, "../core/ts/src/index.ts"),
    },
  },
  server: { port: 26168, host: true },
});
