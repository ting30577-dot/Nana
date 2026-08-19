import { defineConfig, devices } from "@playwright/test";

const port = 43124;
const origin = `http://127.0.0.1:${port}`;
const token = `d3-mutation-session-${"b".repeat(40)}`;

export default defineConfig({
  testDir: "./tests/mutation",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: {
    ...devices["Desktop Chrome"],
    baseURL: origin,
    headless: true,
    extraHTTPHeaders: {
      Authorization: `Bearer ${token}`,
      Origin: origin,
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `..\\.venv\\Scripts\\python.exe ..\\scripts\\run_d3_mutation_ui.py --port ${port}`,
    url: `${origin}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
});
