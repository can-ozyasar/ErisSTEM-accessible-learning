import { LearningExperience } from "./LearningExperience";

/** Preserve the existing practice route while opening the modular learning workshop. */
export function SetPractice({ api, onBack }: { api: string; onBack: () => void }) {
  return <LearningExperience api={api} onBack={onBack} />;
}
