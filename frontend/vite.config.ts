import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend dev runs on :5173, proxies to FastAPI on :5273.
// Production build output lands in ./dist, which the FastAPI app serves
// from "/" + "/assets/*" once present.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:5273",
      "/login": "http://127.0.0.1:5273",
      "/logout": "http://127.0.0.1:5273",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
