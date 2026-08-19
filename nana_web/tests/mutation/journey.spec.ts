import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function buildRunnableJourney(page: import("@playwright/test").Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("类型化命令通道已就绪")).toBeVisible();
  await page.getByRole("button", { name: "创建项目" }).click();
  await page.getByRole("button", { name: "创建研究问题" }).click();
  await page.getByRole("button", { name: "登记固定来源" }).click();
  await page.getByRole("button", { name: "核验精确来源范围" }).click();
  await page.getByRole("button", { name: "创建限定论断" }).click();
  await page.getByRole("button", { name: "关联正式证据" }).click();
  await page.getByRole("button", { name: "提交计划" }).click();
  await expect(page.getByRole("button", { name: "启动锁定测试" })).toBeEnabled();
}

test("typed workbench survives response loss and completes the canonical locked journey", async ({ page }) => {
  const commandBodies: Array<Record<string, unknown>> = [];
  let loseFirstProjectResponse = true;
  let rejectFirstInquiry = true;
  await page.route("**/api/v1/journey/commands", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    commandBodies.push(body);
    if (body.type === "CreateProject" && loseFirstProjectResponse) {
      loseFirstProjectResponse = false;
      const committed = await route.fetch();
      expect(committed.status()).toBe(200);
      await route.fulfill({ response: committed, body: "{" });
      return;
    }
    if (body.type === "CreateInquiry" && rejectFirstInquiry) {
      rejectFirstInquiry = false;
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "E_REVISION_CONFLICT", message: "Synthetic stale revision", details: { actual_revision: 1 }, data_safe: true } }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("类型化命令通道已就绪")).toBeVisible();
  await page.getByRole("button", { name: "创建项目" }).click();
  await expect(page.getByRole("alert")).toContainText("命令响应已丢失");
  await expect(page.getByText(/正式项目/)).toBeVisible();
  await page.getByRole("button", { name: "使用相同命令 ID 重试" }).click();
  await expect(page.getByText("创建项目已从正式投影完成核对")).toBeVisible();
  const projectAttempts = commandBodies.filter((body) => body.type === "CreateProject");
  expect(projectAttempts).toHaveLength(2);
  expect(projectAttempts[0].command_id).toBe(projectAttempts[1].command_id);

  await page.getByRole("button", { name: "创建研究问题" }).click();
  await expect(page.getByRole("alert")).toContainText("Synthetic stale revision");
  await expect(page.getByLabel("研究问题")).toHaveValue(/滑动窗口/);
  await page.getByRole("button", { name: "创建研究问题" }).click();
  await expect(page.getByText(/正式研究问题/)).toBeVisible();

  const beforeSource = commandBodies.length;
  await page.getByRole("button", { name: "登记固定来源" }).dblclick();
  await expect(page.getByRole("button", { name: "核验精确来源范围" })).toBeEnabled();
  expect(commandBodies.slice(beforeSource).filter((body) => body.type === "RegisterResource")).toHaveLength(1);
  await page.getByRole("button", { name: "核验精确来源范围" }).click();
  await page.getByRole("button", { name: "创建限定论断" }).click();
  await page.getByRole("button", { name: "关联正式证据" }).click();
  await expect(page.getByRole("button", { name: "提交计划" })).toBeEnabled();

  await page.getByRole("button", { name: "提交计划" }).click();
  await expect(page.getByText(/正式计划修订版 1/)).toBeVisible();
  await page.getByLabel("可见步骤标题").fill("运行编辑过正式标题的固定测试");
  await expect(page.getByText("本地计划文字尚未保存；正式修订版未改变。")).toBeVisible();
  await page.getByRole("button", { name: "提交计划修订" }).click();
  await expect(page.getByText(/正式计划修订版 2/)).toBeVisible();

  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByText("正式终态：成功")).toBeVisible();
  await expect(page.locator(".execution-panel").getByText("成功", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "提交发现草稿" }).click();
  await expect(page.getByLabel("研究旅程工作台").getByText(/正式研究发现/)).toBeVisible();

  expect(commandBodies.some((body) => "backend" in body || "capability" in body || "test_id" in body)).toBe(false);
  const start = commandBodies.find((body) => body.type === "StartRun");
  expect(start).toBeTruthy();
  expect(Object.keys(start!).sort()).toEqual(["command_id", "expected_revision", "inquiry_id", "plan_id", "plan_revision", "project_id", "random_seed", "type"]);

  await page.setViewportSize({ width: 320, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
});

test("typed workbench cancels an active locked Run from canonical state", async ({ page }) => {
  const commandBodies: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/journey/commands", async (route) => {
    commandBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.continue();
  });
  await buildRunnableJourney(page);
  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByRole("button", { name: "取消当前运行" })).toBeVisible();
  await page.getByRole("button", { name: "取消当前运行" }).click();
  await expect(page.getByText("正式终态：已取消")).toBeVisible();
  const cancel = commandBodies.find((body) => body.type === "CancelRun");
  expect(cancel).toBeTruthy();
  expect(Object.keys(cancel!).sort()).toEqual(["command_id", "expected_revision", "reason", "run_id", "type"]);
  expect(commandBodies.filter((body) => body.type === "CancelRun")).toHaveLength(1);
});

test("typed workbench pauses, resumes, and retries only a failed Run", async ({ page }) => {
  const commandBodies: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/journey/commands", async (route) => {
    commandBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.continue();
  });
  await buildRunnableJourney(page);
  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByRole("button", { name: "暂停当前运行" })).toBeVisible();
  await page.getByRole("button", { name: "暂停当前运行" }).click();
  await expect(page.getByRole("button", { name: "继续当前运行" })).toBeVisible();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "继续当前运行" })).toBeVisible();
  await page.getByRole("button", { name: "继续当前运行" }).click();
  await expect(page.getByText("正式终态：失败")).toBeVisible();
  await expect(page.getByRole("button", { name: "重试失败运行" })).toBeEnabled();
  await page.getByRole("button", { name: "重试失败运行" }).click();
  await expect(page.getByText("正式终态：成功")).toBeVisible({ timeout: 15_000 });

  const pause = commandBodies.find((body) => body.type === "PauseRun");
  const resume = commandBodies.find((body) => body.type === "ResumeRun");
  const starts = commandBodies.filter((body) => body.type === "StartRun");
  expect(pause).toBeTruthy();
  expect(resume).toBeTruthy();
  expect(starts).toHaveLength(2);
  expect(starts[0].retry_of_run_id).toBeUndefined();
  expect(starts[1].retry_of_run_id).toEqual(expect.any(String));
});
