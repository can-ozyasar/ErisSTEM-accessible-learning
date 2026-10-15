import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "/api";
const STORAGE_KEY = "eristem-explore-speech";
const TARGETS = "button, a, input, select, textarea, summary, [role='button'], [role='link'], [role='radio'], [role='checkbox'], [tabindex='0'], h1, h2, h3, h4, p, li, img, figcaption, label, legend, td, th";

function clean(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function byIds(ids: string): string {
  return clean(ids.split(/\s+/).map(id => document.getElementById(id)?.textContent ?? "").join(" "));
}

function nameOf(element: HTMLElement): string {
  const named = clean(element.getAttribute("aria-label")) || byIds(element.getAttribute("aria-labelledby") ?? "");
  if (named) return named;
  if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
    const label = clean([...element.labels ?? []].map(item => item.textContent).join(" "));
    return label || clean(element.getAttribute("placeholder")) || "Adsız giriş alanı";
  }
  if (element instanceof HTMLImageElement) return clean(element.alt) || "Açıklaması olmayan görsel";
  return clean(element.innerText || element.textContent) || clean(element.getAttribute("title"));
}

function descriptionOf(element: HTMLElement): string {
  const name = nameOf(element);
  if (!name) return "";
  const tag = element.tagName.toLowerCase();
  const role = element.getAttribute("role");
  let kind = "";
  if (tag === "button" || role === "button") kind = "düğme";
  else if (tag === "a" || role === "link") kind = "bağlantı";
  else if (tag === "input") {
    const input = element as HTMLInputElement;
    kind = input.type === "checkbox" ? "onay kutusu" : input.type === "radio" ? "seçenek" : input.type === "search" ? "arama alanı" : "giriş alanı";
  } else if (tag === "select") kind = "seçim alanı";
  else if (tag === "textarea") kind = "yazı alanı";
  else if (tag === "summary") kind = "açılır bölüm";
  else if (/^h[1-4]$/.test(tag)) kind = "başlık";
  else if (tag === "img") kind = "görsel";
  else if (tag === "p" || tag === "figcaption" || tag === "li") kind = "metin";
  else if (tag === "th") kind = "tablo başlığı";
  else if (tag === "td") kind = "tablo hücresi";
  if (!kind && !role) return "";
  const state = element instanceof HTMLInputElement && ["checkbox", "radio"].includes(element.type)
    ? element.checked ? ", seçili" : ", seçili değil" : element.getAttribute("aria-current") === "true" ? ", seçili" : "";
  const disabled = element.matches(":disabled, [aria-disabled='true']") ? ", kullanılamıyor" : "";
  const text = `${name}, ${kind || role}${state}${disabled}`;
  return text.length > 580 ? `${text.slice(0, 575).trimEnd()}…` : text;
}

function targetOf(value: EventTarget | null): HTMLElement | null {
  const start = value instanceof HTMLElement ? value : null;
  if (!start || start.closest("[aria-hidden='true'], [inert], .explore-control")) return null;
  const interactive = start.closest<HTMLElement>("button, a, input, select, textarea, summary, [role='button'], [role='link'], [role='radio'], [role='checkbox'], [tabindex='0']");
  const target = interactive ?? start.closest<HTMLElement>(TARGETS);
  if (!target || target.matches(":disabled") && !nameOf(target)) return null;
  return target;
}

