import { useEffect, useRef, useState } from "react";
import { useLearningSpeech } from "./useLearningSpeech";
import { fetchAudio } from "./audio_cache";

type Source = { page: number; section: string; excerpt: string };
type Reply = { reply: string; stage: string; sources: Source[] };
type Entry = { message: string; response: Reply; selectedChoice: string | null };
type Recognition = { lang: string; continuous: boolean; interimResults: boolean; processLocally?: boolean;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null; start: () => void; abort: () => void };
type RecognitionCtor = { new (): Recognition;
  available?: (settings: { langs: string[]; processLocally: boolean; quality: "command" }) => Promise<string>;
  install?: (settings: { langs: string[]; processLocally: boolean; quality: "command" }) => Promise<boolean> };

export function QuestionTutor({ api, questionId, selectedChoice }: { api: string; questionId: string; selectedChoice: string }) {
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [listening, setListening] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef<string | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const { speak, stop } = useLearningSpeech(1);
  useEffect(() => () => { recognition.current?.abort(); audio.current?.pause(); if (audioUrl.current) URL.revokeObjectURL(audioUrl.current); stop(); }, [stop]);
  const dictate = async () => {
    if (listening) { recognition.current?.abort(); return; }
    const browser = window as Window & { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
    const Ctor = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
    if (!Ctor?.available) { setNotice("Bu tarayıcı Türkçe cihaz içi konuşma tanımayı doğrulayamıyor. Metni yazabilirsin."); return; }
    const settings = { langs: ["tr-TR"], processLocally: true, quality: "command" as const };
    try {
      let state = await Ctor.available(settings);
      if (state === "downloadable" && Ctor.install) {
        setNotice("Türkçe cihaz içi dil paketi kuruluyor.");
        if (await Ctor.install(settings)) state = await Ctor.available(settings);
      }
      if (state !== "available") { setNotice("Türkçe cihaz içi tanıma hazır değil. Metni yazabilirsin."); return; }
      const session = new Ctor();
      if (!("processLocally" in session)) { setNotice("Cihaz içi tanıma doğrulanamadı. Metni yazabilirsin."); return; }
      session.lang = "tr-TR"; session.continuous = false; session.interimResults = false; session.processLocally = true;
      session.onresult = event => { const heard = event.results[0]?.[0]?.transcript?.trim(); if (heard) setMessage(heard.slice(0, 500)); };
      session.onerror = () => setNotice("Ses algılanamadı. Yeniden deneyebilir veya yazabilirsin.");
      session.onend = () => { setListening(false); recognition.current = null; };
      recognition.current = session; session.start(); setListening(true); setNotice("Mikrofon açık. Söylediğin metni göndermeden önce kontrol et.");
    } catch { setListening(false); setNotice("Mikrofon başlatılamadı. Metni yazabilirsin."); }
  };
  const ask = async (value: string) => {
    if (pending || entries.length >= 12) return;
    setPending(true); setNotice("Birlikte düşünme yanıtı hazırlanıyor.");
    const turn = { message: value, turns: entries.length, selected_choice: selectedChoice || null };
    try {
      const response = await fetch(`${api}/v1/question-bank/student/questions/${questionId}/tutor`, {
        method: "POST", headers: { "X-Role": "student", "Content-Type": "application/json" }, body: JSON.stringify(turn),
      });
      if (!response.ok) throw Error("Yardım hizmeti kullanılamıyor.");
      const result = await response.json() as Reply;
      setEntries(previous => [...previous, { message: value, response: result, selectedChoice: turn.selected_choice }]); setMessage(""); setNotice("");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Yanıt alınamadı."); }
    finally { setPending(false); }
  };
  const read = async (entry: Entry, turnNumber: number) => {
    audio.current?.pause(); stop(); if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    try {
      const data = await fetchAudio(`tutor:${questionId}:${entry.response.reply}`, `${api}/v1/question-bank/student/questions/${questionId}/tutor/audio`, {
        method: "POST", headers: { "X-Role": "student", "Content-Type": "application/json" },
        body: JSON.stringify({ message: entry.message, turns: turnNumber, selected_choice: entry.selectedChoice }),
      });
      const url = URL.createObjectURL(new Blob([data.slice(0)], { type: "audio/wav" })); audioUrl.current = url;
      audio.current = new Audio(url); await audio.current.play();
    } catch { speak(entry.response.reply); }
  };
  return <section className="question-phase" aria-labelledby="tutor-title">
    <p className="phase-number">İSTEĞE BAĞLI / BİRLİKTE ÇÖZ</p><h3 id="tutor-title">Soru üzerine konuşalım</h3>
    <p>Yardım istediğinde soruyu birlikte inceleriz. Kaynak bilgisini kullanırız; doğru şıkkı hemen söylemeyiz.</p>
    <>
      <ol className="tutor-dialogue" aria-live="polite">{entries.map((entry, index) => <li key={index}>
        <p><strong>Sen:</strong> {entry.message}</p><p><strong>Destekçi:</strong> {entry.response.reply}</p>
        {entry.response.sources.length > 0 && <details><summary>MEB kitap kanıtı</summary><ul>{entry.response.sources.map(source => <li key={`${source.page}-${source.excerpt}`}><strong>{source.section}, PDF s. {source.page}:</strong> {source.excerpt}</li>)}</ul></details>}
        <button type="button" className="quiet-button" onClick={() => void read(entry, index)}>Yanıtı dinle</button>
      </li>)}</ol>
      {entries.length < 12 && <form onSubmit={event => { event.preventDefault(); if (message.trim()) void ask(message.trim()); }}>
        <label>Ne düşünüyorsun?<textarea value={message} maxLength={500} onChange={event => setMessage(event.target.value)} placeholder="Örneğin: Soru hangi olayı soruyor? A şıkkındaki tarih doğru mu?" /></label>
        <button type="button" className="quiet-button" onClick={() => void dictate()}>{listening ? "Dinlemeyi durdur" : "Cihazda konuşarak yaz"}</button>
        <button type="submit" disabled={pending || !message.trim()}>Gönder</button>
        {entries.length === 0 && <button type="button" className="quiet-button" disabled={pending} onClick={() => void ask("Bu soruyu beraber nasıl çözebiliriz?")}>İlk ipucunu iste</button>}
      </form>}
      <p role="status">{notice || (entries.length >= 12 ? "Bu sorudaki konuşma sınırına ulaştın. Şimdi kendi yanıtını ve gerekçeni yazabilirsin." : "")}</p>
    </>
  </section>;
}
