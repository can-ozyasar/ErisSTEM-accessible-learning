import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

const AREAS = [
  { number: "01", label: "Konu anlatımı", title: "9. sınıf tarih kitabı", description: "Bir bölümü seç ve dinle.", action: "Kitabı aç", view: "history" as const },
  { number: "02", label: "Soru çalışması", title: "Tarih soru bankası", description: "Soruyu, görseli ve şıkları sırayla incele.", action: "Sorulara geç", view: "question-bank" as const },
  { number: "03", label: "Kişisel alan", title: "Braille ile yaz", description: "Kısa notunu taslakla.", action: "Yazmaya başla", view: "writing" as const },
] as const;

export function StudentLibrary({ onNavigate }: { onNavigate: (view: "history" | "question-bank" | "writing") => void }) {
  const [active, setActive] = useState(0);
  const startX = useRef<number | null>(null);
  const swiped = useRef(false);
  const move = (direction: -1 | 1) => setActive(current => Math.max(0, Math.min(AREAS.length - 1, current + direction)));
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
      <p className="sr-only" aria-live="polite">{AREAS[active].title} seçili. Sağa veya sola kaydırarak alan değiştir. Açmak için iki kez dokun.</p>
      <div className="student-menu-track" style={{ transform: `translateX(-${active * 100}%)` }}>
        {AREAS.map((area, index) => <article key={area.view} className={`student-menu-slide student-menu-${area.view}`} aria-hidden={active !== index}>
          <button type="button" tabIndex={active === index ? 0 : -1}
            data-explore-summary={`${area.title}. ${area.description}. Açmak için iki kez dokun.`}
            data-explore-doubletap="true"
            onClick={() => { if (!swiped.current) onNavigate(area.view); }}>
            <span className="entry-brand">Eriş<span>STEM</span></span>
            <span className="entry-number" aria-hidden="true">{area.number}</span>
            <span className="entry-role">{area.label}</span>
            <h1>{area.title}</h1>
            <span className="entry-description">{area.description}</span>
            <span className="entry-action">{area.action} <span aria-hidden="true">→</span></span>
            <span className="entry-swipe-hint" aria-hidden="true">← Kaydırarak alan değiştir →</span>
          </button>
        </article>)}
      </div>
    </div>
  </main>;
}
