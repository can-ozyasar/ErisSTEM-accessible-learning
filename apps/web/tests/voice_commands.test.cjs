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
  assert.deepEqual({ ...parseVoiceCommand("tarih çalışmak istiyorum") }, { kind: "start_study" });
  assert.deepEqual({ ...parseVoiceCommand("çalışalım") }, { kind: "start_study" });
});

test("ambiguous or dangerous speech does not cause an action", () => {
  for (const phrase of ["cevabı gönder", "hepsini sil", "sonraki", "sayfa üç yüz bir", "bölüm sıfır", "soru beş", "şık F", "merhaba"]) {
    assert.equal(parseVoiceCommand(phrase), null, phrase);
  }
});
