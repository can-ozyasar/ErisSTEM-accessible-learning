import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({ serviceWorkers: "block", trace: "off" });

test("private 81-question pilot hides answers and coaches only from its exact evidence", async ({ page }) => {
  const packPath = process.env.E2E_PRIVATE_PILOT_PACK;
  test.skip(!packPath, "Run with E2E_PRIVATE_PILOT_PACK to exercise the local private pack.");
  const pack = JSON.parse(readFileSync(packPath!, "utf8")) as {
    questions: { id: string; correct_label: string; choices: string[]; evidence: unknown[] }[];
  };
  const question = pack.questions[0];
  expect(pack.questions).toHaveLength(81);
  expect(question.evidence.length).toBeGreaterThan(0);
  const wrongChoiceIndex = question.choices.findIndex((_, index) => "ABCDE"[index] !== question.correct_label);
  expect(question.choices).toHaveLength(5);

  let started: Record<string, unknown> | undefined;
  let finished: Record<string, unknown> | undefined;
  const coachResponses: Record<string, unknown>[] = [];
  page.on("response", async response => {
    if (!response.ok()) return;
    const url = response.url();
    const method = response.request().method();
    if (method === "POST" && /\/student\/exams\/sessions$/.test(url)) {
      started = await response.json() as Record<string, unknown>;
    } else if (method === "POST" && /\/finish$/.test(url)) {
      finished = await response.json() as Record<string, unknown>;
    } else if (method === "POST" && /\/review\/[^/]+\/coach$/.test(url)) {
      coachResponses.push(await response.json() as Record<string, unknown>);
    }
  });

  await page.goto("/?mode=student&view=exam");
  await expect(page.getByText(/toplam 81 soru/)).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Soru 1 / 81");
  await expect(page.locator("#exam-question")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await expect.poll(() => started).toBeTruthy();
  expect(JSON.stringify((started as { questions: unknown[] }).questions)).not.toMatch(/correct_answer|correct_label|explanation/);

  await page.locator('input[name="exam-answer"]').nth(wrongChoiceIndex).check();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Soru 1 / 81");
  await expect(page.locator('input[name="exam-answer"]').nth(wrongChoiceIndex)).toBeChecked();

  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Provayı bitir", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Prova sonuçları");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await expect(page.getByText("Soru 1: yanlış", { exact: true })).toBeVisible();
  await expect.poll(() => finished).toBeTruthy();
  const finishedResult = (finished as { results: { correct_answer: string | null; explanation: string | null; source_available: boolean }[] }).results[0];
  expect(finishedResult).toMatchObject({ correct_answer: null, explanation: null, source_available: true });
  await page.getByText("Soru 1: yanlış", { exact: true }).click();
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toHaveCount(0);

  await page.getByRole("button", { name: "Kaynakla birlikte çöz" }).click();
  await expect.poll(() => coachResponses.length).toBe(1);
  const first = coachResponses[0] as { reply: { source_ids: string[]; can_reveal_explanation: boolean }; exam: { results: { correct_answer: string | null }[] } };
  expect(first.reply.source_ids.length).toBeGreaterThan(0);
  expect(first.reply.can_reveal_explanation).toBe(false);
  expect(first.exam.results[0].correct_answer).toBeNull();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toHaveCount(0);

  await page.getByLabel("Soru hakkındaki düşünceniz").fill("İki seçeneğin tarihsel ilişkisini karıştırdım.");
  await page.getByRole("button", { name: "Düşüncemi paylaş ve ikinci ipucunu aç" }).click();
  await expect.poll(() => coachResponses.length).toBe(2);
  const second = coachResponses[1] as { reply: { can_reveal_explanation: boolean }; exam: { results: { correct_answer: string | null; explanation: string | null }[] } };
  expect(second.reply.can_reveal_explanation).toBe(true);
  expect(second.exam.results[0].correct_answer).toBe(question.choices["ABCDE".indexOf(question.correct_label)]);
  expect(second.exam.results[0].explanation).toBeTruthy();
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toBeVisible();

  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Prova verisini sil", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sınav düzenlemesini seçin");
});

