import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  workers: 1,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3100",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "python tests/mock_aw_server.py",
      port: 5600,
      reuseExistingServer: !isCI,
      timeout: 30_000,
    },
    {
      command: "python -m uvicorn app.main:app --port 8000",
      cwd: "../backend",
      port: 8000,
      reuseExistingServer: !isCI,
      timeout: 120_000,
      env: {
        APP_ENV: "development",
        AUTO_SYNC_ENABLED: "false",
        DATABASE_URL: process.env.DATABASE_URL || "sqlite:///./e2e_ghosttrace.db",
        SECRET_KEY: process.env.SECRET_KEY || "e2e-secret-key-32chars-minimum-aaaa",
        CORS_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3100,http://127.0.0.1:3100",
      },
    },
    {
      command: "npm run dev -- -p 3100",
      port: 3100,
      reuseExistingServer: !isCI,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
      },
    },
  ],
});