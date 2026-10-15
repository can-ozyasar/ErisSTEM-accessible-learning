import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({ serviceWorkers: "block" });

test("typed commands route to the intended student area; unknown text does nothing", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByLabel("Komutu yazarak dene").fill("sonraki");
  await page.getByRole("button", { name: "Uygula" }).click();
  await expect(page.getByText("İşlem yapılmadı", { exact: false })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("view")).toBeNull();
  await page.getByLabel("Komutu yazarak dene").fill("tarih kitabını aç");
  await page.getByRole("button", { name: "Uygula" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Tarih");
  expect(new URL(page.url()).searchParams.get("view")).toBe("history");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("one-shot local microphone result routes without contacting the app API", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: class {
      static async available() { return "available"; }
      lang = ""; continuous = false; interimResults = false; maxAlternatives = 1; processLocally = true;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onresult: ((event: { results: { transcript: string }[][] }) => void) | null = null;
      onerror: (() => void) | null = null;
      start() { this.onstart?.(); window.setTimeout(() => { this.onresult?.({ results: [[{ transcript: "soru bankasını aç" }]] }); this.onend?.(); }, 0); }
      abort() { this.onend?.(); }
    } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Bir komut dinle" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Bir soruya odaklan.");
  expect(new URL(page.url()).searchParams.get("view")).toBe("question-bank");
});

test("question voice commands reveal and read a choice without selecting an answer", async ({ page }) => {
  const id = "p3-c1-q1";
  await page.route("**/api/v1/question-bank/student/questions", route => route.fulfill({ json: [{ id, number: 1, page: 3, question_type: "multiple_choice", context: { topic: "Tarih Öğrenmenin Faydaları", test_name: "Kavrama Testi", test_number: 1 } }] }));
  await page.route(`**/api/v1/question-bank/student/questions/${id}`, route => route.fulfill({ json: {
    question: { id, number: 1, question_type: "multiple_choice", status: "approved", parts: [], visuals: [], choices: "ABCDE".split("").map(label => ({ label, text: `Seçenek ${label}`, spoken_text: `Seçenek ${label}` })) },
    units: [{ id, kind: "question", label: "Soru 1", spoken_text: "Soru bir" }, { id: `${id}-stem`, kind: "stem", label: "Soru metni", spoken_text: "Örnek soru" }, ..."ABCDE".split("").map(label => ({ id: `${id}-choice-${label}`, kind: "choice", label: `Şık ${label}`, spoken_text: `Şık ${label}, seçenek ${label}` }))],
  } }));
  let requestedChoice = false;
  await page.route(`**/api/v1/question-bank/student/questions/${id}/audio/${id}-choice-A`, route => { requestedChoice = true; return route.fulfill({ status: 503 }); });
  await page.goto("/?view=question-bank");
  await expect(page.getByRole("heading", { name: "Soru 1" })).toBeVisible({ timeout: 5000 });
  await page.getByLabel("Komutu yazarak dene").fill("şıkları göster");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  await expect(page.getByRole("radio", { name: /Şık A/ })).toBeVisible();
  await page.getByLabel("Komutu yazarak dene").fill("şık A'yı oku");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  await expect.poll(() => requestedChoice).toBe(true);
  await expect(page.getByRole("radio", { name: /Şık A/ })).not.toBeChecked();
});
