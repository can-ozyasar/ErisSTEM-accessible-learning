import { expect, test } from "@playwright/test";

test("spoken exploration announces the selected card when enabled", async ({ page }) => {
  const spoken: string[] = [];
  await page.route("**/api/v1/student/interface-speech", async route => {
    spoken.push((route.request().postDataJSON() as { text: string }).text);
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Sesli keşfi başlat" }).click();
  await page.getByRole("button", { name: "Sonraki alan" }).click();
  await expect.poll(() => spoken.some(value => value.includes("Öğretmen alanına geç"))).toBe(true);
  await page.getByRole("button", { name: "Keşif sesini kapat" }).click();
  await expect(page.getByRole("button", { name: "Keşif sesini aç" })).toBeVisible();
});

test("a touch activation uses the native link without an extra app-level double tap", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: "block" });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("link", { name: /Öğrenci olarak devam et/ }).tap();
  await expect(page).toHaveURL(/mode=student/);
  await expect(page.getByRole("heading", { name: "9. sınıf tarih kitabı" })).toBeVisible();
  await context.close();
});
