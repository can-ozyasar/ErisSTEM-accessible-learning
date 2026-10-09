const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/study_progress.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { progressKey, progressPrefix, parseProgress, recordSelfReview, dueUnitIds } = context.exports;

test("progress belongs to a published document revision", () => {
  assert.notEqual(progressKey("lesson", 1), progressKey("lesson", 2));
  assert.notEqual(progressKey("a:b", 1), progressKey("a", 1));
  assert.ok(progressKey("lesson", 1).startsWith(progressPrefix("lesson")));
});

test("only current published unit identifiers survive malformed or stale storage", () => {
  const parsed = parseProgress(JSON.stringify({ approved: { attempts: 1, nextReviewAt: 123 }, stale: { attempts: 2, nextReviewAt: 123 }, invalid: { attempts: -1, nextReviewAt: 0 } }), ["approved", "invalid"]);
  assert.deepEqual(JSON.parse(JSON.stringify(parsed)), { approved: { attempts: 1, nextReviewAt: 123 } });
  assert.deepEqual(JSON.parse(JSON.stringify(parseProgress("{", ["approved"]))), {});
});

test("remembered items become due later and failed recall is due immediately", () => {
  const first = recordSelfReview({}, "a", true, 1000);
  assert.deepEqual(dueUnitIds(["a", "b"], first, 1000), ["b"]);
  assert.deepEqual(dueUnitIds(["a"], first, 1000 + 86400000), ["a"]);
  const forgotten = recordSelfReview(first, "a", false, 2000);
  assert.deepEqual(dueUnitIds(["a"], forgotten, 2000), ["a"]);
  assert.equal(forgotten.a.attempts, 0);
});
