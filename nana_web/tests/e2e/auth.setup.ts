import { expect, test as setup } from "@playwright/test";

const authState = "test-results/e2e-session.json";
const bootstrapSecret = `d3-e2e-bootstrap-${"b".repeat(32)}`;

setup("fragment exchange and secure reload recovery", async ({ page }) => {
  const exchange: import("@playwright/test").Request[] = [];
  const restore: import("@playwright/test").Request[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/session/exchange")) exchange.push(request);
    if (request.url().endsWith("/api/v1/session/restore")) restore.push(request);
  });

  await page.goto(`/#bootstrap=${bootstrapSecret}`, { waitUntil: "domcontentloaded" });
  await expect(page).not.toHaveURL(/bootstrap=/);
  await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
  await expect.poll(() => exchange.length).toBe(1);
  expect((await exchange[0].allHeaders()).authorization).toBeUndefined();

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "研究驾驶舱" })).toBeVisible();
  await expect.poll(() => restore.length).toBe(1);
  expect((await restore[0].allHeaders()).authorization).toBeUndefined();
  await page.context().storageState({ path: authState });
});