/** UI exploration is deliberately separate from reading-plan playback and voice commands. */
export function ExploreSpeech({ routeKey }: { routeKey: string }) {
  const [enabled, setEnabled] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) !== "off"; } catch { return true; }
  });
  const [unlocked, setUnlocked] = useState(false);
  const [status, setStatus] = useState("Sesli keşif için bir kez Başlat düğmesine dokunun.");
  const timer = useRef<number | null>(null);
  const serial = useRef(0);
  const current = useRef<HTMLElement | null>(null);
  const context = useRef<AudioContext | null>(null);
  const source = useRef<AudioBufferSourceNode | null>(null);
  const controller = useRef<AbortController | null>(null);
  const touchedAt = useRef(0);
  const lastTap = useRef<{ target: HTMLElement; time: number } | null>(null);
  const touchSelected = useRef<HTMLElement | null>(null);
  const enabledRef = useRef(enabled);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);
  useEffect(() => () => { void context.current?.close(); }, []);

  useEffect(() => {
    const stop = () => {
      serial.current++;
      if (timer.current !== null) window.clearTimeout(timer.current);
      timer.current = null;
      controller.current?.abort(); controller.current = null;
      try { source.current?.stop(); } catch { /* already stopped */ }
      source.current = null;
    };
    const say = async (value: string) => {
      if (!enabledRef.current || !context.current || !value) return;
      stop();
      const token = serial.current;
      const request = new AbortController(); controller.current = request;
      try {
        const response = await fetch(`${API}/v1/student/interface-speech`, {
          method: "POST", headers: { "Content-Type": "application/json", "X-Role": "student" },
          body: JSON.stringify({ text: value }), signal: request.signal,
        });
        if (!response.ok) throw new Error("tts");
        const data = await response.arrayBuffer();
        if (token !== serial.current || !enabledRef.current) return;
        const buffer = await context.current.decodeAudioData(data);
        if (token !== serial.current || !enabledRef.current) return;
        const next = context.current.createBufferSource();
        next.buffer = buffer; next.connect(context.current.destination);
        source.current = next;
        next.start();
        setStatus(value);
      } catch {
        if (!request.signal.aborted && token === serial.current) setStatus("Ses başlatılamadı. Cihazın sesini kontrol edin veya ekran okuyucunuzu kullanın.");
      }
    };
    const announce = (target: HTMLElement | null, delay: number) => {
      if (!unlocked || !enabledRef.current || !target || target === current.current) return;
      current.current = target;
      if (timer.current !== null) window.clearTimeout(timer.current);
      const value = descriptionOf(target);
      if (value) timer.current = window.setTimeout(() => void say(value), delay);
    };
    const over = (event: PointerEvent) => { if (event.pointerType === "mouse" || event.pointerType === "pen") announce(targetOf(event.target), 230); };
    const focus = (event: FocusEvent) => announce(targetOf(event.target), 30);
    const touch = (event: TouchEvent) => {
      const point = event.touches[0];
      if (!point) return;
      touchedAt.current = Date.now();
      const target = targetOf(document.elementFromPoint(point.clientX, point.clientY));
      if (touchSelected.current !== target) {
        touchSelected.current?.classList.remove("explore-selected");
        touchSelected.current = target;
        target?.classList.add("explore-selected");
      }
      announce(target, 0);
    };
    const leave = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && current.current && !(event.relatedTarget instanceof Node && current.current.contains(event.relatedTarget))) current.current = null;
    };
    const click = (event: MouseEvent) => {
      if ((event.target as HTMLElement)?.closest(".explore-control")) { stop(); return; }
      if (!unlocked || !enabledRef.current || Date.now() - touchedAt.current > 800) return;
      const target = targetOf(event.target);
      if (!target?.matches("button, a, summary, [role='button'], [role='link']")) return;
      const previous = lastTap.current;
      if (previous?.target === target && Date.now() - previous.time < 4000) { lastTap.current = null; return; }
      event.preventDefault(); event.stopPropagation();
      lastTap.current = { target, time: Date.now() };
      setStatus("Öğe seçildi. Açmak için aynı öğeye tekrar dokunun.");
    };
    document.addEventListener("pointerover", over);
    document.addEventListener("focusin", focus);
    document.addEventListener("touchstart", touch, { passive: true });
    document.addEventListener("touchmove", touch, { passive: true });
    document.addEventListener("pointerout", leave);
    document.addEventListener("click", click, true);
    const heading = document.querySelector<HTMLElement>("main h1");
    if (unlocked && enabledRef.current && heading) timer.current = window.setTimeout(() => void say(`${nameOf(heading)}, ekran açıldı`), 450);
    return () => {
      document.removeEventListener("pointerover", over);
      document.removeEventListener("focusin", focus);
      document.removeEventListener("touchstart", touch);
      document.removeEventListener("touchmove", touch);
      document.removeEventListener("pointerout", leave);
      document.removeEventListener("click", click, true);
      touchSelected.current?.classList.remove("explore-selected");
      touchSelected.current = null; lastTap.current = null;
      stop(); current.current = null;
    };
  }, [routeKey, unlocked]);

  const start = () => {
    try {
      const audio = new AudioContext();
      context.current = audio;
      void audio.resume().then(() => {
        enabledRef.current = true;
        setEnabled(true); setUnlocked(true);
        setStatus("Sesli keşif açık. Öğelerin üzerine gelin, odaklanın veya dokunun.");
        try { localStorage.setItem(STORAGE_KEY, "on"); } catch { /* private mode */ }
      }).catch(() => { void audio.close(); setStatus("Ses başlatılamadı. Tarayıcının ses izinlerini kontrol edin."); });
    } catch { setStatus("Bu tarayıcı yerel ses çıkışını desteklemiyor."); }
  };

  const toggle = () => {
    const next = !enabled;
    enabledRef.current = next;
    setEnabled(next);
    try { localStorage.setItem(STORAGE_KEY, next ? "on" : "off"); } catch { /* private mode */ }
    if (!next) {
      serial.current++; controller.current?.abort();
      try { source.current?.stop(); } catch { /* already stopped */ }
      source.current = null;
      setStatus("Ekranı keşfetme sesi kapalı.");
    } else setStatus("Ekranı keşfetme sesi açık.");
  };
  return <aside className="explore-control" aria-label="Ekranı keşfetme sesi">
    <button type="button" aria-pressed={unlocked && enabled} onClick={unlocked ? toggle : start}>{!unlocked ? "🔊 Sesli keşfi başlat" : enabled ? "🔊 Keşif sesi açık" : "🔇 Keşif sesi kapalı"}</button>
    <span className="explore-status" aria-live="off">{status}</span>
  </aside>;
}
