import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Geliştirmede de production nginx ile aynı `/api` sözleşmesini koru. Böylece
// öğretmen önizlemeleri tarayıcının Vite HTML fallback'inden değil API'den gelir.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
