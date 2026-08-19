import { defineConfig, devices } from "@playwright/test";

const port = 43123;
const origin = `http://127.0.0.1:${port}`;
const authState = "test-results/e2e-session.json";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20_000,
  expect: { timeout: 5_000 },
  use: {
    ...devices["Desktop Chrome"],
    baseURL: origin,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `..\\.venv\\Scripts\\python.exe ..\\scripts\\run_d3_readonly_ui.py --port ${port}`,
    url: `${origin}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    {
      name: "auth-setup",
      testMatch: /auth\.setup\.ts/,
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
    {
      name: "chromium",
      testIgnore: /auth\.setup\.ts/,
      dependencies: ["auth-setup"],
      use: { ...devices["Desktop Chrome"], channel: "chrome", storageState: authState },
    },
  ],
});
