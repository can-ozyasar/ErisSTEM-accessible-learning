import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAudio } from "./audio_cache";

const API = import.meta.env.VITE_API_URL ?? "/api";
const MAX_CHUNK = 500;
type SpeechAsset = { urlPath: string; cacheKey: string };

function chunks(value: string): string[] {
  const words = value.replace(/\s+/g, " ").trim().split(" ");
  const result: string[] = [];
  let current = "";
  for (const word of words) {
    if (word.length > MAX_CHUNK) return [];
    if (current && `${current} ${word}`.length > MAX_CHUNK) {
      result.push(current);
      current = word;
    } else current = current ? `${current} ${word}` : word;
  }
  if (current) result.push(current);
  return result;
}

export function useLearningSpeech(rate: number) {
  const [status, setStatus] = useState("");
  const generation = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const cancel = useCallback(() => {
    generation.current += 1;
    request.current?.abort();
    request.current = null;
    audio.current?.pause();
    audio.current = null;
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = null;
  }, []);
  const stop = useCallback(() => { cancel(); setStatus(""); }, [cancel]);
  useEffect(() => () => cancel(), [cancel]);
  const speak = useCallback((value: string) => {
    cancel();
    const parts = chunks(value);
    if (!parts.length) { setStatus("Bu metin güvenli seslendirme sınırını aşıyor. Metni ekran okuyucunuzla inceleyebilirsiniz."); return; }
    const current = generation.current;
    const playPart = async (index: number): Promise<void> => {
      if (current !== generation.current || index >= parts.length) {
        if (current === generation.current) setStatus("Seslendirme tamamlandı.");
        return;
      }
      const controller = new AbortController();
      request.current = controller;
      try {
        const data = await fetchAudio(`interface:${parts[index]}`, `${API}/v1/student/interface-speech`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Role": "student" },
          body: JSON.stringify({ text: parts[index] }),
        });
        if (current !== generation.current) return;
        const nextUrl = URL.createObjectURL(new Blob([data.slice(0)], { type: "audio/wav" }));
        const nextAudio = new Audio(nextUrl);
        nextAudio.playbackRate = rate;
        url.current = nextUrl;
        audio.current = nextAudio;
        nextAudio.onended = () => {
          URL.revokeObjectURL(nextUrl);
          if (url.current === nextUrl) url.current = null;
          if (audio.current === nextAudio) audio.current = null;
          void playPart(index + 1);
        };
        nextAudio.onerror = () => { if (current === generation.current) setStatus("Ses oynatılamadı. Metni ekran okuyucunuzla inceleyebilirsiniz."); };
        setStatus("Yerel Türkçe sesle okunuyor.");
        await nextAudio.play();
      } catch {
        if (current === generation.current && !controller.signal.aborted)
          setStatus("Yerel ses hizmetine erişilemedi. Metni ekran okuyucunuzla inceleyebilirsiniz.");
      }
    };
    void playPart(0);
  }, [cancel, rate]);
  const speakUnits = useCallback((items: SpeechAsset[]) => {
    cancel();
    if (!items.length) { setStatus("Okunacak ses birimi bulunamadı."); return; }
    const current = generation.current;
    const playUnit = (index: number) => {
      if (current !== generation.current) return;
      if (index >= items.length) { setStatus("Seslendirme tamamlandı."); return; }
      const item = items[index];
      const controller = new AbortController();
      request.current = controller;
      void fetchAudio(item.cacheKey, item.urlPath, {
        headers: { "X-Role": "student" }, signal: controller.signal,
      }).then(data => {
        if (current !== generation.current) return;
        const nextUrl = URL.createObjectURL(new Blob([data.slice(0)], { type: "audio/wav" }));
        const nextAudio = new Audio(nextUrl);
        url.current = nextUrl; audio.current = nextAudio; nextAudio.playbackRate = rate;
        const release = () => {
          URL.revokeObjectURL(nextUrl);
          if (url.current === nextUrl) url.current = null;
          if (audio.current === nextAudio) audio.current = null;
        };
        nextAudio.onended = () => { release(); playUnit(index + 1); };
        nextAudio.onerror = () => {
          release();
          if (current === generation.current) setStatus("Ses oynatılamadı. Metni ekran okuyucunuzla inceleyebilirsiniz.");
        };
        setStatus("Yerel Türkçe sesle okunuyor; hazır kayıt yoksa Piper kullanılır.");
        void nextAudio.play().catch(() => {
          release();
          if (current === generation.current) setStatus("Ses oynatılamadı. Metni ekran okuyucunuzla inceleyebilirsiniz.");
        });
      }).catch(() => {
        if (current === generation.current && !controller.signal.aborted)
          setStatus("Yerel ses hizmetine erişilemedi. Metni ekran okuyucunuzla inceleyebilirsiniz.");
      });
    };
    playUnit(0);
  }, [cancel, rate]);
  const speakUnit = useCallback((urlPath: string, cacheKey: string) => {
    speakUnits([{ urlPath, cacheKey }]);
  }, [speakUnits]);
  return { speak, speakUnit, speakUnits, stop, status };
}
