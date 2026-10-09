import { defineConfig } from "@playwright/test";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";

const testDirectory = mkdtempSync(join(tmpdir(), "eristem-learning-e2e-"));
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ??
  (existsSync("/usr/bin/google-chrome") ? "/usr/bin/google-chrome" : undefined);

export default defineConfig({
  testDir: "./e2e", timeout: 30_000, fullyParallel: false, workers: 1,
  use: { baseURL: "http://127.0.0.1:18766", launchOptions: { executablePath },
    trace: "retain-on-failure" },
  webServer: [
    { command: "../api/.venv/bin/python -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port 18765",
      url: "http://127.0.0.1:18765/openapi.json", reuseExistingServer: false,
      env: { DATABASE_URL: `sqlite:///${join(testDirectory, "test.db")}`, APP_ENV: "development" } },
    { command: "npm run dev -- --host 127.0.0.1 --port 18766 --strictPort",
      url: "http://127.0.0.1:18766", reuseExistingServer: false,
      env: { VITE_API_PROXY_TARGET: "http://127.0.0.1:18765" } },
  ],
});
