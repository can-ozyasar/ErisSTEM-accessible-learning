import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("exam navigation saves and changes answers, resumes, hides solutions and erases records", async ({ page }) => {
  await page.goto("/?view=exam");
  await expect(page.getByLabel("Sınav ve düzenleme")).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Soru 1 / 6");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("radio", { name: "Çember", exact: true }).check();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeEnabled();
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toHaveCount(0);
  await page.getByRole("button", { name: "Sonra gözden geçirmek için işaretle" }).click();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı · gözden geçir", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Sonraki soru", exact: true }).click();
  await page.getByRole("radio", { name: "Elma", exact: true }).check();
  await expect(page.getByRole("button", { name: "Soru 2 · yanıtlı", exact: true })).toBeEnabled();
  await page.getByRole("radio", { name: "Su", exact: true }).check();
  await expect(page.getByRole("button", { name: "Önceki soru", exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole("radio", { name: "Çember", exact: true })).toBeChecked();
  await page.getByRole("button", { name: "Sonraki soru", exact: true }).click();
  await expect(page.getByRole("radio", { name: "Su", exact: true })).toBeChecked();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Provayı bitir", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Prova sonuçları");
  await expect(page.getByText("2 doğru · 0 yanlış · 4 boş.", { exact: false })).toBeVisible();
  await page.getByText("Soru 1: doğru", { exact: true }).click();
  await expect(page.getByText("Doğru yanıt: Çember.", { exact: false })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Prova verisini sil", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sınav düzenlemesini seçin");
  expect(await page.evaluate(() => sessionStorage.getItem("eristem:exam-session:v1"))).toBeNull();
});

test("expert panel records a requested change, rehearsal pilots cannot unlock publishing", async ({ page }) => {
  await page.goto("/?mode=learning-review");
  await expect(page.getByLabel("Öğrenme konusu")).toContainText("Çemberi keşfet");
  await page.getByLabel("Private uzman değerlendirme kaydı referansı").fill("automated-test-only");
  await page.getByRole("combobox", { name: "Karar", exact: true }).selectOption("changes_requested");
  await page.getByLabel("İnceleme notu veya istenen düzeltme").fill("Otomatik test kaydı; gerçek uzman görüşü değildir.");
  await page.getByRole("button", { name: "Uzman incelemesini kaydet" }).click();
  await expect(page.getByText("Son inceleme kaydı: automated-test-only.", { exact: false })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("link", { name: "Kullanıcı pilotu", exact: true }).click();
  await page.getByRole("button", { name: "Pilot oturumu aç", exact: true }).click();
  await expect(page.getByRole("heading", { name: /P-.*: görev gözlemleri/ })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const taskSelect = page.getByRole("combobox", { name: "Gözlenen görev", exact: true });
  const taskIds = await taskSelect.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
  for (const [i, id] of taskIds.entries()) {
    await taskSelect.selectOption(id);
    await page.getByRole("button", { name: "Görev gözlemini kaydet", exact: true }).click();
    await expect(page.getByText(`${i + 1} / 8 görev kaydedildi.`, { exact: false })).toBeVisible();
  }
  await page.getByRole("button", { name: "Pilotu tamamla", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pilotu tamamla", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "Yayın kontrolü", exact: true }).click();
  await expect(page.getByRole("button", { name: "İçeriğin yayınını onayla", exact: true })).toBeDisabled();
  await expect(page.getByText("Gerçek kullanıcıyla uygun tamamlanmış pilot: 0.", { exact: false })).toBeVisible();
});

test("real participant session cannot be created without consent", async ({ page }) => {
  await page.goto("/?mode=pilot");
  await page.getByLabel("Oturum türü").selectOption("participant");
  await expect(page.getByRole("button", { name: "Pilot oturumu aç", exact: true })).toBeDisabled();
  await page.getByLabel("Private rıza kaydı referansı").fill("test-only-consent-reference");
  await expect(page.getByRole("button", { name: "Pilot oturumu aç", exact: true })).toBeDisabled();
  // Do not fabricate an actual participant record in the browser smoke test.
  await page.getByLabel("Oturum türü").selectOption("rehearsal");
  await expect(page.getByRole("button", { name: "Pilot oturumu aç", exact: true })).toBeEnabled();
});
