import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { EXPLORE_ANNOUNCE_EVENT } from "./ExploreSpeech";

const AREAS = [
  { number: "01", label: "Konu anlatımı", title: "9. sınıf tarih kitabı", description: "Bir bölümü seç ve dinle.", action: "Kitabı aç", view: "history" as const },
  { number: "02", label: "Soru çalışması", title: "Tarih soru bankası", description: "Soruyu, görseli ve şıkları sırayla incele.", action: "Sorulara geç", view: "question-bank" as const },
  { number: "03", label: "Kişisel alan", title: "Braille ile yaz", description: "Kısa notunu taslakla.", action: "Yazmaya başla", view: "writing" as const },
] as const;

export function StudentLibrary({ onNavigate }: { onNavigate: (view: "history" | "question-bank" | "writing") => void }) {
  const [active, setActive] = useState(0);
  const startX = useRef<number | null>(null);
  const swiped = useRef(false);
  const move = (direction: -1 | 1) => {
    const next = Math.max(0, Math.min(AREAS.length - 1, active + direction));
    if (next === active) return;
    setActive(next);
    window.dispatchEvent(new CustomEvent(EXPLORE_ANNOUNCE_EVENT, { detail: { text: `${AREAS[next].title}. ${AREAS[next].description} Enter tuşuyla veya dokunarak aç. ${next + 1} / ${AREAS.length}.` } }));
  };
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => { startX.current = event.clientX; swiped.current = false; };
  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (startX.current === null) return;
    const distance = event.clientX - startX.current;
    startX.current = null;
    if (Math.abs(distance) < 42) return;
    swiped.current = true;
    move(distance < 0 ? 1 : -1);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); }
    if (event.key === "ArrowRight") { event.preventDefault(); move(1); }
  };
  return <main id="student-main" className="student-menu" aria-label="Öğrenci alanı">
    <div className="student-menu-viewport" role="region" aria-roledescription="kaydırmalı öğrenme menüsü" aria-label={`${AREAS[active].title}, ${active + 1} / ${AREAS.length}`} tabIndex={0}
      onPointerDown={onPointerDown} onPointerUp={onPointerUp} onPointerCancel={() => { startX.current = null; }} onKeyDown={onKeyDown}>
      <p className="sr-only" aria-live="polite">{AREAS[active].title} seçili. Kaydırarak, ok tuşlarıyla veya önceki ve sonraki düğmeleriyle alan değiştir. Enter tuşuyla aç.</p>
      <div className="student-menu-track" style={{ transform: `translateX(-${active * 100}%)` }}>
        {AREAS.map((area, index) => <article key={area.view} className={`student-menu-slide student-menu-${area.view}`} aria-hidden={active !== index}>
          <button type="button" tabIndex={active === index ? 0 : -1}
            data-explore-summary={`${area.title}. ${area.description}. Enter tuşuyla veya dokunarak aç.`}
            onClick={() => { if (!swiped.current) onNavigate(area.view); }}>
            <span className="entry-brand">Eriş<span>STEM</span></span>
            <span className="entry-number" aria-hidden="true">{area.number}</span>
            <span className="entry-role">{area.label}</span>
            <span role="heading" aria-level={1} tabIndex={-1}>{area.title}</span>
            <span className="entry-description">{area.description}</span>
            <span className="entry-action">{area.action} <span aria-hidden="true">→</span></span>
            <span className="entry-swipe-hint" aria-hidden="true">← Kaydır veya ok tuşlarını kullan →</span>
          </button>
        </article>)}
      </div>
    </div>
    <nav className="carousel-controls" aria-label="Öğrenme alanları arasında gezin"><button type="button" className="quiet-button" onClick={() => move(-1)} disabled={active === 0} aria-label="Önceki öğrenme alanı">← Önceki</button><span aria-live="off">{active + 1} / {AREAS.length}</span><button type="button" className="quiet-button" onClick={() => move(1)} disabled={active === AREAS.length - 1} aria-label="Sonraki öğrenme alanı">Sonraki →</button></nav>
  </main>;
}
