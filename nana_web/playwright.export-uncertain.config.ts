import base from "./playwright.export.config";

const port = 43126;
const origin = `http://127.0.0.1:${port}`;

export default {
  ...base,
  use: { ...base.use, baseURL: origin, extraHTTPHeaders: { Authorization: `Bearer d3-export-session-${"c".repeat(40)}`, Origin: origin } },
  webServer: {
    command: `..\\.venv\\Scripts\\python.exe ..\\scripts\\run_d3_export_ui.py --port ${port} --mode uncertain`,
    url: `${origin}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
};
