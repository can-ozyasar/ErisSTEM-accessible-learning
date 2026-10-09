const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/speech_voices.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { turkishVoices } = context.exports;

test("never silently selects a non-Turkish browser voice", () => {
  const voices = [
    { lang: "en-US", voiceURI: "english", localService: true },
    { lang: "tr", voiceURI: "remote-turkish", localService: false },
    { lang: "tr", voiceURI: "generic", localService: true },
    { lang: "tr-TR", voiceURI: "turkish-local", localService: true },
  ];
  assert.deepEqual(turkishVoices(voices).map(voice => voice.voiceURI), ["turkish-local", "generic"]);
  assert.equal(turkishVoices([voices[0]]).length, 0);
});
