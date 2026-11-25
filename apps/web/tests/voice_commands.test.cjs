const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/voice_commands.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { parseVoiceCommand, parseTurkishNumber } = context.exports;

test("Turkish page numbers and exact navigation intents", () => {
  assert.equal(parseTurkishNumber("kırk iki"), 42);
  assert.equal(parseTurkishNumber("iki yüz altmış üç"), 263);
  assert.deepEqual({ ...parseVoiceCommand("Sayfa kırk iki") }, { kind: "go_page", number: 42 });
  assert.deepEqual({ ...parseVoiceCommand("sonraki soruya geç") }, { kind: "next_question" });
  assert.deepEqual({ ...parseVoiceCommand("bölüm üç") }, { kind: "select_region", number: 3 });
  assert.deepEqual({ ...parseVoiceCommand("Şık A'yı oku") }, { kind: "read_choice", label: "A" });
  assert.deepEqual({ ...parseVoiceCommand("şık B'yi seç") }, { kind: "select_choice", label: "B" });
  assert.deepEqual({ ...parseVoiceCommand("soru yirmi dört") }, { kind: "go_question", number: 24 });
  assert.deepEqual({ ...parseVoiceCommand("yanıtı onayla") }, { kind: "confirm" });
  assert.deepEqual({ ...parseVoiceCommand("tarih çalışmak istiyorum") }, { kind: "start_study" });
  assert.deepEqual({ ...parseVoiceCommand("çalışalım") }, { kind: "start_study" });
});

test("ambiguous or dangerous speech does not cause an action", () => {
  for (const phrase of ["cevabı gönder", "hepsini sil", "sonraki", "sayfa üç yüz bir", "bölüm sıfır", "soru sıfır", "şık F", "merhaba"]) {
    assert.equal(parseVoiceCommand(phrase), null, phrase);
  }
});

test("100 labeled Turkish text variants meet intent and safe-abstention gates", () => {
  const cases = [];
  const add = (phrases, expected) => phrases.forEach(text => cases.push({ text, expected }));
  add(["yardım", "komutlar", "ne diyebilirim"], { kind: "help" });
  add(["onayla", "yanıtı onayla", "işlemi onayla"], { kind: "confirm" });
  add(["yanıtı temizle", "cevabı temizle", "işaretlemeyi temizle"], { kind: "clear_answer" });
  add(["soruyu işaretle", "gözden geçirmek için işaretle"], { kind: "flag_question" });
  add(["kalan süre", "süreyi oku", "süre ne kadar"], { kind: "read_time" });
  add(["denemeyi bitir", "sınavı bitir"], { kind: "finish_exam" });
  add(["dur", "sesi durdur", "okumayı durdur", "seslendirmeyi durdur"], { kind: "stop_audio" });
  add(["şıkları aç", "şıkları göster", "seçenekleri aç", "seçenekleri göster"], { kind: "show_choices" });
  add(["sonraki soru", "bir sonraki soru", "sonraki soruya geç"], { kind: "next_question" });
  add(["önceki soru", "bir önceki soru", "önceki soruya geç"], { kind: "previous_question" });
  add(["oku", "seçili bölümü oku", "bölümü oku", "soruyu oku", "metni oku", "seslendir"], { kind: "read_selected" });
  add(["ana sayfa", "ana sayfaya dön", "kütüphane", "kütüphaneye dön", "geri dön"], { kind: "back" });
  add(["tarih çalışmak istiyorum", "tarih dersi çalışalım", "ders çalışmak istiyorum", "çalışalım"], { kind: "start_study" });
  for (const label of "ABCDE") {
    const suffix = label === "A" ? "yı" : "yi";
    add([`şık ${label} oku`, `şık ${label}'${suffix} oku`, `şık ${label}'${suffix} seslendir`], { kind: "read_choice", label });
    add([`şık ${label}'${suffix} seç`, `seçenek ${label}'${suffix} seç`], { kind: "select_choice", label });
  }
  cases.push(...[
    { text: "soru 1", expected: { kind: "go_question", number: 1 } },
    { text: "soruya git 21", expected: { kind: "go_question", number: 21 } },
    { text: "soruyu aç seksen bir", expected: { kind: "go_question", number: 81 } },
    { text: "soru 120", expected: { kind: "go_question", number: 120 } },
  ]);
  cases.push(...[
    { text: "sayfa 1", expected: { kind: "go_page", number: 1 } },
    { text: "sayfaya git kırk iki", expected: { kind: "go_page", number: 42 } },
    { text: "sayfayı aç 300", expected: { kind: "go_page", number: 300 } },
  ]);
  cases.push(...[
    { text: "bölüm 1", expected: { kind: "select_region", number: 1 } },
    { text: "bölüme git 100", expected: { kind: "select_region", number: 100 } },
    { text: "bölüm yirmi bir", expected: { kind: "select_region", number: 21 } },
  ]);

  const rejected = [
    "cevabı gönder", "hepsini sil", "sonraki", "sayfa üç yüz bir", "bölüm sıfır",
    "soru sıfır", "şık F", "merhaba", "denemeyi bitir ve onayla", "şık A'yı seç ve kaydet",
    "soruyu oku ve sonraki soru", "kalan süreyi oku", "bana yardım et", "soruları aç",
    "şık A'yı oku lütfen", "sayfa 0", "soru 121", "sil", "bitir", "onaylar mısın",
  ].map(text => ({ text, expected: null }));
  const all = [...cases, ...rejected];
  assert.equal(cases.length, 80);
  assert.equal(all.length, 100);
  assert.equal(new Set(all.map(item => item.text)).size, 100, "variants must be unique");
  const correct = all.filter(item => {
    const actual = parseVoiceCommand(item.text);
    return item.expected === null ? actual === null : JSON.stringify(actual) === JSON.stringify(item.expected);
  }).length;
  const falseActions = rejected.filter(item => parseVoiceCommand(item.text) !== null).length;
  console.log(`Voice text benchmark: ${correct}/100 intent outcomes; ${falseActions}/20 rejected phrases caused an action.`);
  assert.equal(correct, 100);
  assert.equal(falseActions, 0);
});