test("all private pilot questions without verified final evidence abstain safely", async ({ request }) => {
  const packPath = process.env.E2E_PRIVATE_PILOT_PACK;
  test.skip(!packPath, "Run with E2E_PRIVATE_PILOT_PACK to exercise the local private pack.");
  const pack = JSON.parse(readFileSync(packPath!, "utf8")) as {
    questions: { id: string; authorship: string; correct_label: string; final_bundle_verified?: boolean }[];
  };
  const withheld = pack.questions.filter(q => q.authorship === "ai_source_reviewed_local_pilot" && q.final_bundle_verified !== true);
  expect(withheld).toHaveLength(5);
  const base = "http://127.0.0.1:18766/api/v1/student/exams/sessions";
  const headers = { "X-Role": "student" };
  const createdResponse = await request.post(base, { headers, data: {
    profile_id: "yks-reader-2026", slot_id: "ayt", arrangement_confirmed: true,
    mode: "short", short_minutes: 5,
  } });
  expect(createdResponse.ok()).toBe(true);
  let exam = await createdResponse.json() as { id: string; revision: number; questions: { id: string }[] };
  expect(exam.questions).toHaveLength(81);

  for (const question of withheld) {
    const questionIndex = exam.questions.findIndex(item => item.id === question.id);
    expect(questionIndex).toBeGreaterThanOrEqual(0);
    const wrongIndex = "ABCDE".split("").findIndex(label => label !== question.correct_label);
    const answerResponse = await request.put(`${base}/${exam.id}/answer`, { headers, data: {
      revision: exam.revision, question_id: question.id, answer: `option-${wrongIndex + 1}`,
    } });
    expect(answerResponse.ok()).toBe(true);
    exam = await answerResponse.json() as typeof exam;
  }

  const finishResponse = await request.post(`${base}/${exam.id}/finish`, { headers, data: { revision: exam.revision } });
  expect(finishResponse.ok()).toBe(true);
  exam = await finishResponse.json() as typeof exam;
  const results = (exam as typeof exam & { results: { question_id: string; correct_answer: string | null; explanation: string | null; source_available: boolean }[] }).results;
  for (const question of withheld) {
    const result = results.find(item => item.question_id === question.id);
    expect(result).toMatchObject({ correct_answer: null, explanation: null, source_available: false });
    const response = await request.post(`${base}/${exam.id}/review/${question.id}/coach`, { headers, data: {
      revision: exam.revision, turn: 1, learner_response: "", external_coach_consent: false,
    } });
    expect(response.ok()).toBe(true);
    const coach = await response.json() as { reply: { stage: string; source_ids: string[]; can_reveal_explanation: boolean }; exam: { results: { correct_answer: string | null; explanation: string | null }[] } };
    expect(coach.reply).toMatchObject({ stage: "source_unavailable", source_ids: [], can_reveal_explanation: false });
    expect(coach.exam.results.find(item => item.question_id === question.id)).toMatchObject({ correct_answer: null, explanation: null });
  }

  await request.delete(`${base}/${exam.id}?revision=${exam.revision}`, { headers });
});

test("100 real-pack API sessions keep unique IDs, reject duplicate writes, and finish idempotently", async ({ request }) => {
  test.setTimeout(120_000);
  const packPath = process.env.E2E_PRIVATE_PILOT_PACK;
  test.skip(!packPath, "Run with E2E_PRIVATE_PILOT_PACK to stress the local private pack.");
  const pack = JSON.parse(readFileSync(packPath!, "utf8")) as {
    questions: { id: string; correct_label: string; choices: string[] }[];
  };
  const firstQuestion = pack.questions[0];
  const wrongIndex = firstQuestion.choices.findIndex((_, index) => "ABCDE"[index] !== firstQuestion.correct_label);
  const base = "http://127.0.0.1:18766/api/v1/student/exams/sessions";
  const headers = { "X-Role": "student" };
  const ids = new Set<string>();

  for (let iteration = 0; iteration < 100; iteration += 1) {
    const createdResponse = await request.post(base, { headers, data: {
      profile_id: "yks-reader-2026", slot_id: "ayt", arrangement_confirmed: true,
      mode: "short", short_minutes: 5,
    } });
    expect(createdResponse.ok(), `create session ${iteration + 1}`).toBe(true);
    const created = await createdResponse.json() as {
      id: string; revision: number; questions: { id: string }[]; answers: Record<string, string>;
    };
    expect(ids.has(created.id)).toBe(false);
    ids.add(created.id);
    expect(created.questions).toHaveLength(81);
    expect(created.answers).toEqual({});

    const answerPayload = {
      revision: created.revision, question_id: firstQuestion.id, answer: `option-${wrongIndex + 1}`,
    };
    const savedResponse = await request.put(`${base}/${created.id}/answer`, { headers, data: answerPayload });
    expect(savedResponse.ok(), `save answer in session ${iteration + 1}`).toBe(true);
    const saved = await savedResponse.json() as { revision: number; answers: Record<string, string> };
    expect(saved.answers[firstQuestion.id]).toBe(answerPayload.answer);

    const replay = await request.put(`${base}/${created.id}/answer`, { headers, data: answerPayload });
    expect(replay.status(), `reject stale replay in session ${iteration + 1}`).toBe(409);

    const finishResponse = await request.post(`${base}/${created.id}/finish`, {
      headers, data: { revision: saved.revision },
    });
    expect(finishResponse.ok(), `finish session ${iteration + 1}`).toBe(true);
    const finished = await finishResponse.json() as {
      id: string; revision: number; state: string; answers: Record<string, string>;
      results: { question_id: string; correct_answer: string | null; explanation: string | null }[];
    };
    expect(finished).toMatchObject({ id: created.id, state: "finished", answers: {} });
    expect(finished.results).toHaveLength(81);
    expect(new Set(finished.results.map(result => result.question_id)).size).toBe(81);
    expect(finished.results.find(result => result.question_id === firstQuestion.id)).toMatchObject({
      correct_answer: null, explanation: null,
    });

    const repeatedFinish = await request.post(`${base}/${created.id}/finish`, {
      headers, data: { revision: finished.revision },
    });
    expect(repeatedFinish.ok(), `idempotent finish ${iteration + 1}`).toBe(true);
    expect((await repeatedFinish.json()).results).toEqual(finished.results);
    const deleted = await request.delete(`${base}/${created.id}?revision=${finished.revision}`, { headers });
    expect(deleted.status(), `clean up session ${iteration + 1}`).toBe(204);
  }

  expect(ids.size).toBe(100);
});

