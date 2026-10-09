import type { LearningExercise, LearningStage } from "./learning_types";

/** Device-only observations. No answers, identities, diagnoses, or lesson text. */
export type LearningRecord = {
  attempts: number; firstCorrect: boolean | null; firstHelpUsed: boolean;
  helpUsed: boolean; completed: boolean; skipped: boolean; completedAt: number | null;
};
export type LearningProgress = Record<string, LearningRecord>;
export const LEARNING_PREFIX = "eristem:learning:v1:";
export function learningKey(moduleId: string, version: string): string {
  return `${LEARNING_PREFIX}${encodeURIComponent(moduleId)}:${encodeURIComponent(version)}`;
}

function emptyRecord(): LearningRecord {
  return { attempts: 0, firstCorrect: null, firstHelpUsed: false, helpUsed: false,
    completed: false, skipped: false, completedAt: null };
}

export function parseLearningProgress(raw: string | null, ids: readonly string[]): LearningProgress {
  if (!raw || raw.length > 100_000) return {};
  try {
    const data: unknown = JSON.parse(raw);
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    const result: LearningProgress = {};
    for (const id of ids) {
      if (!Object.prototype.hasOwnProperty.call(data, id)) continue;
      const candidate: unknown = (data as Record<string, unknown>)[id];
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) continue;
      const r = candidate as Record<string, unknown>;
      if (!Number.isInteger(r.attempts) || Number(r.attempts) < 0 || Number(r.attempts) > 100 ||
          !(r.firstCorrect === null || typeof r.firstCorrect === "boolean") ||
          typeof r.firstHelpUsed !== "boolean" || typeof r.helpUsed !== "boolean" ||
          typeof r.completed !== "boolean" || typeof r.skipped !== "boolean" ||
          !(r.completedAt === null || (typeof r.completedAt === "number" && Number.isFinite(r.completedAt) && r.completedAt >= 0))) continue;
      // Reject inconsistent records rather than presenting misleading achievements.
      if ((r.attempts === 0) !== (r.firstCorrect === null) ||
          r.completed !== (r.completedAt !== null) || (r.skipped && !r.completed) ||
          (r.firstHelpUsed && !r.helpUsed)) continue;
      result[id] = { attempts: Number(r.attempts), firstCorrect: r.firstCorrect as boolean | null,
        firstHelpUsed: r.firstHelpUsed, helpUsed: r.helpUsed, completed: r.completed,
        skipped: r.skipped, completedAt: r.completedAt as number | null };
    }
    return result;
  } catch { return {}; }
}

export function markLearningHelp(progress: LearningProgress, id: string): LearningProgress {
  const previous = progress[id] ?? emptyRecord();
  return { ...progress, [id]: { ...previous, helpUsed: true } };
}

export function recordLearningAnswer(
  progress: LearningProgress, exercise: Pick<LearningExercise, "id" | "stage">,
  correct: boolean, hintShown: boolean, now: number, helpAtSubmission?: boolean,
): LearningProgress {
  if (!Number.isFinite(now) || now < 0) throw new Error("invalid_learning_time");
  const previous = progress[exercise.id] ?? emptyRecord();
  if (previous.completed) return progress;
  const completed = exercise.stage !== "guided" || correct;
  return { ...progress, [exercise.id]: {
    attempts: Math.min(previous.attempts + 1, 100),
    firstCorrect: previous.firstCorrect ?? correct,
    // A hint returned AFTER a first answer does not contaminate that first observation.
    firstHelpUsed: previous.attempts === 0 ? (helpAtSubmission ?? previous.helpUsed) : previous.firstHelpUsed,
    helpUsed: previous.helpUsed || hintShown, completed, skipped: false,
    completedAt: completed ? now : null,
  } };
}

export function skipLearningExercise(progress: LearningProgress, id: string, now: number): LearningProgress {
  if (!Number.isFinite(now) || now < 0) throw new Error("invalid_learning_time");
  const previous = progress[id] ?? emptyRecord();
  if (previous.completed) return progress;
  return { ...progress, [id]: { ...previous, completed: true, skipped: true, completedAt: now } };
}

export function reviewAvailableAt(
  exercises: readonly Pick<LearningExercise, "id" | "stage">[], progress: LearningProgress, delayHours: number,
): number | null {
  const learning = exercises.filter(item => item.stage !== "review");
  if (!learning.length || !Number.isFinite(delayHours) || delayHours < 0 ||
      learning.some(item => !progress[item.id]?.completed)) return null;
  return Math.max(...learning.map(item => progress[item.id].completedAt ?? 0)) + delayHours * 3_600_000;
}

export function stageResults(
  exercises: readonly Pick<LearningExercise, "id" | "stage">[], progress: LearningProgress, stage: LearningStage,
): { total: number; answered: number; firstCorrect: number; independent: number; helped: number; skipped: number } {
  const items = exercises.filter(item => item.stage === stage).map(item => progress[item.id]);
  return {
    total: items.length, answered: items.filter(item => item?.attempts > 0).length,
    firstCorrect: items.filter(item => item?.firstCorrect === true).length,
    independent: items.filter(item => item?.firstCorrect === true && !item.firstHelpUsed).length,
    helped: items.filter(item => item?.helpUsed).length,
    skipped: items.filter(item => item?.skipped).length,
  };
}
