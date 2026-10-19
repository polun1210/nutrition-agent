import { defineConfig } from "@playwright/test";

// 煙霧測試：自己啟動獨立資料庫的後端（8001）與前端（5174），不碰開發中的服務。
// 前置：docker compose up -d db；第一次需 npx playwright install chromium。
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5174", viewport: { width: 390, height: 844 } },
  webServer: [
    {
      command: "uv run python scripts/e2e_server.py 8001",
      cwd: "..",
      url: "http://127.0.0.1:8001/docs",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: "npx vite --host 127.0.0.1 --port 5174 --strictPort",
      env: { API_URL: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
