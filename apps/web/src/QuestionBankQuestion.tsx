import { useEffect, useRef, useState } from "react";
import { EXPLORE_READ_EVENT } from "./ExploreSpeech";
import { useLearningSpeech } from "./useLearningSpeech";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

export type QuestionBankQuestionData = {
  id: string; number: number; question_type: "multiple_choice" | "open_response" | "fill_blank" | "true_false"; status: "draft" | "review_required" | "approved";
  parts: { id: string; kind: "stem" | "prompt" | "statement" | "caption" | "instruction" | "choice_table_header"; text: string; spoken_text: string; source: { page: number; bbox: number[] } }[];
  choices: { label: "A" | "B" | "C" | "D" | "E"; text: string; spoken_text: string }[];
  visuals: { id: string; kind: string; description: string | null; description_reviewed: boolean; caption: string | null; source: { page: number; bbox: number[] } }[];
};
export type QuestionBankUnit = { id: string; kind: string; label: string; spoken_text: string };

/** One reviewed question, with independently focusable speech units. */
export function QuestionBankQuestion({ question, units: readingUnits, api, onPrevious, onNext, onBack }: {
  question: QuestionBankQuestionData; units: QuestionBankUnit[]; api: string; onPrevious?: () => void; onNext?: () => void; onBack?: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [audioStatus, setAudioStatus] = useState("");
  const [choicesShown, setChoicesShown] = useState(false);
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const player = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef<string | null>(null);
  const playbackSerial = useRef(0);
  const { speak, stop, status } = useLearningSpeech(1);
  useEffect(() => () => { playbackSerial.current++; player.current?.pause(); if (audioUrl.current) URL.revokeObjectURL(audioUrl.current); stop(); }, [stop]);
  const visibleUnits = readingUnits.filter(unit => unit.kind !== "choice");
  const current = readingUnits.find(unit => unit.id === selected && (choicesShown || unit.kind !== "choice")) ?? readingUnits[0];
  const navigationSequence = choicesShown ? readingUnits : visibleUnits;
  const navigationIndex = navigationSequence.findIndex(unit => unit.id === current.id);
  const stopAll = () => { playbackSerial.current++; stop(); player.current?.pause(); if (audioUrl.current) URL.revokeObjectURL(audioUrl.current); audioUrl.current = null; setAudioStatus(""); };
  const focus = (id: string) => { stopAll(); setSelected(id); };
  const play = async (target: QuestionBankUnit = current) => {
    stopAll(); const serial = playbackSerial.current; setAudioStatus("Yerel Türkçe ses hazırlanıyor.");
    try {
      const response = await fetch(`${api}/v1/question-bank/student/questions/${question.id}/audio/${target.id}`, { headers: { "X-Role": "student" } });
      if (!response.ok) throw Error();
      const url = URL.createObjectURL(await response.blob());
      if (serial !== playbackSerial.current) { URL.revokeObjectURL(url); return; }
      audioUrl.current = url;
      const next = new Audio(url); player.current = next; next.onended = () => setAudioStatus("Seçili bölüm okundu.");
      await next.play(); setAudioStatus(`${target.label} okunuyor.`);
    } catch { if (serial === playbackSerial.current) { setAudioStatus("Yerel ses kullanılamadı; cihazdaki Türkçe sese geçiliyor."); speak(target.spoken_text); } }
  };
  useEffect(() => {
    const readMarkedUnit = (event: Event) => {
      const id = (event as CustomEvent<{ id?: string }>).detail?.id;
      const target = readingUnits.find(unit => unit.id === id);
      if (!target) return;
      focus(target.id);
      void play(target);
    };
    window.addEventListener(EXPLORE_READ_EVENT, readMarkedUnit);
    return () => window.removeEventListener(EXPLORE_READ_EVENT, readMarkedUnit);
  });
  if (question.status !== "approved") return <p role="status">Bu soru henüz kaynak ve erişilebilirlik denetiminden geçmedi.</p>;
  const moveUnit = (offset: number) => {
    const target = navigationSequence[navigationIndex + offset];
    if (!target) { setAudioStatus(offset > 0 ? "Bu sorunun son bölümündesin." : "Bu sorunun ilk bölümündesin."); return; }
    focus(target.id); void play(target);
  };
  return <section className="question-bank-question" aria-labelledby={`${question.id}-heading`}>
    <p className="eyebrow">KAYNAKLA DOĞRULANMIŞ SORU</p><h2 id={`${question.id}-heading`}>Soru {question.number}</h2>
    {question.question_type !== "multiple_choice" && <p>Bu soru açık yanıt gerektirir; uygulama kendiliğinden doğru-yanlış kararı vermez.</p>}
    <nav aria-label="Sorular arasında gezinme"><button type="button" onClick={onPrevious} disabled={!onPrevious}>Önceki soru</button><button type="button" onClick={onNext} disabled={!onNext}>Sonraki soru</button></nav>
    <VoiceCommandPanel title="Soruda sesli ilerle" examples={["sonraki bölüm", "seçili bölümü oku", "şıkları göster", "şık A'yı oku", "sonraki soru"]}
      available={["read_selected", "stop_audio", ...(navigationIndex < navigationSequence.length - 1 ? ["next_unit" as const] : []), ...(navigationIndex > 0 ? ["previous_unit" as const] : []), ...(!choicesShown ? ["show_choices" as const] : []), ...(choicesShown ? ["read_choice" as const] : []), ...(onPrevious ? ["previous_question" as const] : []), ...(onNext ? ["next_question" as const] : []), ...(onBack ? ["back" as const] : [])]}
      onCommand={command => {
        if (command.kind === "next_unit") moveUnit(1);
        else if (command.kind === "previous_unit") moveUnit(-1);
        else if (command.kind === "read_selected") void play();
        else if (command.kind === "stop_audio") stopAll();
        else if (command.kind === "show_choices") setChoicesShown(true);
        else if (command.kind === "read_choice") { const target = readingUnits.find(unit => unit.id === `${question.id}-choice-${command.label}`); if (target) { focus(target.id); void play(target); } }
        else if (command.kind === "next_question") onNext?.();
        else if (command.kind === "previous_question") onPrevious?.();
        else if (command.kind === "back") onBack?.();
      }} />
    <section className="question-phase" aria-labelledby="question-read-title"><p className="phase-number">1 / OKU VE DİNLE</p><h3 id="question-read-title">Soru metni</h3><p>Sesli keşif açıkken bir bölüme dokunmak yalnız o bölümün tamamını okur; kapalıyken bölümü seçip aşağıdaki düğmeden dinleyebilirsin.</p><ol className="question-bank-units">{visibleUnits.map(unit => <li key={unit.id}><button type="button" data-explore-read-id={unit.id} data-explore-summary={`${unit.label}. Soru bölümü`} aria-current={current.id === unit.id ? "true" : undefined} onFocus={() => focus(unit.id)} onClick={() => focus(unit.id)}><strong>{unit.label}</strong><span>{unit.spoken_text}</span></button></li>)}</ol><div className="audio-actions"><p>Seçili bölüm: <strong>{current.label}</strong></p><button type="button" onClick={() => void play()}>Seçili bölümü dinle</button><button type="button" className="quiet-button" onClick={stopAll}>Sesi durdur</button></div><p role="status">{audioStatus || status}</p></section>
    <section className="question-phase" aria-labelledby="question-answer-title"><p className="phase-number">2 / DÜŞÜN VE YANITLA</p><h3 id="question-answer-title">Yanıtın</h3>{question.question_type === "multiple_choice" && !choicesShown && <><p>Önce soruyu düşün. Hazır olduğunda seçenekleri açabilirsin.</p><button type="button" onClick={() => setChoicesShown(true)}>Şıkları göster</button></>}
      {question.question_type === "multiple_choice" && choicesShown && <fieldset><legend>Bir şık seç</legend>{question.choices.map(choice => <label className="learning-option" key={choice.label}><input type="radio" name={`${question.id}-answer`} value={choice.label} data-explore-read-id={`${question.id}-choice-${choice.label}`} data-explore-summary={`Şık ${choice.label}`} checked={answer === choice.label} onFocus={() => focus(`${question.id}-choice-${choice.label}`)} onChange={() => setAnswer(choice.label)} /><span><strong>Şık {choice.label}</strong> {choice.text}</span></label>)}</fieldset>}
      {question.question_type !== "multiple_choice" && <label>Yanıt taslağım<textarea value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Yalnız bu oturumda tutulur." /></label>}
    </section>
    <section className="question-phase" aria-labelledby="question-reflect-title"><p className="phase-number">3 / GEREKÇELENDİR</p><h3 id="question-reflect-title">Nasıl düşündün?</h3><label>Gerekçem<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Hangi bilgiye dayanarak düşündün?" /></label><p className="source-note">Yanıt ve gerekçe yalnız bu oturumda kalır. Doğrulanmış cevap anahtarı bağlanmadığı için otomatik puanlama yapılmaz.</p></section>
  </section>;
}
