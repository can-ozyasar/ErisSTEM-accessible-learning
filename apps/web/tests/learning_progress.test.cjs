const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync(path.join(__dirname, "../src/learning_progress.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { learningKey, parseLearningProgress, markLearningHelp, recordLearningAnswer, skipLearningExercise, reviewAvailableAt, stageResults } = context.exports;
const exercises = [{ id: "baseline", stage: "baseline" }, { id: "guided", stage: "guided" }, { id: "transfer", stage: "transfer" }, { id: "review", stage: "review" }];

test("first attempt survives retries and assistance cannot become independent success", () => {
  let progress = recordLearningAnswer({}, exercises[1], false, true, 100);
  progress = recordLearningAnswer(progress, exercises[1], true, false, 200);
  assert.equal(progress.guided.attempts, 2);
  assert.equal(progress.guided.firstCorrect, false);
  assert.equal(progress.guided.helpUsed, true);
  assert.equal(stageResults(exercises, progress, "guided").independent, 0);
  const assisted = recordLearningAnswer(markLearningHelp({}, "guided"), exercises[1], true, false, 100);
  assert.equal(assisted.guided.firstHelpUsed, true);
  assert.equal(stageResults(exercises, assisted, "guided").independent, 0);
});

test("help requested while a submission is pending does not change its first-answer observation", () => {
  const progress = recordLearningAnswer(markLearningHelp({}, "guided"), exercises[1], true, false, 100, false);
  assert.equal(progress.guided.helpUsed, true);
  assert.equal(progress.guided.firstHelpUsed, false);
});

test("independent phases retain a single observation even if a client tries another answer", () => {
  const first = recordLearningAnswer({}, exercises[2], false, false, 100);
  const second = recordLearningAnswer(first, exercises[2], true, false, 200);
  assert.equal(first, second);
  assert.equal(second.transfer.firstCorrect, false);
  assert.equal(second.transfer.attempts, 1);
});

test("skips are distinct from wrong answers and review waits until learning is complete", () => {
  let progress = skipLearningExercise({}, "baseline", 100);
  assert.equal(progress.baseline.firstCorrect, null);
  assert.equal(stageResults(exercises, progress, "baseline").skipped, 1);
  assert.equal(stageResults(exercises, progress, "baseline").answered, 0);
  assert.equal(reviewAvailableAt(exercises, progress, 24), null);
  progress = recordLearningAnswer(progress, exercises[1], true, false, 200);
  progress = recordLearningAnswer(progress, exercises[2], true, false, 300);
  assert.equal(reviewAvailableAt(exercises, progress, 24), 300 + 86400000);
});

test("device storage is versioned, bounded and does not preserve arbitrary fields or stale tasks", () => {
  assert.notEqual(learningKey("a", "v1"), learningKey("a", "v2"));
  assert.notEqual(learningKey("a:b", "v1"), learningKey("a", "b:v1"));
  const progress = recordLearningAnswer({}, exercises[0], true, false, 100);
  const parsed = parseLearningProgress(JSON.stringify({ baseline: { ...progress.baseline, answer: "private" }, old: progress.baseline }), ["baseline"]);
  assert.deepEqual(JSON.parse(JSON.stringify(parsed)), JSON.parse(JSON.stringify(progress)));
  assert.deepEqual(JSON.parse(JSON.stringify(parseLearningProgress("{", ["baseline"]))), {});
  const invalid = { ...progress.baseline, attempts: 0 };
  assert.deepEqual(JSON.parse(JSON.stringify(parseLearningProgress(JSON.stringify({ baseline: invalid }), ["baseline"]))), {});
  assert.throws(() => skipLearningExercise({}, "baseline", NaN));
});
