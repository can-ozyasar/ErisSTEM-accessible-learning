import { useEffect, useRef, useState } from "react";
import { EXPLORE_READ_EVENT } from "./ExploreSpeech";
import { fetchAudio } from "./audio_cache";
import { QuestionTutor } from "./QuestionTutor";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

export type QuestionBankQuestionData = {
  id: string; number: number; question_type: "multiple_choice" | "open_response" | "fill_blank" | "true_false"; status: "draft" | "review_required" | "approved";
  parts: { id: string; kind: "stem" | "prompt" | "statement" | "caption" | "instruction" | "choice_table_header"; text: string; spoken_text: string; source: { page: number; bbox: number[] } }[];
  choices: { label: "A" | "B" | "C" | "D" | "E"; text: string; spoken_text: string }[];
  visuals: { id: string; kind: string; description: string | null; description_reviewed: boolean; caption: string | null; source: { page: number; bbox: number[] } }[];
};
export type QuestionBankUnit = { id: string; kind: string; label: string; spoken_text: string };
type AudioSegment = { id: string; spoken_text: string };

export function QuestionBankQuestion({ question, units, segments, api, onPrevious, onNext }: {
  question: QuestionBankQuestionData; units: QuestionBankUnit[]; segments: AudioSegment[]; api: string; onPrevious?: () => void; onNext?: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [audioStatus, setAudioStatus] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedUnit, setSelectedUnit] = useState<string | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);
  const serial = useRef(0);
  const cacheKey = (unitId: string) => `question:${question.id}:${unitId}:${[...units, ...segments].map(unit => unit.spoken_text).join("|")}`;
  const audioUrl = (unitId: string) => `${api}/v1/question-bank/student/questions/${encodeURIComponent(question.id)}/audio/${encodeURIComponent(unitId)}`;
  const stop = () => { serial.current += 1; player.current?.pause(); player.current = null; if (url.current) URL.revokeObjectURL(url.current); url.current = null; setIsPlaying(false); setAudioStatus(""); };
  useEffect(() => {
    if (question.status === "approved" && segments.length) void fetchAudio(cacheKey(segments[0].id), audioUrl(segments[0].id), { headers: { "X-Role": "student" } }).catch(() => undefined);
    return () => { serial.current += 1; player.current?.pause(); if (url.current) URL.revokeObjectURL(url.current); };
  // One approved question is mounted per component; prefetch its first short segment.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id, question.status]);
  const play = async (unitId: string) => {
    stop();
    const request = serial.current;
    setAudioStatus("Ses hazırlanıyor.");
    try {
      const data = await fetchAudio(cacheKey(unitId), audioUrl(unitId), { headers: { "X-Role": "student" } });
      if (request !== serial.current) return;
      const nextUrl = URL.createObjectURL(new Blob([data.slice(0)], { type: "audio/wav" }));
      url.current = nextUrl;
      const next = new Audio(nextUrl); player.current = next;
      next.onended = () => { if (request === serial.current) { setIsPlaying(false); setAudioStatus("Okuma tamamlandı. Tekrar dinlemek için aynı düğmeye basabilirsin."); } };
      await next.play();
      if (request === serial.current) { setIsPlaying(true); setAudioStatus("Seçili bölüm okunuyor."); }
    } catch { if (request === serial.current) setAudioStatus("Yerel ses kullanılamıyor. Metin ekran okuyucuya açıktır."); }
  };
  const playQuestion = async () => {
    if (!segments.length) { setAudioStatus("Okunacak soru metni bulunamadı."); return; }
    stop();
    const request = serial.current;
    setAudioStatus("Ses hazırlanıyor.");
    try {
      for (let index = 0; index < segments.length; index += 1) {
        const segment = segments[index];
        const data = await fetchAudio(cacheKey(segment.id), audioUrl(segment.id), { headers: { "X-Role": "student" } });
        if (request !== serial.current) return;
        const upcoming = segments[index + 1];
        if (upcoming) void fetchAudio(cacheKey(upcoming.id), audioUrl(upcoming.id), { headers: { "X-Role": "student" } }).catch(() => undefined);
        if (url.current) URL.revokeObjectURL(url.current);
        const nextUrl = URL.createObjectURL(new Blob([data.slice(0)], { type: "audio/wav" }));
        url.current = nextUrl;
        const next = new Audio(nextUrl);
        player.current = next;
        setAudioStatus(`Soru okunuyor (${index + 1}/${segments.length}).`);
        await new Promise<void>((resolve, reject) => {
          next.onended = () => resolve();
          next.onpause = () => resolve();
          next.onerror = () => reject(new Error("audio playback failed"));
          void next.play().then(() => { if (request === serial.current) setIsPlaying(true); }).catch(reject);
        });
        if (request !== serial.current) return;
        setIsPlaying(false);
      }
      setAudioStatus("Okuma tamamlandı. Tekrar dinleyebilirsin.");
    } catch { if (request === serial.current) { setIsPlaying(false); setAudioStatus("Yerel ses kullanılamıyor. Metin ekran okuyucuya açıktır."); } }
  };
  useEffect(() => {
    const listener = (event: Event) => {
      const id = (event as CustomEvent<{ id?: string }>).detail?.id;
      if (id && units.some(unit => unit.id === id)) { setSelectedUnit(id); void play(id); }
    };
    window.addEventListener(EXPLORE_READ_EVENT, listener);
    return () => window.removeEventListener(EXPLORE_READ_EVENT, listener);
  });
  if (question.status !== "approved") return <p role="status">Bu soru henüz kaynak denetiminden geçmedi.</p>;
  return <section className="question-bank-question focused-question" aria-labelledby={`${question.id}-heading`}>
    <div className="focused-question-top"><div><p className="eyebrow">ŞİMDİKİ SORU</p><h2 id={`${question.id}-heading`}>Soru {question.number}</h2></div><div className="focused-question-nav"><button type="button" className="quiet-button" onClick={onPrevious} disabled={!onPrevious}>← Önceki</button><button type="button" className="quiet-button" onClick={onNext} disabled={!onNext}>Sonraki →</button></div></div>
    <div className="question-content">{question.parts.map((part, index) => <p key={part.id} className={part.kind === "prompt" ? "question-prompt" : ""}>{question.parts.length > 1 && <span className="sr-only">{part.kind === "prompt" ? "Soru kökü: " : index === 0 ? "Soru metni: " : "Soru bölümü: "}</span>}{part.text}</p>)}
      {question.visuals.map(visual => <p className="question-visual" key={visual.id}><strong>Görsel:</strong> {visual.description_reviewed ? visual.description : "Doğrulanmış betimleme henüz yok."}</p>)}
    </div>
    {question.question_type === "multiple_choice" ? <fieldset className="focused-choices"><legend>Yanıt olarak hangi şıkkı düşünüyorsun?</legend>{question.choices.map(choice => <label key={choice.label} className="focused-choice"><input type="radio" name={`${question.id}-answer`} value={choice.label} checked={answer === choice.label} onChange={() => setAnswer(choice.label)} /><span className="choice-letter">{choice.label}</span><span>{choice.text}</span></label>)}</fieldset>
      : <label className="focused-written-answer">Yanıt taslağın<textarea value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Yanıtını burada düşünebilirsin." /></label>}
    <div className="focused-actions"><button type="button" onClick={() => void playQuestion()}>▶ Soruyu dinle</button><button type="button" className="quiet-button" onClick={() => setHelpOpen(value => !value)} aria-expanded={helpOpen}>{helpOpen ? "Konuşmayı gizle" : "Birlikte çöz"}</button>{isPlaying && <button type="button" className="quiet-button" onClick={stop}>Sesi durdur</button>}</div>
    <p role="status" className="focused-audio-status">{audioStatus}</p>
    <div hidden={!helpOpen}><QuestionTutor api={api} questionId={question.id} selectedChoice={answer} /></div>
    <details className="question-more"><summary>Ayrıntılı okuma ve notlar</summary>
      <p>Bir bölümü ayrı dinlemek veya gerekçeni yazmak istersen burayı kullan.</p>
      <ul className="question-detail-units">{units.map(unit => <li key={unit.id}><span>{unit.label}</span><button type="button" className="quiet-button" data-explore-read-id={unit.id} data-explore-summary={`${unit.label} bölümünü dinle`} aria-current={selectedUnit === unit.id ? "true" : undefined} onClick={() => { setSelectedUnit(unit.id); void play(unit.id); }}>Dinle</button></li>)}</ul>
      <label>Gerekçem<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Bu şıkkı neden seçtin?" /></label>
      <details><summary>Sesli komutlar</summary><VoiceCommandPanel title="Soruda sesli ilerle" examples={["soruyu oku", "şık A'yı oku", "sonraki soru"]}
        available={["read_selected", "stop_audio", "read_choice", ...(onPrevious ? ["previous_question" as const] : []), ...(onNext ? ["next_question" as const] : [])]}
        onCommand={command => {
          if (command.kind === "read_selected") { if (selectedUnit) void play(selectedUnit); else void playQuestion(); }
          else if (command.kind === "read_choice") void play(`${question.id}-choice-${command.label}`);
          else if (command.kind === "stop_audio") stop();
          else if (command.kind === "next_question") onNext?.();
          else if (command.kind === "previous_question") onPrevious?.();
        }} /></details>
    </details>
  </section>;
}