test("keyboard alone completes the real pilot, post-exam coaching, and data deletion", async ({ page }) => {
  const packPath = process.env.E2E_PRIVATE_PILOT_PACK;
  test.skip(!packPath, "Run with E2E_PRIVATE_PILOT_PACK to exercise the local private pack.");
  const pack = JSON.parse(readFileSync(packPath!, "utf8")) as {
    questions: { correct_label: string; evidence: unknown[] }[];
  };
  expect(pack.questions).toHaveLength(81);
  expect(pack.questions[0].evidence.length).toBeGreaterThan(0);

  async function tabTo(locator: import("@playwright/test").Locator, maxTabs = 160) {
    const isFocused = async () => locator.evaluate(element => element === document.activeElement).catch(() => false);
    for (let count = 0; count <= maxTabs; count += 1) {
      if (await isFocused()) return;
      await page.keyboard.press("Tab");
      if (await isFocused()) return;
    }
    throw new Error(`Keyboard focus did not reach ${await locator.toString()}`);
  }

  await page.goto("/?mode=student&view=exam");
  const confirmation = page.getByRole("checkbox");
  await tabTo(confirmation);
  await page.keyboard.press("Space");
  const start = page.getByRole("button", { name: "Provayı başlat", exact: true });
  await tabTo(start);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Soru 1 / 81");

  const firstChoice = page.getByRole("radio").nth(0);
  await tabTo(firstChoice);
  await page.keyboard.press("Space");
  await expect(firstChoice).toBeChecked();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeEnabled();
  if (pack.questions[0].correct_label === "A") {
    await tabTo(firstChoice);
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("radio").nth(1)).toBeChecked();
    await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeEnabled();
  }

  const finish = page.getByRole("button", { name: "Provayı bitir", exact: true });
  await tabTo(finish);
  page.once("dialog", dialog => void dialog.accept());
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Prova sonuçları");

  const firstResult = page.getByText("Soru 1: yanlış", { exact: true });
  await tabTo(firstResult);
  await page.keyboard.press("Enter");
  await expect(firstResult.locator("xpath=.." )).toHaveAttribute("open", "");
  const firstCoach = page.getByRole("button", { name: "Kaynakla birlikte çöz", exact: true });
  await expect(firstCoach).toBeVisible();
  await tabTo(firstCoach);
  await page.keyboard.press("Enter");
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toHaveCount(0);

  const learnerResponse = page.getByLabel("Soru hakkındaki düşünceniz");
  await tabTo(learnerResponse);
  await page.keyboard.type("İki seçeneğin tarihsel ilişkisini karıştırdım.");
  const secondHint = page.getByRole("button", { name: "Düşüncemi paylaş ve ikinci ipucunu aç", exact: true });
  await tabTo(secondHint);
  await page.keyboard.press("Enter");
  await expect(page.getByText("Doğru yanıt:", { exact: false })).toBeVisible();

  const remove = page.getByRole("button", { name: "Prova verisini sil", exact: true });
  await tabTo(remove, 200);
  page.once("dialog", dialog => void dialog.accept());
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sınav düzenlemesini seçin");
});
