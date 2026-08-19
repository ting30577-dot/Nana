import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

type CommandBody = Record<string, unknown>;

async function buildFinding(page: import("@playwright/test").Page, bodies: CommandBody[]) {
  await page.route("**/api/v1/journey/commands", async (route) => {
    bodies.push(route.request().postDataJSON() as CommandBody);
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("类型化命令通道已就绪")).toBeVisible();
  await page.getByRole("button", { name: "创建项目" }).click();
  await page.getByRole("button", { name: "创建研究问题" }).click();
  await page.getByRole("button", { name: "登记固定来源" }).click();
  await page.getByRole("button", { name: "核验精确来源范围" }).click();
  await page.getByRole("button", { name: "创建限定论断" }).click();
  await page.getByRole("button", { name: "关联正式证据" }).click();
  await page.getByRole("button", { name: "提交计划" }).click();
  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByText("正式终态：成功")).toBeVisible();
  await page.getByRole("button", { name: "提交发现草稿" }).click();
  await expect(page.getByLabel("研究旅程工作台").getByText(/正式研究发现/)).toBeVisible();
  await expect(page.getByText("Dedicated local draft folder")).toBeVisible();
}

test("one-time Approval produces a controlled T3 draft and canonical Receipt", async ({ page }) => {
  const bodies: CommandBody[] = [];
  await buildFinding(page, bodies);
  await page.getByRole("button", { name: "准备受控草稿导出" }).click();
  await expect(page.getByText("待审批", { exact: true })).toBeVisible();
  const prepare = bodies.find((body) => body.type === "RequestApproval");
  expect(prepare).toBeTruthy();
  expect(Object.keys(prepare!).sort()).toEqual(["command_id", "expected_revision", "finding_id", "target_selection_id", "type"]);
  expect(String(prepare!.target_selection_id)).toMatch(/^[A-Za-z0-9_-]{43,64}$/);
  expect(JSON.stringify(prepare)).not.toMatch(/[A-Z]:\\|dedicated-export|filename|capability|authorization|bytes|effects|risk/i);

  await page.getByRole("button", { name: "批准一次性草稿" }).click();
  await expect(page.getByText("正式回执确认固定草稿已写入。")).toBeVisible();
  await expect(page.getByText("是 · 仅一次")).toBeVisible();
  await expect(page.getByText("measured_observed_effect")).toBeVisible();
  const approval = bodies.find((body) => body.type === "DecideApproval");
  expect(approval).toBeTruthy();
  expect(Object.keys(approval!).sort()).toEqual(["approval_id", "command_id", "decision", "expected_revision", "subject_hash", "type"]);
  expect(approval!.decision).toBe("approved");
  expect(approval!.subject_hash).toMatch(/^sha256:[a-f0-9]{64}$/);
  await expect(page.getByRole("button", { name: "批准一次性草稿" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /重试|继续|重新绑定|发布/ })).toHaveCount(0);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByText("正式回执确认固定草稿已写入。")).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
});

test("denied Approval remains canonical and produces no Receipt", async ({ page }) => {
  const bodies: CommandBody[] = [];
  await buildFinding(page, bodies);
  await page.getByRole("button", { name: "准备受控草稿导出" }).click();
  await expect(page.getByText("待审批", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "拒绝导出" }).click();
  await expect(page.getByText("正式拒绝。系统未创建授权")).toBeVisible();
  expect(bodies.filter((body) => body.type === "DecideApproval")).toHaveLength(1);
  expect(bodies.find((body) => body.type === "DecideApproval")?.decision).toBe("denied");
  await expect(page.getByText("正式回执确认固定草稿已写入。")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /重试|继续|重新绑定|发布/ })).toHaveCount(0);
});

test("post-fence uncertainty is quarantined and has no retry control", async ({ page }) => {
  const bodies: CommandBody[] = [];
  await buildFinding(page, bodies);
  await page.getByRole("button", { name: "准备受控草稿导出" }).click();
  await page.getByRole("button", { name: "批准一次性草稿" }).click();
  await expect(page.getByText("执行结果未知 · 已隔离", { exact: true })).toBeVisible();
  await expect(page.getByText("conservative_uncertain_effect")).toBeVisible();
  await expect(page.getByText("已提交", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /重试|继续|重新绑定|忽略|发布|批准/ })).toHaveCount(0);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByText("执行结果未知 · 已隔离", { exact: true })).toBeVisible();
});

test("expired Approval is rendered from canonical facts and cannot authorize", async ({ page }) => {
  const bodies: CommandBody[] = [];
  await buildFinding(page, bodies);
  await page.getByRole("button", { name: "准备受控草稿导出" }).click();
  await page.getByRole("button", { name: "批准一次性草稿" }).click();
  await expect(page.getByText("正式审批已过期。系统未创建授权")).toBeVisible();
  await expect(page.getByText("已过期", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /批准|重试|继续|重新绑定|发布/ })).toHaveCount(0);
});
