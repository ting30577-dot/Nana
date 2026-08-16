import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const origin = "http://127.0.0.1:43123";
const token = `d3-e2e-session-${"a".repeat(40)}`;
const authenticatedHeaders = { Authorization: `Bearer ${token}`, Origin: origin };

async function installImmediateTransport(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.__NANA_E2E_TRANSPORT__ = {
      delay: async () => undefined,
      random: () => 0.5,
    };
  });
}

function sseFrame(event: Record<string, unknown>): string {
  return `id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
}

async function expectApiRequest(
  request: import("@playwright/test").Request,
  path: "/api/v1/bootstrap" | "/api/v1/events",
  cursor?: string,
) {
  expect(request.url()).toBe(origin + path);
  const headers = await request.allHeaders();
  expect(headers.authorization).toBe(`Bearer ${token}`);
  expect(headers.origin).toBeUndefined();
  if (cursor !== undefined) expect(headers["last-event-id"]).toBe(cursor);
}

test("renders canonical cockpit through authenticated fetch SSE", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.addInitScript(() => {
    Object.defineProperty(window, "EventSource", {
      configurable: false,
      value: class ForbiddenEventSource { constructor() { throw new Error("EventSource is forbidden"); } },
    });
  });
  const eventRequests: import("@playwright/test").Request[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/events")) eventRequests.push(request);
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
  await expect(page.getByText("workspace-d3-readonly")).toBeVisible();
  await expect(page.getByRole("heading", { name: "执行结果未知" })).toBeVisible();
  const studio = page.getByLabel("研究工作台");
  await expect(studio.getByText("The browser projection preserves causal status.")).toBeVisible();
  await expect(studio.getByText("receipt-succeeded")).toBeVisible();
  await expect(studio.getByText("运行 run-uncertain")).toBeVisible();
  await expect(studio.getByText("locator-readonly")).toBeVisible();
  await expect(studio.getByText("证据 evidence-readonly")).toBeVisible();
  await expect(studio.getByText("Run the frozen locked test")).toBeVisible();
  await expect(page.getByText("python.unittest.locked").first()).toBeVisible();
  await expect(page.getByText("等待审批").first()).toBeVisible();
  await expect(page.getByText("需要你处理", { exact: true }).locator("..")).toContainText("01");
  const quarantine = page.getByRole("alert");
  await expect(quarantine).toContainText("不能重试、继续、忽略或将其标记为成功");
  await expect(quarantine.getByRole("button")).toHaveCount(0);
  const canonicalPlan = page.getByText("plan-readonly");
  await expect(canonicalPlan).toBeVisible();
  await page.getByLabel("本地草稿 — 未保存").fill("尝试另一种本地解释");
  await expect(page.getByText("本地文字尚未保存；正式计划未改变。")).toBeVisible();
  await expect(canonicalPlan).toBeVisible();
  await expect(page.getByRole("status")).toContainText("已连接");
  await expect.poll(() => eventRequests.length).toBeGreaterThan(0);
  const headers = await eventRequests[0].allHeaders();
  expect(headers.authorization).toBe(`Bearer ${token}`);
  expect(headers.origin).toBeUndefined();
  expect(headers["last-event-id"]).toBe("8");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("本地草稿 — 未保存")).toHaveValue("");
  await expect(page.getByRole("status")).toContainText("已连接");
  await expect.poll(() => eventRequests.length).toBeGreaterThanOrEqual(2);
  expect((await eventRequests.at(-1)?.allHeaders())?.["last-event-id"]).toBe("8");
  expect(consoleErrors).toEqual([]);
});

test("visible restoration rebuilds bootstrap before reopening the read stream", async ({ page }) => {
  let bootstrapMatches = 0;
  let streamMatches = 0;
  await page.route("**/api/v1/bootstrap", async (route) => {
    bootstrapMatches += 1;
    await expectApiRequest(route.request(), "/api/v1/bootstrap");
    await route.continue();
  });
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    await expectApiRequest(route.request(), "/api/v1/events", "8");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
  const beforeRefresh = { bootstrap: bootstrapMatches, stream: streamMatches };
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await expect.poll(() => bootstrapMatches).toBe(beforeRefresh.bootstrap + 1);
  await expect.poll(() => streamMatches).toBe(beforeRefresh.stream + 1);
  await expect(page.getByRole("status")).toContainText("已连接");
});

test("receipt effect_unknown keeps quarantine when action state is not mirrored", async ({ page }) => {
  await page.route("**/api/v1/bootstrap", async (route) => {
    const response = await route.fetch({
      headers: { ...(await route.request().allHeaders()), Origin: origin },
    });
    const snapshot = await response.json() as { actions: Array<Record<string, unknown>> };
    snapshot.actions = snapshot.actions.map((action) =>
      action.id === "action-uncertain" ? { ...action, state: "succeeded" } : action,
    );
    await route.fulfill({ response, json: snapshot });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "执行结果未知" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("不能重试、继续、忽略或将其标记为成功");
});

test("keeps launcher assets public but rejects anonymous data and undeclared paths", async () => {
  const index = await fetch(origin + "/");
  expect(index.status).toBe(200);
  const knownAsset = (await index.text()).match(/(?:src|href)="(\/assets\/[^"]+)"/)?.[1];
  expect(knownAsset).toBeTruthy();
  expect((await fetch(origin + knownAsset!)).status).toBe(200);
  for (const path of ["/api/v1/ui-config", "/api/v1/bootstrap"]) {
    const response = await fetch(origin + path, { redirect: "manual" });
    expect([401, 403], `${path} must stay default-deny`).toContain(response.status);
  }
  for (const path of ["/assets/unknown.js", "/assets/index.js.map"]) {
    expect((await fetch(origin + path)).status).toBe(404);
  }
  expect((await fetch(origin + "/api/v1/ui-config", { headers: authenticatedHeaders })).status).toBe(404);
  const response = await fetch(origin + "/api/v1/bootstrap", {
    headers: { Authorization: `Bearer ${token}-wrong`, Origin: origin },
  });
  expect(response.status).toBe(401);
  expect(await response.text()).not.toContain(`${token}-wrong`);
  for (const value of response.headers.values()) expect(value).not.toContain(`${token}-wrong`);
});

test("four automatic reconnects end terminal and manual reconnect resumes from the frozen cursor", async ({ page }) => {
  await installImmediateTransport(page);
  let matches = 0;
  await page.route("**/api/v1/events", async (route) => {
    const request = route.request();
    await expectApiRequest(request, "/api/v1/events", "8");
    matches += 1;
    if (matches <= 5) await route.abort("connectionreset");
    else await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "事件流已断开" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("手动重新连接");
  expect(matches).toBe(5);
  await page.getByRole("button", { name: "重新连接事件流" }).click();
  await expect(page.getByRole("heading", { name: "已连接" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("已连接");
  expect(matches).toBe(6);
});

test("two bootstrap transport failures are terminal without opening a stream", async ({ page }) => {
  await installImmediateTransport(page);
  let bootstrapMatches = 0;
  let streamMatches = 0;
  await page.route("**/api/v1/bootstrap", async (route) => {
    await expectApiRequest(route.request(), "/api/v1/bootstrap");
    bootstrapMatches += 1;
    await route.abort("connectionreset");
  });
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    await route.abort();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "投影不可用" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("新的 Nana 会话");
  expect(bootstrapMatches).toBe(2);
  expect(streamMatches).toBe(0);
});

test("a 401 on manual stream reconnect is terminal session expired without retry", async ({ page }) => {
  await installImmediateTransport(page);
  let matches = 0;
  await page.route("**/api/v1/events", async (route) => {
    matches += 1;
    if (matches <= 5) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.abort("connectionreset");
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "8");
    await route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "事件流已断开" })).toBeVisible();
  await page.getByRole("button", { name: "重新连接事件流" }).click();
  await expect(page.getByRole("heading", { name: "会话已过期" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("重新启动 Nana");
  expect(matches).toBe(6);
});

test("malformed SSE freezes cursor and one invalid recovery bootstrap is terminal", async ({ page }) => {
  await installImmediateTransport(page);
  let bootstrapMatches = 0;
  await page.route("**/api/v1/bootstrap", async (route) => {
    await expectApiRequest(route.request(), "/api/v1/bootstrap");
    bootstrapMatches += 1;
    if (bootstrapMatches === 1) await route.continue();
    else if (bootstrapMatches === 2) await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ high_water_event_id: "invalid" }) });
    else throw new Error("unexpected parallel/repeated bootstrap");
  });
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    await expectApiRequest(route.request(), "/api/v1/events", "8");
    streamMatches += 1;
    if (streamMatches > 1) throw new Error("unexpected parallel/repeated stream");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: "id: nope\nevent: run.started\ndata: {}\n\n" });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "投影不可用" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("启动新的 Nana 会话");
  await expect(page.getByText("事件游标 8")).toBeVisible();
  expect(bootstrapMatches).toBe(2);
  expect(streamMatches).toBe(1);
});

test("sparse event IDs and an exact duplicate advance by sequence, not integer adjacency", async ({ page }) => {
  const events = [
    { id: 10, aggregate_type: "run", aggregate_id: "run-sparse", aggregate_version: 1, run_id: "run-sparse", run_seq: 1, action_id: null, type: "run.started", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:10Z" },
    { id: 10, aggregate_type: "run", aggregate_id: "run-sparse", aggregate_version: 1, run_id: "run-sparse", run_seq: 1, action_id: null, type: "run.started", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:10Z" },
    { id: 12, aggregate_type: "run", aggregate_id: "run-sparse", aggregate_version: 2, run_id: "run-sparse", run_seq: 2, action_id: null, type: "run.heartbeat", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:12Z" },
    { id: 19, aggregate_type: "artifact", aggregate_id: "artifact-sparse", aggregate_version: 1, run_id: "run-sparse", run_seq: 3, action_id: null, type: "artifact.committed", payload: { artifact_id: "artifact-sparse", state: "available", blob_hash: `sha256:${"f".repeat(64)}`, size: 1, media_type: "text/plain" }, occurred_at: "2026-08-08T00:00:19Z" },
  ];
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches === 1) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: events.map(sseFrame).join("") });
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "19");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("事件游标 19")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("已连接");
  await expect.poll(() => streamMatches).toBe(2);
});

test("known Approval events stay canonical while future Approval events degrade", async ({ page }) => {
  await installImmediateTransport(page);
  const unknown = {
    id: 10,
    aggregate_type: "approval",
    aggregate_id: "approval-pending",
    aggregate_version: 1,
    run_id: null,
    run_seq: null,
    action_id: null,
    type: "approval.future_unknown",
    payload: { state: "requested" },
    occurred_at: "2026-08-08T00:00:10Z",
  };
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches === 1) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: sseFrame(unknown) });
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "10");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "需要升级投影" })).toBeVisible();
  await expect(page.getByRole("status", { name: "需要升级投影" })).toContainText("活动记录已保留该事件");
  await expect(page.getByLabel("研究工作台").getByText("approval.future_unknown")).toBeVisible();
  await expect(page.getByText("事件游标 10")).toBeVisible();
});

test("future event types under a known aggregate never infer domain state", async ({ page }) => {
  await installImmediateTransport(page);
  const future = {
    id: 10,
    aggregate_type: "run",
    aggregate_id: "run-future-type",
    aggregate_version: 1,
    run_id: "run-future-type",
    run_seq: 1,
    action_id: null,
    type: "run.future_unknown",
    payload: { state: "succeeded" },
    occurred_at: "2026-08-08T00:00:10Z",
  };
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches === 1) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: sseFrame(future) });
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "10");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "需要升级投影" })).toBeVisible();
  await expect(page.getByLabel("研究工作台").getByText("run.future_unknown")).toBeVisible();
  await expect(page.locator(".execution-panel").getByText("run-future-type")).toHaveCount(0);
  await expect(page.getByText("事件游标 10")).toBeVisible();
});

test("streamed Finding facts remain canonical and render provenance", async ({ page }) => {
  await installImmediateTransport(page);
  const finding = {
    id: 10,
    aggregate_type: "finding",
    aggregate_id: "finding-streamed",
    aggregate_version: 1,
    run_id: "run-streamed",
    run_seq: 1,
    action_id: null,
    type: "finding.drafted",
    payload: {
      finding_id: "finding-streamed",
      statement: "Observed streamed finding",
      status: "draft",
      evidence_ids: ["evidence-streamed"],
      producer_run_id: "run-streamed",
    },
    occurred_at: "2026-08-08T00:00:10Z",
  };
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches === 1) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: sseFrame(finding) });
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "10");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const studio = page.getByLabel("研究工作台");
  await expect(studio.getByText("Observed streamed finding")).toBeVisible();
  await expect(studio.getByText("来源运行 run-streamed")).toBeVisible();
  await expect(studio.getByText("证据 evidence-streamed")).toBeVisible();
  await expect(page.getByText("事件游标 10")).toBeVisible();
  await expect(page.getByRole("heading", { name: "需要升级投影" })).toHaveCount(0);
});

test("streamed negative Run states remain literal", async ({ page }) => {
  await installImmediateTransport(page);
  const events = [
    {
      id: 10,
      aggregate_type: "run",
      aggregate_id: "run-cancelled",
      aggregate_version: 1,
      run_id: "run-cancelled",
      run_seq: 1,
      action_id: null,
      type: "run.cancelled",
      payload: { state: "cancelled" },
      occurred_at: "2026-08-08T00:00:10Z",
    },
    {
      id: 12,
      aggregate_type: "run",
      aggregate_id: "run-budget",
      aggregate_version: 1,
      run_id: "run-budget",
      run_seq: 1,
      action_id: null,
      type: "run.budget_exceeded",
      payload: { state: "budget_exceeded" },
      occurred_at: "2026-08-08T00:00:12Z",
    },
  ];
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches === 1) {
      await expectApiRequest(route.request(), "/api/v1/events", "8");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: events.map(sseFrame).join("") });
      return;
    }
    await expectApiRequest(route.request(), "/api/v1/events", "12");
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const studio = page.getByLabel("研究工作台");
  await expect(studio.getByText("运行 run-cancelled")).toBeVisible();
  await expect(studio.getByText("运行 run-budget")).toBeVisible();
  await expect(studio.getByText("已取消", { exact: true })).toBeVisible();
  await expect(studio.getByText("超出预算", { exact: true })).toBeVisible();
  await expect(page.getByText("事件游标 12")).toBeVisible();
});

test("same event ID with different content freezes cursor and performs one recovery", async ({ page }) => {
  await installImmediateTransport(page);
  let bootstrapMatches = 0;
  await page.route("**/api/v1/bootstrap", async (route) => {
    await expectApiRequest(route.request(), "/api/v1/bootstrap");
    bootstrapMatches += 1;
    if (bootstrapMatches === 1) await route.continue();
    else if (bootstrapMatches === 2) await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ high_water_event_id: "invalid" }) });
    else throw new Error("unexpected parallel/repeated bootstrap");
  });
  const first = { id: 10, aggregate_type: "run", aggregate_id: "run-conflict", aggregate_version: 1, run_id: "run-conflict", run_seq: 1, action_id: null, type: "run.started", payload: { state: "running" }, occurred_at: "2026-08-08T00:00:10Z" };
  const conflicting = { ...first, payload: { state: "failed" } };
  let streamMatches = 0;
  await page.route("**/api/v1/events", async (route) => {
    streamMatches += 1;
    if (streamMatches > 1) throw new Error("unexpected parallel/repeated stream");
    await expectApiRequest(route.request(), "/api/v1/events", "8");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: sseFrame(first) + sseFrame(conflicting) });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "投影不可用" })).toBeVisible();
  await expect(page.getByText("事件游标 10")).toBeVisible();
  expect(bootstrapMatches).toBe(2);
  expect(streamMatches).toBe(1);
});

test("production build contains no fixture, launcher token, or source-map artifact", async () => {
  const root = resolve(process.cwd(), "dist");
  const files = (directory: string): string[] => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = join(directory, entry.name);
    return entry.isDirectory() ? files(target) : [target];
  });
  const buildFiles = files(root);
  expect(buildFiles.some((file) => file.endsWith(".map"))).toBe(false);
  const content = buildFiles.map((file) => readFileSync(file, "utf8")).join("\n");
  for (const forbidden of ["d3-e2e-session-", "workspace-d3-readonly", "run-succeeded", "page.route("]) {
    expect(content).not.toContain(forbidden);
  }
});

test("keyboard, reflow, forced colors, and serious accessibility checks pass", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce", forcedColors: "active", contrast: "more" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "已连接" })).toBeFocused();
  await page.locator(":focus").evaluate((element: HTMLElement) => element.blur());
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "执行结果未知" })).toBeVisible();
  await page.evaluate(() => { document.documentElement.style.fontSize = "100%"; });
  const scrollbarWidth = await page.evaluate(() => window.innerWidth - document.documentElement.clientWidth);
  await page.setViewportSize({ width: 320 + scrollbarWidth, height: 900 });
  expect(await page.evaluate(() => document.documentElement.clientWidth)).toBe(320);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const offenders = await page.evaluate(() => [...document.querySelectorAll("*")].map((element) => {
    const rect = element.getBoundingClientRect();
    return { tag: element.tagName, className: element.className, text: element.textContent?.slice(0, 40), left: rect.left, right: rect.right, width: rect.width };
  }).filter((item) => item.left < -1 || item.right > document.documentElement.clientWidth + 1));
  expect(overflow, JSON.stringify(offenders.slice(0, 10))).toBeLessThanOrEqual(1);
  expect(offenders).toEqual([]);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
});

test("desktop remains usable at 125 and 150 percent browser scale", async ({ browser }) => {
  for (const scale of [1.25, 1.5]) {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
      deviceScaleFactor: scale,
      storageState: "test-results/e2e-session.json",
    });
    const page = await context.newPage();
    await page.goto(origin + "/", { waitUntil: "domcontentloaded" });
    await page.evaluate((zoom) => { document.documentElement.style.zoom = String(zoom); }, scale);
    await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "执行结果未知" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `horizontal overflow at ${scale * 100}%`).toBeLessThanOrEqual(1);
    await context.close();
  }
});
