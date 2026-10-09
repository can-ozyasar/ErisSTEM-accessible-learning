/** Local-only, source-revision-bound self-review. No lesson text or answers are stored. */
export type ReviewRecord = { attempts: number; nextReviewAt: number };
export type ReviewProgress = Record<string, ReviewRecord>;

const DAY = 24 * 60 * 60 * 1000;
const INTERVAL_DAYS = [1, 3, 7, 14];

export function progressPrefix(documentId: string): string {
  return `eristem:study:v1:${encodeURIComponent(documentId)}:`;
}

export function progressKey(documentId: string, publishedRevision: number): string {
  return `${progressPrefix(documentId)}${publishedRevision}`;
}

export function parseProgress(raw: string | null, allowedIds: readonly string[]): ReviewProgress {
  if (!raw || raw.length > 100_000) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    const allowed = new Set(allowedIds);
    const result: ReviewProgress = {};
    for (const [id, record] of Object.entries(parsed)) {
      if (!allowed.has(id) || typeof record !== "object" || record === null || Array.isArray(record)) continue;
      const candidate = record as Record<string, unknown>;
      if (Number.isInteger(candidate.attempts) && Number(candidate.attempts) >= 0 && Number(candidate.attempts) <= 1000 &&
          typeof candidate.nextReviewAt === "number" && Number.isFinite(candidate.nextReviewAt) && candidate.nextReviewAt >= 0) {
        result[id] = { attempts: Number(candidate.attempts), nextReviewAt: candidate.nextReviewAt };
      }
    }
    return result;
  } catch {
    return {};
  }
}

export function recordSelfReview(progress: ReviewProgress, unitId: string, remembered: boolean, now: number): ReviewProgress {
  if (!Number.isFinite(now) || now < 0) throw new Error("invalid_review_time");
  const previous = progress[unitId];
  const attempts = remembered ? Math.min((previous?.attempts ?? 0) + 1, 1000) : 0;
  const days = remembered ? INTERVAL_DAYS[Math.min(attempts - 1, INTERVAL_DAYS.length - 1)] : 0;
  return { ...progress, [unitId]: { attempts, nextReviewAt: now + days * DAY } };
}

export function dueUnitIds(unitIds: readonly string[], progress: ReviewProgress, now: number): string[] {
  return unitIds.filter(id => !progress[id] || progress[id].nextReviewAt <= now);
}
