import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({ serviceWorkers: "block" });

test("exam stem and individual choice use session-bound audio without saving an answer", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "Audio", { configurable: true, value: class {
      playbackRate = 1;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(_source: string) {}
      play() { return Promise.resolve(); }
      pause() {}
    } });
  });
  const units: string[] = [];
  await page.route("**/api/v1/student/exams/sessions/*/questions/*/audio/*", async route => {
    const unit = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    units.push(unit);
    await route.fulfill({ status: 200, contentType: "audio/wav",
      headers: { "X-Audio-Source": unit === "stem" ? "piper" : "fine-tuned-v5" },
      body: Buffer.from("RIFF0000WAVE" + "0".repeat(32)) });
  });
  await page.goto("/?mode=student&view=exam");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  await page.getByRole("button", { name: "Soruyu tekrar seslendir" }).click();
  await expect.poll(() => units.includes("stem")).toBe(true);
  await expect(page.getByText("Yerel Piper Türkçe sesiyle okunuyor.", { exact: true })).toBeVisible();
  await page.getByLabel("Komutu yazarak dene").fill("Şık A'yı oku");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  await expect.poll(() => units.includes("choice-A")).toBe(true);
  await expect(page.getByText("Fine-tune edilmiş Türkçe sesle okunuyor.", { exact: true })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Çember", exact: true })).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Soru 1 · boş", exact: true })).toBeVisible();
});

test("showing choices reads separate audio assets in order and stop cancels the remaining queue", async ({ page }) => {
  await page.addInitScript(() => {
    const state = window as Window & { currentAudio?: { onended: (() => void) | null }; finishCurrentAudio?: () => void; audioStarts?: number };
    state.audioStarts = 0;
    Object.defineProperty(window, "Audio", { configurable: true, value: class {
      playbackRate = 1;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(_source: string) {}
      play() { state.currentAudio = this; state.audioStarts = (state.audioStarts ?? 0) + 1; return Promise.resolve(); }
      pause() {}
    } });
    state.finishCurrentAudio = () => state.currentAudio?.onended?.();
  });
  const units: string[] = [];
  await page.route("**/api/v1/student/exams/sessions/*/questions/*/audio/choice-*", async route => {
    units.push(new URL(route.request().url()).pathname.split("/").pop() ?? "");
    await route.fulfill({ status: 200, contentType: "audio/wav", headers: { "X-Audio-Source": "fine-tuned-v5" },
      body: Buffer.from("RIFF0000WAVE" + "0".repeat(32)) });
  });
  await page.goto("/?mode=student&view=exam");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  const command = page.getByLabel("Komutu yazarak dene");
  await command.fill("şıkları göster");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  for (const [index, unit] of ["choice-A", "choice-B", "choice-C"].entries()) {
    await expect.poll(() => units.length).toBe(index + 1);
    expect(units[index]).toBe(unit);
    if (index < 2) await page.evaluate(() => (window as Window & { finishCurrentAudio: () => void }).finishCurrentAudio());
  }
  await command.fill("şıkları göster");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { audioStarts: number }).audioStarts)).toBe(4);
  await command.fill("sesi durdur");
  await page.getByRole("button", { name: "Uygula", exact: true }).click();
  await page.evaluate(() => (window as Window & { finishCurrentAudio: () => void }).finishCurrentAudio());
  await page.waitForTimeout(100);
  expect(units).toEqual(["choice-A", "choice-B", "choice-C"]);
  await expect.poll(() => page.evaluate(() => (window as Window & { audioStarts: number }).audioStarts)).toBe(4);
});

test("voice answer selection, clearing and finishing each wait for a separate confirmation", async ({ page }) => {
  await page.goto("/?mode=student&view=exam");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  const command = page.getByLabel("Komutu yazarak dene");
  const apply = page.getByRole("button", { name: "Uygula", exact: true });
  await command.fill("şık A'yı seç");
  await apply.click();
  await expect(page.getByRole("button", { name: "Soru 1 · boş", exact: true })).toBeVisible();
  await command.fill("onayla");
  await apply.click();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeVisible();
  await command.fill("yanıtı temizle");
  await apply.click();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeVisible();
  await command.fill("onayla");
  await apply.click();
  await expect(page.getByRole("button", { name: "Soru 1 · boş", exact: true })).toBeVisible();
  await command.fill("denemeyi bitir");
  await apply.click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Soru 1 / 6");
  await command.fill("onayla");
  await apply.click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Prova sonuçları");
});

test("coach dictation remains a local draft until the learner sends it", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: class {
      static async available(options: { processLocally: boolean }) { return options.processLocally ? "available" : "unavailable"; }
      lang = ""; continuous = false; interimResults = false; processLocally = false;
      onresult: ((event: { results: { transcript: string }[][] }) => void) | null = null;
      onend: (() => void) | null = null; onerror: (() => void) | null = null;
      start() { if (this.processLocally) window.setTimeout(() => { this.onresult?.({ results: [[{ transcript: "Tarihleri karıştırdım" }]] }); this.onend?.(); }, 0); }
      abort() { this.onend?.(); }
    } });
  });
  await page.route("**/api/v1/student/exams/sessions/*/finish", async route => {
    const response = await route.fetch();
    const exam = await response.json();
    exam.results[0].source_available = true;
    exam.results[0].coach_turns = 1;
    exam.results[0].coach_text = "Ne düşünüyorsun?";
    await route.fulfill({ response, json: exam });
  });
  let sent: unknown = null;
  await page.route("**/api/v1/student/exams/sessions/*/review/*/coach", async route => {
    sent = route.request().postDataJSON();
    await route.fulfill({ status: 503, json: { detail: "test" } });
  });
  await page.goto("/?mode=student&view=exam");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Provayı başlat", exact: true }).click();
  await page.getByRole("radio", { name: "Doğru parçası", exact: true }).check();
  await expect(page.getByRole("button", { name: "Soru 1 · yanıtlı", exact: true })).toBeEnabled();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Provayı bitir", exact: true }).click();
  await page.getByText("Soru 1: yanlış", { exact: true }).click();
  await page.getByRole("button", { name: "Düşüncemi konuşarak yaz" }).click();
  await expect(page.getByLabel("Soru hakkındaki düşünceniz")).toHaveValue("Tarihleri karıştırdım");
  expect(sent).toBeNull();
  await page.getByRole("button", { name: "Düşüncemi paylaş ve ikinci ipucunu aç" }).click();
  await expect.poll(() => sent).toMatchObject({ learner_response: "Tarihleri karıştırdım", turn: 2 });
});

test("exam navigation saves and changes answers, resumes, hides solutions and erases records", async ({ page }) => {
  await page.goto("/?mode=student&view=exam");
  await expect(page.getByLabel("Sınav ve düzenleme")).toBeVisible();
  await expect(page.getByLabel("Sınav ve düzenleme")).toHaveValue("yks-reader-2026");
  await expect(page.getByLabel("Oturum")).toHaveValue("ayt");
  await expect(page.getByText(/Bu oturumda 6 soru gösterilir/)).toBeVisible();
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
