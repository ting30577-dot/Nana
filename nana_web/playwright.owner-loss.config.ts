import base from "./playwright.worker-crash.config";

const port = 43129;
const origin = `http://127.0.0.1:${port}`;

export default {
  ...base,
  use: { ...base.use, baseURL: origin, extraHTTPHeaders: { Authorization: `Bearer d3-fault-session-${"d".repeat(40)}`, Origin: origin } },
  webServer: { command: `..\\.venv\\Scripts\\python.exe ..\\scripts\\run_d3_locked_fault_ui.py --port ${port} --mode owner_context_loss`, url: `${origin}/healthz`, reuseExistingServer: false, timeout: 30_000 },
};
