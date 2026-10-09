const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/table_reading.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { turkishCellReading, cellSpeechLabel } = context.exports;

test("set symbols have explicit Turkish names, ordinary words stay intact", () => {
  assert.equal(turkishCellReading("∪"), "birleşim");
  assert.equal(turkishCellReading("∈"), "elemanıdır");
  assert.equal(turkishCellReading("∉"), "elemanı değildir");
  assert.equal(turkishCellReading("A′"), "A asal işareti");
  assert.equal(turkishCellReading("x² + β"), "x karesi artı beta");
  assert.equal(turkishCellReading("x₁"), "x alt indis bir");
  assert.equal(turkishCellReading("A'nın tümleyeni"), "A'nın tümleyeni");
});

test("focused cell is read with coordinates and its published column header", () => {
  const cells = [
    { row: 1, column: 1, role: "header", text: "Sembol" },
    { row: 1, column: 2, role: "header", text: "Anlamı" },
    { row: 2, column: 1, role: "data", text: "∩" },
    { row: 2, column: 2, role: "data", text: "kesişim" },
  ];
  assert.equal(cellSpeechLabel(cells[2], cells), "Satır 2, sütun 1. Sembol: kesişim");
  assert.equal(cellSpeechLabel(cells[3], cells), "Satır 2, sütun 2. Anlamı: kesişim");
});

test("unknown notation fails closed for application speech", () => {
  assert.equal(turkishCellReading("A ★ B"), null);
  const cells = [{ row: 1, column: 1, role: "header", text: "★" }, { row: 2, column: 1, role: "data", text: "∪" }];
  assert.equal(cellSpeechLabel(cells[1], cells), null);
});

test("teacher-reviewed pronunciation overrides ambiguous symbol in one cell", () => {
  const cells = [
    { row: 1, column: 1, role: "header", text: "Sembol" },
    { row: 2, column: 1, role: "data", text: "A′", spoken_text: "A kümesinin tümleyeni" },
  ];
  assert.equal(cellSpeechLabel(cells[1], cells), "Satır 2, sütun 1. Sembol: A kümesinin tümleyeni");
});
