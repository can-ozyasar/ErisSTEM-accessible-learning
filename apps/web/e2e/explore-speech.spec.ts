import { expect, test } from "@playwright/test";

test("student UI announces hovered and focused controls and can be switched off", async ({ page }) => {
  const spoken: string[] = [];
  await page.route("**/api/v1/student/interface-speech", async route => {
    spoken.push((route.request().postDataJSON() as { text: string }).text);
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "🔊 Sesli keşfi başlat" }).click();
  const history = page.getByRole("button", { name: /9. sınıf tarih kitabı/ });
  await history.hover();
  await expect.poll(() => spoken.some(value => value.includes("9. sınıf tarih kitabı") && value.includes("düğme"))).toBe(true);
  const bank = page.getByRole("button", { name: /Tarih soru bankasını aç/ });
  await bank.focus();
  await expect.poll(() => spoken.some(value => value.includes("Tarih soru bankası") && value.includes("düğme"))).toBe(true);
  await page.getByRole("button", { name: "🔊 Keşif sesi açık" }).click();
  const before = spoken.length;
  await history.hover();
  await page.waitForTimeout(350);
  expect(spoken).toHaveLength(before);
});

test("touch exploration selects first and activates on a second tap", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const spoken: string[] = [];
  await page.route("**/api/v1/student/interface-speech", async route => {
    spoken.push((route.request().postDataJSON() as { text: string }).text);
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Sesli keşfi başlat/ }).tap();
  const history = page.getByRole("button", { name: "9. sınıf tarih kitabını aç" });
  await history.tap();
  await expect(page).toHaveURL(/127\.0\.0\.1:18766\/$/);
  await expect.poll(() => spoken.some(value => value.includes("9. sınıf tarih kitabını aç"))).toBe(true);
  await history.tap();
  await expect(page).toHaveURL(/view=history/);
  await context.close();
});
