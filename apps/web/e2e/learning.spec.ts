import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function openWorkshop(page: Page, title: string) {
  await page.goto("/?view=practice");
  await page.getByRole("button", { name: `${title}: çalışmayı aç`, exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(title);
}
async function choose(page: Page, name: string) {
  await page.getByRole("radio", { name, exact: true }).check();
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sonraki adıma geç", exact: true })).toBeVisible();
}
async function next(page: Page) {
  await page.getByRole("button", { name: "Sonraki adıma geç", exact: true }).click();
}

test("circle: assistance, single first attempts, resume, delayed fresh questions and deletion", async ({ page }) => {
  await openWorkshop(page, "Çemberi keşfet");
  await expect(page.locator("h1")).toBeFocused();
  await expect(page.getByText("Kavramı keşfet:", { exact: false })).toHaveCount(0);
  await choose(page, "Merkeze uzaklıkların eşit olması");
  await next(page);
  await page.getByText("Kavramı keşfet: Çemberi tanıtan ilişki", { exact: true }).click();
  await expect(page.getByText("Matematiksel çember kalın bir cisim", { exact: false })).toBeVisible();
  await choose(page, "Çember");
  await expect(page.getByText("İlk yanıtınız açıklama yardımıyla doğruydu.")).toBeVisible();
  await next(page);
  await page.reload();
  await page.getByRole("button", { name: "Çemberi keşfet: çalışmayı aç", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Karşı örnek", exact: true })).toBeVisible();
  await choose(page, "Hayır, uzaklık ilişkisi de gerekir");
  await next(page);
  await expect(page.getByText("Kavramı keşfet:", { exact: false })).toHaveCount(0);
  await choose(page, "İçi dolu bir daire");
  await expect(page.getByRole("button", { name: "Yanıtı gönder", exact: true })).toHaveCount(0);
  await next(page);
  await choose(page, "Hayır, merkezin kendisine uzaklığı sıfırdır");
  await next(page);
  await expect(page.getByRole("button", { name: "Gecikmeli denemeyi başlat" })).toBeDisabled();
  const guidedRow = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Rehberli çalışma", exact: true }) });
  await expect(guidedRow.getByRole("cell").nth(2)).toHaveText("1");
  // Move only the device clock, retaining real recorded answers and the real API.
  await page.clock.install();
  await page.clock.fastForward(24 * 60 * 60 * 1000 + 15_000);
  await page.getByRole("button", { name: "Gecikmeli denemeyi başlat" }).click();
  await expect(page.getByText("Bir düzlemde O noktasına tam 7 birim", { exact: false }).first()).toBeVisible();
  await choose(page, "Hayır, O'nun kendisine uzaklığı 7 birim değil");
  await next(page);
  await choose(page, "Merkezden çevreye uzaklıklar eşittir");
  await next(page);
  await expect(page.getByText("Gecikmeli deneme tamamlandı.", { exact: false })).toBeVisible();
  const keys = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("eristem:learning:v1:")));
  const saved = await page.evaluate(key => localStorage.getItem(key), keys[0]);
  expect(saved).not.toContain("option-");
  expect(saved).not.toContain("answer");
  await page.getByRole("button", { name: "Öğrenme konularına dön" }).click();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Bu cihazdaki atölye kayıtlarını ve tercihleri sil" }).click();
  expect(await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("eristem:learning:v1:")))).toEqual([]);
});

test("set syntax errors preserve the first observation and targeted hints stay in guidance", async ({ page }) => {
  await openWorkshop(page, "Kümeler ve ilişkiler");
  for (let i = 0; i < 3; i++) await page.getByRole("button", { name: "Bu soruyu geç", exact: true }).click();
  await page.getByLabel("Sonuç kümesi", { exact: true }).fill("1+2");
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByText("Bu bir giriş biçimi sorunudur", { exact: false })).toBeVisible();
  await page.getByLabel("Sonuç kümesi", { exact: true }).fill("{2}");
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByText("İpucu: Yanıt yalnız ortak", { exact: false })).toBeVisible();
  await page.getByLabel("Sonuç kümesi", { exact: true }).fill("{1,2,3,4}");
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByText("İpucu veya açıklamayla çalışmayı tamamladınız.", { exact: false })).toBeVisible();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("eristem:learning:v1:sets:sets-learning-v2") ?? "{}"));
  expect(saved["union-guided"].attempts).toBe(2);
  expect(saved["union-guided"].firstCorrect).toBe(false);
  expect(saved["union-baseline"].skipped).toBe(true);
});

test("a connection failure retains the answer and does not become an incorrect attempt", async ({ page }) => {
  await openWorkshop(page, "Çemberi keşfet");
  await page.route("**/exercises/**/check", route => route.abort());
  await page.getByRole("radio", { name: "Merkeze uzaklıkların eşit olması", exact: true }).check();
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByText("Yanıt kontrol edilemedi.", { exact: false })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Merkeze uzaklıkların eşit olması", exact: true })).toBeChecked();
  expect(await page.evaluate(() => localStorage.getItem("eristem:learning:v1:circle:circle-learning-v1"))).toBeNull();
  await page.unroute("**/exercises/**/check");
  await page.getByRole("button", { name: "Yanıtı gönder", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sonraki adıma geç" })).toBeVisible();
});

test("catalog, choice, guided exploration and summaries pass automated accessibility on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/?view=practice");
  await expect(page.getByRole("button", { name: "Uçak: parçalar ve yönler: çalışmayı aç", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/learning-catalog-mobile.png", fullPage: true });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Uçak: parçalar ve yönler: çalışmayı aç", exact: true }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Bu soruyu geç", exact: true }).click();
  await page.getByText("Kavramı keşfet: Uçak: bütün, parçalar ve ilişkiler", { exact: true }).click();
  await page.getByText("Anlatım ve görünüm tercihleri", { exact: true }).click();
  await page.getByRole("checkbox", { name: "Daha büyük metin" }).check();
  await page.getByText("Anlatım ve görünüm tercihleri", { exact: true }).click();
  await page.screenshot({ path: "test-results/learning-exploration-mobile.png", fullPage: true });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Bu soruyu geç", exact: true }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "Çalışma sonuçları tablosu; yatay kaydırılabilir" }).focus();
  await expect(page.getByRole("region", { name: "Çalışma sonuçları tablosu; yatay kaydırılabilir" })).toBeFocused();
});
