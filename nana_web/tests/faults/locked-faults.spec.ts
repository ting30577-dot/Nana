import { expect, test } from "@playwright/test";

async function buildRunnable(page: import("@playwright/test").Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("类型化命令通道已就绪")).toBeVisible();
  await page.getByRole("button", { name: "创建项目" }).click();
  await page.getByRole("button", { name: "创建研究问题" }).click();
  await page.getByRole("button", { name: "登记固定来源" }).click();
  await page.getByRole("button", { name: "核验精确来源范围" }).click();
  await page.getByRole("button", { name: "创建限定论断" }).click();
  await page.getByRole("button", { name: "关联正式证据" }).click();
  await page.getByRole("button", { name: "提交计划" }).click();
}

test("worker crash settles through owner-lane facts as effect unknown", async ({ page }) => {
  await buildRunnable(page);
  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByText("正式终态：失去归属")).toBeVisible();
  await expect(page.getByRole("heading", { name: "执行结果未知" })).toBeVisible();
  await expect(page.locator(".execution-panel").getByText("结果未知", { exact: true }).last()).toBeVisible();
  await expect(page.getByRole("button", { name: /重试|继续|忽略/ })).toHaveCount(0);
});

test("owner-context loss before spawn settles as proved pre-spawn cancellation", async ({ page }) => {
  await buildRunnable(page);
  await page.getByRole("button", { name: "启动锁定测试" }).click();
  await expect(page.getByText("正式终态：已取消")).toBeVisible();
  await expect(page.locator(".execution-panel").getByText("已取消", { exact: true }).last()).toBeVisible();
  await expect(page.getByRole("heading", { name: "执行结果未知" })).toHaveCount(0);
});
