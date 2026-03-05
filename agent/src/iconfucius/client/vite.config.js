import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: 55129,
    hmr: {
      host: "localhost",
      port: 55129,
      protocol: "ws",
    },
    proxy: {
      "/api": {
        target: "http://localhost:55129",
        changeOrigin: true,
        ws: false, // don't proxy WebSocket on /api — keeps HMR working
      },
    },
  },
});
