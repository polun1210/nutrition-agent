import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 開發時把 /api 轉給後端；compose 內用 API_URL 指向 api 服務。
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": apiUrl } },
});
