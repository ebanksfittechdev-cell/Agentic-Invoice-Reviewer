import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Use 127.0.0.1 (not "localhost") so the proxy always reaches the IPv4
  // Flask dev server. On many systems localhost resolves to ::1 first and
  // Flask's `flask run` only listens on 127.0.0.1, causing ECONNREFUSED.
  const apiTarget = env.VITE_API_PROXY || "http://127.0.0.1:5000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
