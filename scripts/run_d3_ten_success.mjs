import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const webRoot = path.join(root, "nana_web");
const launcher = path.join(webRoot, "node_modules", "@playwright", "test", "cli.js");

for (let run = 1; run <= 10; run += 1) {
  process.stdout.write(`\n[D3-09] full success journey ${run}/10\n`);
  const result = spawnSync(
    process.execPath,
    [
      launcher,
      "test",
      "--config",
      "playwright.export.config.ts",
      "--grep",
      "one-time Approval",
    ],
    {
      cwd: webRoot,
      env: { ...process.env, NANA_D3_RELEASE_RUN: String(run) },
      stdio: "inherit",
      shell: false,
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.stderr.write(`[D3-09] journey ${run}/10 failed; later runs were not attempted\n`);
    process.exit(result.status ?? 1);
  }
}

process.stdout.write("\n[D3-09] 10/10 consecutive full success journeys passed with Playwright retries=0\n");
