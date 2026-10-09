import { useCallback, useEffect, useRef, useState } from "react";
import { turkishVoices } from "./speech_voices";

export function useLearningSpeech(rate: number) {
  const [status, setStatus] = useState("");
  const generation = useRef(0);
  const stop = useCallback(() => {
    generation.current += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setStatus("");
  }, []);
  useEffect(() => () => {
    generation.current += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);
  const speak = useCallback((value: string) => {
    stop();
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      setStatus("Seslendirme bulunamadı. Metni ekran okuyucunuzla inceleyebilirsiniz."); return;
    }
    const voice = turkishVoices(window.speechSynthesis.getVoices())[0];
    if (!voice) { setStatus("Yerel Türkçe ses bulunamadı. Metni ekran okuyucunuzla inceleyebilirsiniz."); return; }
    const current = generation.current;
    const utterance = new SpeechSynthesisUtterance(value);
    utterance.lang = "tr-TR"; utterance.voice = voice; utterance.rate = rate;
    utterance.onstart = () => { if (generation.current === current) setStatus("Seslendiriliyor."); };
    utterance.onend = () => { if (generation.current === current) setStatus("Seslendirme tamamlandı."); };
    utterance.onerror = () => { if (generation.current === current) setStatus("Seslendirme tamamlanamadı. Metni ekran okuyucunuzla inceleyebilirsiniz."); };
    window.speechSynthesis.speak(utterance);
  }, [rate, stop]);
  return { speak, stop, status };
}
