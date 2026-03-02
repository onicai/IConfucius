import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: 3000,
    hmr: {
      host: "localhost",
      port: 3000,
      protocol: "ws",
    },
    proxy: {
      "/api": {
        target: "http://localhost:3001",
        changeOrigin: true,
        ws: false, // don't proxy WebSocket on /api — keeps HMR working
      },
    },
  },
});
