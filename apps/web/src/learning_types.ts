export type LearningStage = "baseline" | "guided" | "transfer" | "review";
export type LearningExercise = {
  id: string; stage: LearningStage; topic: string; question: string; spoken_question: string;
  answer_kind: "set" | "choice"; answer_format: string; lesson_id: string;
  choices: { id: string; text: string }[];
};
export type LearningLesson = {
  id: string; title: string; short_description: string; detailed_description: string[];
  exploration: string[]; limitation: string;
};
export type LearningContext = "formal_learning" | "exam_preparation" | "higher_education" | "daily_or_professional";
export type LearningScope = {
  applicable_contexts: LearningContext[]; context_note: string; representation_options: string[];
};
export type ModuleSummary = { id: string; version: string; title: string; goal: string; materials: string; scope: LearningScope };
export type LearningModule = ModuleSummary & {
  provenance: string; review_delay_hours: number; lessons: LearningLesson[]; exercises: LearningExercise[];
};
export type LearningFeedback = {
  correct: boolean; valid: boolean; message: string;
  error_kind: "format" | "answer_mismatch" | null; hint: string | null;
};
