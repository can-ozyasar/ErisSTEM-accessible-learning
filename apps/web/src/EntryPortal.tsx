import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { EXPLORE_ANNOUNCE_EVENT, ExploreSpeech } from "./ExploreSpeech";

const AREAS = [
  { mode: "student", number: "01", label: "Öğrenci", title: "Öğrenci olarak devam et", description: "Kitabı aç, soru çöz, destek iste.", action: "Öğrenme alanına geç" },
  { mode: "teacher", number: "02", label: "Öğretmen", title: "Öğretmen alanına geç", description: "Soruları, cevap anahtarını ve MEB kaynaklarını denetle.", action: "Öğretmen alanını aç" },
] as const;

export function EntryPortal() {
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
  return <><ExploreSpeech routeKey="entry" /><main id="entry-main" className="entry-carousel" aria-label="Alan seçimi">
    <div className="entry-carousel-viewport" role="region" aria-roledescription="kaydırmalı alan seçici" aria-label={`${AREAS[active].label} alanı, ${active + 1} / ${AREAS.length}`} tabIndex={0}
      onPointerDown={onPointerDown} onPointerUp={onPointerUp} onPointerCancel={() => { startX.current = null; }} onKeyDown={onKeyDown}>
      <p className="sr-only" aria-live="polite">{AREAS[active].label} alanı seçili. Kaydırarak, ok tuşlarıyla veya önceki ve sonraki düğmeleriyle alan değiştir.</p>
      <div className="entry-carousel-track" style={{ transform: `translateX(-${active * 100}%)` }}>
        {AREAS.map((area, index) => <article key={area.mode} className={`entry-slide ${area.mode === "student" ? "entry-slide-student" : "entry-slide-teacher"}`} aria-hidden={active !== index}>
          <a href={`?mode=${area.mode}`} tabIndex={active === index ? 0 : -1}
            data-explore-summary={`${area.title}. ${area.description}. Enter tuşuyla veya dokunarak aç.`}
            onClick={event => { if (swiped.current) event.preventDefault(); }}>
            <span className="entry-brand">Eriş<span>STEM</span></span>
            <span className="entry-number" aria-hidden="true">{area.number}</span>
            <span className="entry-role">{area.label}</span>
            <h1>{area.title}</h1>
            <span className="entry-description">{area.description}</span>
            <span className="entry-action">{area.action} <span aria-hidden="true">→</span></span>
            <span className="entry-swipe-hint" aria-hidden="true">← Kaydır veya ok tuşlarını kullan →</span>
          </a>
        </article>)}
      </div>
    </div>
    <nav className="carousel-controls" aria-label="Alanlar arasında gezin"><button type="button" className="quiet-button" onClick={() => move(-1)} disabled={active === 0} aria-label="Önceki alan">← Önceki</button><span aria-live="off">{active + 1} / {AREAS.length}</span><button type="button" className="quiet-button" onClick={() => move(1)} disabled={active === AREAS.length - 1} aria-label="Sonraki alan">Sonraki →</button></nav>
  </main></>;
}

export function TeacherHome() {
  return <><header className="site-header"><div className="site-header-inner"><p className="brand">Eriş<span>STEM</span></p><p className="site-header-context">Öğretmen çalışma alanı</p></div></header>
    <main className="entry-shell"><p className="eyebrow">ÖĞRETMEN</p><h1>İçerik denetimi</h1>
      <p>Öğrenciye açılacak soruları ve MEB kitabındaki bilgi parçalarını buradan inceleyin.</p>
      <div className="entry-grid"><a className="entry-card entry-card-primary" href="?mode=question-bank-review"><strong>Soruları ve MEB kaynağını incele</strong><span>Soru metni, şıklar, cevap anahtarı ve kaynak bilgileri.</span><span className="entry-action">İncelemeye başla →</span></a></div>
      <details className="teacher-tools"><summary>Diğer öğretmen araçları</summary><nav className="teacher-home-links" aria-label="Diğer öğretmen araçları"><a href="?mode=learning-review">Öğrenme içeriği</a><a href="?mode=table-review">Tablolar</a><a href="?mode=reviewer">Yayın kontrolü</a><a href="?mode=benchmark">Ölçme ve anotasyon</a><a href="?mode=teacher-editor">Belge düzenleme</a></nav></details>
    </main></>;
}

export function PortalNav({ mode }: { mode: string }) {
  return <nav className="portal-nav" aria-label="Alan değiştir"><a href="/">Ana giriş</a><a aria-current={mode === "student" ? "page" : undefined} href="?mode=student">Öğrenci</a><a aria-current={mode === "teacher" || mode === "question-bank-review" ? "page" : undefined} href="?mode=teacher">Öğretmen</a></nav>;
}
