import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test("entry and student menus keep one active choice and support visible navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Öğrenci olarak devam et" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Önceki alan" })).toBeDisabled();
  await page.getByRole("button", { name: "Sonraki alan" }).click();
  await expect(page.getByRole("heading", { name: "Öğretmen alanına geç" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Öğrenci olarak devam et" })).toBeHidden();
  await page.getByRole("link", { name: /Öğretmen alanına geç/ }).click();
  await expect(page.getByRole("heading", { name: "İçerik denetimi" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Soruları ve MEB kaynağını incele/ })).toBeVisible();

  await page.goto("/?mode=student");
  await page.getByRole("button", { name: "Sonraki öğrenme alanı" }).click();
  await expect(page.getByRole("heading", { name: "Tarih soru bankası" })).toBeVisible();
  await page.locator(".student-menu-viewport").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: "Braille ile yaz" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sonraki öğrenme alanı" })).toBeDisabled();
});
