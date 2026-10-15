import { LearningExperience } from "./LearningExperience";

/** Preserve the existing practice route while opening the modular learning workshop. */
export function SetPractice({ api, onBack, onOpenDocument }: {
  api: string; onBack: () => void; onOpenDocument: (documentId: string) => void;
}) {
  return <LearningExperience api={api} onBack={onBack} onOpenDocument={onOpenDocument} />;
}
