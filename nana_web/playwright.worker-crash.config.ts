import { defineConfig, devices } from "@playwright/test";

const port = 43128;
const origin = `http://127.0.0.1:${port}`;
const authorization = `Bearer d3-fault-session-${"d".repeat(40)}`;

export default defineConfig({
  testDir: "./tests/faults",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: { ...devices["Desktop Chrome"], baseURL: origin, headless: true, extraHTTPHeaders: { Authorization: authorization, Origin: origin }, trace: "retain-on-failure" },
  webServer: { command: `..\\.venv\\Scripts\\python.exe ..\\scripts\\run_d3_locked_fault_ui.py --port ${port} --mode worker_crash`, url: `${origin}/healthz`, reuseExistingServer: false, timeout: 30_000 },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
});
