import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("text size, contrast and motion preferences persist and keep the entry usable", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await expect.poll(() => page.evaluate(() => {
    const rectangles = [".accessibility-settings", ".explore-control", ".carousel-controls"]
      .map(selector => document.querySelector(selector)?.getBoundingClientRect()).filter((value): value is DOMRect => Boolean(value));
    return rectangles.every((first, index) => rectangles.slice(index + 1).every(second =>
      first.right <= second.left || second.right <= first.left || first.bottom <= second.top || second.bottom <= first.top));
  })).toBe(true);
  await page.getByText("Ayarlar", { exact: true }).click();
  await page.getByLabel("Yazı boyutu").selectOption("largest");
  await page.getByLabel("Yüksek kontrast").check();
  await page.getByLabel("Hareketi azalt").check();
  await expect(page.locator("html")).toHaveAttribute("data-text-size", "largest");
  await expect(page.locator("html")).toHaveAttribute("data-contrast", "high");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.reload();
  await expect(page.getByLabel("Yazı boyutu")).toHaveValue("largest");
  await expect(page.getByLabel("Yüksek kontrast")).toBeChecked();
  await expect(page.getByRole("link", { name: /Öğrenci olarak devam et/ })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const audit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(audit.violations).toEqual([]);
  await page.goto("/?mode=student");
  await expect.poll(() => page.locator(".student-menu-slide > button").first().evaluate(element => element.getBoundingClientRect().right <= window.innerWidth)).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const studentAudit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(studentAudit.violations).toEqual([]);
  await page.goto("/?mode=teacher");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Sesli keşfi başlat" })).toBeVisible();
});
