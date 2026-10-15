import { expect, test } from "@playwright/test";

test.use({ serviceWorkers: "block" });

test("student can choose a source-derived topic and test before a question", async ({ page }) => {
  const contexts = [
    { topic: "Tarih Öğrenmenin Faydaları", test_name: "Kavrama Testi", test_number: 1 },
    { topic: "Eski Çağ'da Hukuk", test_name: "Geliştirme Testi", test_number: 10 },
  ];
  await page.route("**/api/v1/question-bank/student/questions", route => route.fulfill({ json: contexts.map((context, index) => ({
    id: `q-${index + 1}`, number: index + 1, page: index + 3, question_type: "multiple_choice", context,
  })) }));
  await page.route(/\/api\/v1\/question-bank\/student\/questions\/q-[12]$/, route => {
    const id = route.request().url().endsWith("q-1") ? "q-1" : "q-2";
    return route.fulfill({ json: {
      question: { id, number: id === "q-1" ? 1 : 2, question_type: "multiple_choice", status: "approved", parts: [], visuals: [], choices: "ABCDE".split("").map(label => ({ label, text: label, spoken_text: label })) },
      units: [{ id, kind: "question", label: id === "q-1" ? "Soru 1" : "Soru 2", spoken_text: id },
        { id: `${id}-stem`, kind: "stem", label: "Soru metni", spoken_text: "Kaynak sorusu" }],
    } });
  });
  await page.goto("/?view=question-bank");
  await expect(page.getByRole("heading", { name: "Soru 1" })).toBeVisible();
  await page.getByLabel("Konu seç").selectOption("Eski Çağ'da Hukuk");
  await expect(page.getByRole("heading", { name: "Soru 2" })).toBeVisible();
  await expect(page.getByText("Konu: Eski Çağ'da Hukuk · Geliştirme Testi 10", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Test seç").locator("option")).toHaveCount(2);
});
