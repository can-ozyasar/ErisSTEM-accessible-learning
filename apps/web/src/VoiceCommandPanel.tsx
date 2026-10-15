import { useEffect, useRef, useState, type FormEvent } from "react";
import { parseVoiceCommand, type VoiceIntent, type VoiceKind } from "./voice_commands";

type RecognitionResultEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type RecognitionErrorEvent = { error: string };
type RecognitionInstance = {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  processLocally?: boolean;
  onstart: (() => void) | null; onend: (() => void) | null;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  start: () => void; abort: () => void;
};
type RecognitionCtor = {
  new (): RecognitionInstance;
  available?: (options: { langs: string[]; processLocally: boolean; quality: "command" }) => Promise<"available" | "downloadable" | "downloading" | "unavailable">;
  install?: (options: { langs: string[]; processLocally: boolean; quality: "command" }) => Promise<boolean>;
};

function recognitionConstructor(): RecognitionCtor | null {
  const browser = window as Window & { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return browser.SpeechRecognition ?? browser.webkitSpeechRecognition ?? null;
}

/** Push-to-talk only. Speech transcripts stay in this component; no app API call. */
export function VoiceCommandPanel({ title = "Sesli yönlendirme", examples, available, onCommand }: {
  title?: string; examples: string[]; available: VoiceKind[]; onCommand: (command: VoiceIntent) => void;
}) {
  const [text, setText] = useState("");
  const [heard, setHeard] = useState("");
  const [status, setStatus] = useState("Komut yazabilir veya mikrofonu tek seferlik açabilirsin.");
  const [listening, setListening] = useState(false);
  const [browserConsent, setBrowserConsent] = useState(false);
  const [packState, setPackState] = useState<"downloadable" | "downloading" | null>(null);
  const recognition = useRef<RecognitionInstance | null>(null);
  const pending = useRef<string | null>(null);
  const live = useRef(true);
  const handler = useRef(onCommand);
  const allowed = useRef(available);
  useEffect(() => { handler.current = onCommand; allowed.current = available; }, [onCommand, available]);
  useEffect(() => {
    live.current = true;
    return () => { live.current = false; pending.current = null; recognition.current?.abort(); recognition.current = null; };
  }, []);

  function route(transcript: string) {
    const command = parseVoiceCommand(transcript);
    setHeard(transcript);
    if (command?.kind === "help") { setStatus(`Örnek komutlar: ${examples.join(", ")}.`); return; }
    if (!command || !allowed.current.includes(command.kind)) {
      setStatus("Bu ekranda bu komutu güvenle eşleştiremedim. İşlem yapılmadı; aşağıdaki örneklerden birini dene."); return;
    }
    setStatus(`Komut anlaşıldı: ${transcript}.`);
    handler.current(command);
  }

  async function startListening() {
    if (listening) return;
    const Ctor = recognitionConstructor();
    if (!Ctor) { setStatus("Bu tarayıcı mikrofonla konuşma tanımayı desteklemiyor. Komutu yazabilir veya düğmeleri kullanabilirsin."); return; }
    if (!browserConsent) {
      if (!Ctor.available) { setStatus("Bu tarayıcı Türkçe cihaz içi tanımayı doğrulayamıyor. İstersen tarayıcı servisine açıkça izin ver veya komutu yaz."); return; }
      try {
        const state = await Ctor.available({ langs: ["tr-TR"], processLocally: true, quality: "command" });
        if (state !== "available") {
          setPackState(state === "downloadable" || state === "downloading" ? state : null);
          setStatus(state === "downloadable" ? "Türkçe cihaz içi dil paketi kurulabilir. Kurmak için aşağıdaki düğmeyi kullan." : state === "downloading" ? "Türkçe dil paketi indiriliyor; bitince yeniden dene." : "Bu tarayıcıda Türkçe cihaz içi tanıma hazır değil. Komutu yazabilir veya tarayıcı servisine ayrıca izin verebilirsin.");
          return;
        }
      } catch { setStatus("Cihaz içi tanıma denetimi başarısız. Mikrofon açılmadı; komutu yazabilirsin."); return; }
    }
    const session = new Ctor();
    if (!browserConsent && !("processLocally" in session)) { setStatus("Bu tarayıcı cihaz içi işlemeyi garanti etmiyor; mikrofon açılmadı."); return; }
    session.lang = "tr-TR"; session.continuous = false; session.interimResults = false; session.maxAlternatives = 1;
    if (!browserConsent) session.processLocally = true;
    pending.current = null;
    session.onstart = () => { if (live.current) { setListening(true); setStatus("Mikrofon açık. Tek bir kısa komut söyle."); } };
    session.onresult = event => { pending.current = event.results[0]?.[0]?.transcript?.trim() ?? null; };
    session.onerror = event => {
      pending.current = null;
      if (!live.current) return;
      const error = event.error;
      setStatus(error === "not-allowed" ? "Mikrofon izni verilmedi. Komutu yazabilir veya düğmeleri kullanabilirsin." : error === "no-speech" ? "Ses algılanmadı. Tekrar deneyebilir veya komutu yazabilirsin." : error === "language-not-supported" ? "Türkçe tanıma bu tarayıcıda hazır değil." : "Ses tanıma tamamlanamadı. Komutu yazmayı dene.");
    };
    session.onend = () => {
      recognition.current = null;
      if (!live.current) return;
      setListening(false);
      const transcript = pending.current;
      pending.current = null;
      if (transcript) route(transcript);
    };
    recognition.current = session;
    setStatus("Mikrofon başlatılıyor.");
    try { session.start(); } catch { recognition.current = null; setStatus("Mikrofon başlatılamadı. İzinleri denetle veya komutu yaz."); }
  }

  async function installLocalPack() {
    const Ctor = recognitionConstructor();
    if (!Ctor?.install) return;
    setStatus("Türkçe cihaz içi dil paketi kuruluyor. Bu işlem tarayıcı tarafından yapılır.");
    setPackState("downloading");
    try {
      const installed = await Ctor.install({ langs: ["tr-TR"], processLocally: true, quality: "command" });
      if (live.current) { setPackState(null); setStatus(installed ? "Türkçe dil paketi hazır. Şimdi Dinle düğmesini kullanabilirsin." : "Dil paketi kurulamadı. Komutu yazabilir veya tarayıcı servisini seçebilirsin."); }
    } catch { if (live.current) { setPackState(null); setStatus("Dil paketi kurulamadı. Komutu yazabilirsin."); } }
  }

  function submit(event: FormEvent) { event.preventDefault(); if (!text.trim()) return; route(text.trim()); setText(""); }
  const microphoneAvailable = Boolean(recognitionConstructor());
  return <section className="voice-panel" aria-label={title}>
    <div className="voice-panel-heading"><div><p className="eyebrow">İSTEĞE BAĞLI</p><h2>{title}</h2></div><span className={listening ? "voice-live" : "voice-idle"}>{listening ? "● Dinleniyor" : "Mikrofon kapalı"}</span></div>
    <p>Tek bir kısa komut söyle. Anlaşılmayan komut hiçbir işlemi başlatmaz; yanıt gönderme veya silme sesle yapılamaz.</p>
    <div className="voice-actions"><button type="button" onClick={() => listening ? (pending.current = null, recognition.current?.abort()) : void startListening()} disabled={!microphoneAvailable}>{listening ? "Dinlemeyi durdur" : "Bir komut dinle"}</button>{packState === "downloadable" && <button type="button" className="quiet-button" onClick={() => void installLocalPack()}>Türkçe yerel dil paketini kur</button>}</div>
    <p role="status" className="voice-status">{status}</p>{heard && <p className="voice-heard">Algılanan komut: <strong>{heard}</strong></p>}
    <form className="voice-text-command" onSubmit={submit}><label htmlFor="voice-command-text">Komutu yazarak dene</label><div><input id="voice-command-text" value={text} onChange={event => setText(event.target.value)} maxLength={90} placeholder={examples[0] ?? "Komut yaz"} /><button type="submit" disabled={!text.trim()}>Uygula</button></div></form>
    <details><summary>Örnek komutlar ve gizlilik</summary><ul>{examples.map(example => <li key={example}>“{example}”</li>)}</ul><p>Varsayılan mikrofon seçeneği yalnız cihaz içi Türkçe tanıma hazırsa çalışır. Ses ve komut metni uygulama sunucusuna kaydedilmez.</p><label className="voice-consent"><input type="checkbox" checked={browserConsent} onChange={event => { setBrowserConsent(event.target.checked); setPackState(null); }} /> Tarayıcının ses tanıma servisini kullanmayı kabul ediyorum. Ses, tarayıcı sağlayıcısının sunucusuna gönderilebilir.</label><p>Bu izni kapatırsan cihaz içi tanıma veya yazılı komut kullanılabilir.</p></details>
  </section>;
}
