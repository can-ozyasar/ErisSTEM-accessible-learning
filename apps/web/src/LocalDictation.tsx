import { useEffect, useRef, useState } from "react";

type Recognition = {
  lang: string; continuous: boolean; interimResults: boolean; processLocally?: boolean;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null;
  start: () => void; abort: () => void;
};
type RecognitionCtor = {
  new (): Recognition;
  available?: (options: { langs: string[]; processLocally: boolean; quality: "command" }) => Promise<string>;
};

/** Dictation is on-device only; text is a draft until the learner submits it. */
export function LocalDictation({ onText, disabled = false }: { onText: (value: string) => void; disabled?: boolean }) {
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const active = useRef(true);
  const recognition = useRef<Recognition | null>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; recognition.current?.abort(); }; }, []);

  async function start() {
    if (listening) { recognition.current?.abort(); return; }
    const browser = window as Window & { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
    const Ctor = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
    if (!Ctor?.available) { setStatus("Cihaz içi Türkçe konuşma tanıma desteklenmiyor; düşünceni yazabilirsin."); return; }
    try {
      const state = await Ctor.available({ langs: ["tr-TR"], processLocally: true, quality: "command" });
      if (!active.current) return;
      if (state !== "available") { setStatus("Cihaz içi Türkçe tanıma hazır değil; düşünceni yazabilirsin."); return; }
      const session = new Ctor();
      if (!("processLocally" in session)) { setStatus("Cihaz içi işlem doğrulanamadı; mikrofon açılmadı."); return; }
      session.lang = "tr-TR"; session.continuous = false; session.interimResults = false; session.processLocally = true;
      session.onresult = event => { if (active.current) { const text = event.results[0]?.[0]?.transcript?.trim(); if (text) onText(text.slice(0, 1000)); } };
      session.onerror = () => { if (active.current) setStatus("Ses algılanamadı; yeniden deneyebilir veya yazabilirsin."); };
      session.onend = () => { recognition.current = null; if (active.current) setListening(false); };
      recognition.current = session; session.start(); setListening(true);
      setStatus("Mikrofon açık. Düşüncen taslak olarak yazılacak; göndermek için düğmeyi kullan.");
    } catch { if (active.current) { setListening(false); setStatus("Mikrofon başlatılamadı; düşünceni yazabilirsin."); } }
  }
  return <><button type="button" disabled={disabled} onClick={() => void start()}>{listening ? "Dinlemeyi durdur" : "Düşüncemi konuşarak yaz"}</button>
    <p role="status">{status}</p></>;
}
