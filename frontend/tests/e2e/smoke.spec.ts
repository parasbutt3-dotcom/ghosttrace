import { test, expect } from "@playwright/test";

test("register -> connect ActivityWatch mock -> event shows on timeline", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByPlaceholder("Full name").fill("E2E User");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill("password1234");
  await page.getByRole("button", { name: /Create account/i }).click();
  await page.waitForURL("**/overview", { timeout: 20_000 });

  await page.goto("/integrations");
  await page.locator("#integ-kind").selectOption("activitywatch");
  await page.locator("#integ-name").fill("AW Mock");
  await page.getByRole("button", { name: /^Add$/ }).click();

  // Sync the newly created integration.
  await page.waitForTimeout(500);
  const syncBtn = page.getByRole("button", { name: /^Sync$/ }).first();
  await syncBtn.click();
  await expect(page.getByRole("button", { name: /^Syncing/i })).toHaveCount(0, { timeout: 20_000 });

  await page.goto("/timeline");
  await expect(page.getByText("MockApp")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Mock Window Title")).toBeVisible({ timeout: 20_000 });
});