import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.use({ serviceWorkers: "block", viewport: { width: 390, height: 844 } });

test("question flow preserves focus, marks the choice and reads the displayed tutor reply", async ({ page }) => {
  const reply = "A seçeneğini hangi tarihsel olayla ilişkilendiriyorsun?";
  const spoken: string[] = [];
  let oldAudioCalls = 0;
  await page.route("**/api/v1/student/interface-speech", route => {
    spoken.push((route.request().postDataJSON() as { text: string }).text);
    return route.fulfill({ status: 503, body: "{}" });
  });
  await page.route("**/api/v1/question-bank/student/questions", route => route.fulfill({ json: [1, 2].map(number => ({
    id: `q${number}`, number, page: 12, question_type: "multiple_choice", context: { topic: "İlk Çağ Uygarlıkları", test_name: "Kavrama Testi", test_number: 1 },
  })) }));
  await page.route(/\/api\/v1\/question-bank\/student\/questions\/q[12]$/, route => {
    const number = Number(route.request().url().at(-1));
    return route.fulfill({ json: {
      question: { id: `q${number}`, number, question_type: "multiple_choice", status: "approved",
        parts: [{ id: `p${number}`, kind: "stem", text: "Bu soru hangi uygarlığı soruyor?", spoken_text: "Bu soru hangi uygarlığı soruyor?", source: { page: 12, bbox: [] } }],
        choices: ["A", "B", "C", "D", "E"].map(label => ({ label, text: `${label} seçeneği`, spoken_text: `${label} seçeneği` })), visuals: [] },
      units: [{ id: `p${number}`, kind: "stem", label: "Soru metni", spoken_text: "Bu soru hangi uygarlığı soruyor?" }], audio_segments: [],
    } });
  });
  await page.route("**/api/v1/question-bank/student/questions/q1/tutor", route => route.fulfill({ json: { reply, stage: "justify", sources: [] } }));
  await page.route("**/api/v1/question-bank/student/questions/q1/tutor/audio", route => { oldAudioCalls++; return route.fulfill({ status: 500 }); });

  await page.goto("/?mode=student&view=question-bank");
  const heading = page.getByRole("heading", { name: "Soru 1" });
  await expect(heading).toBeFocused();
  await page.getByRole("radio", { name: "A A seçeneği" }).check();
  await expect(page.getByText("Seçildi", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Takıldım, birlikte çözelim" }).click();
  await page.getByRole("button", { name: "İlk ipucunu iste" }).click();
  await expect(page.getByText(reply)).toBeVisible();
  await page.getByRole("button", { name: "Yanıtı dinle" }).click();
  await expect.poll(() => spoken.includes(reply)).toBe(true);
  expect(oldAudioCalls).toBe(0);
  await page.getByRole("button", { name: "Sonraki soru" }).click();
  await expect(page.getByRole("heading", { name: "Soru 2" })).toBeFocused();
  await page.setViewportSize({ width: 320, height: 720 });
  await page.getByText("Ayarlar", { exact: true }).click();
  await page.getByLabel("Yazı boyutu").selectOption("largest");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const audit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(audit.violations).toEqual([]);
});
