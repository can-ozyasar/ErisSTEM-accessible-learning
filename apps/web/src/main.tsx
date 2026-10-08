import { useCallback, useEffect, useRef, useState } from "react";
import type { ElementType } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Block = { id: string; kind: "heading" | "paragraph" | "formula-display"; text?: string; latex?: string; mathml?: string; status: string; revision: number; source: { page: number; bbox: number[]; source_checksum: string; extraction_step: string }; validation: { confidence: number; reasons: string[] } };
type Document = { id: string; title: string; license_notice: string; blocks: Block[] };
type ReadingUnit = { id: string; kind: string; navigation_label: string; spoken_text: string; braille_available: boolean; reading_order: number };
type ReadingPlanResponse = { plan: { units: ReadingUnit[] }; unavailable_block_ids: string[] };
// Üretimde istekler aynı-origin nginx proxy'si üzerinden gider; uzak/IDE önizlemelerinde
// tarayıcının kendi localhost'una yanlışlıkla bağlanılmaz.
const API = import.meta.env.VITE_API_URL ?? "/api";
// React'in HTML tipleri MathML etiketini henüz tanımıyor; tarayıcıya gerçek MathML gönderilir.
const MathElement = "math" as unknown as ElementType;

function Formula({ block }: { block: Block }) {
  return <section className="formula" aria-labelledby={`${block.id}-label`} tabIndex={0}><h2 id={`${block.id}-label`}>Formül</h2><MathElement aria-label={`Formül: ${block.latex}`}>{block.latex}</MathElement><p className="sr-only">Ayrıntılı okunuş: a'nın karesi artı b'nin karesi eşittir c'nin karesi.</p><details><summary>Kaynak ve doğrulama bilgisi</summary><p>Sayfa {block.source.page}, kutu: {block.source.bbox.join(", ")}. Güven: %{Math.round(block.validation.confidence * 100)}.</p></details></section>;
}

function Reader() {
  const [content, setContent] = useState<Document | null>(null);
  const [plan, setPlan] = useState<ReadingPlanResponse | null>(null);
  const [currentUnit, setCurrentUnit] = useState(0);
  const [speechStatus, setSpeechStatus] = useState("Sesli okuma hazırlanıyor.");
  const main = useRef<HTMLElement>(null);
  const approvedAudio = useRef<HTMLAudioElement | null>(null);
  const approvedAudioUrl = useRef<string | null>(null);
  const speechAvailable = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  useEffect(() => {
    void Promise.all([
      fetch(`${API}/v1/student/documents/synthetic-geometry-01`, { headers: { "X-Role": "student" } }).then(r => r.ok ? r.json() as Promise<Document> : Promise.reject()),
      fetch(`${API}/v1/student/documents/synthetic-geometry-01/reading-plan`, { headers: { "X-Role": "student" } }).then(r => r.ok ? r.json() as Promise<ReadingPlanResponse> : Promise.reject()),
    ]).then(([document, readingPlan]) => { setContent(document); setPlan(readingPlan); setSpeechStatus("Doğrulanmış okuma planı hazır."); }).catch(() => { setContent(null); setSpeechStatus("Doğrulanmış okuma planı yüklenemedi."); });
    return () => { if (speechAvailable) window.speechSynthesis.cancel(); approvedAudio.current?.pause(); if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current); };
  }, [speechAvailable]);
  const stop = useCallback(() => {
    if (speechAvailable) window.speechSynthesis.cancel();
    approvedAudio.current?.pause();
    approvedAudio.current = null;
    if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current);
    approvedAudioUrl.current = null;
    setSpeechStatus("Sesli okuma durduruldu.");
  }, [speechAvailable]);
  const speak = useCallback(async (index = currentUnit) => {
    const unit = plan?.plan.units[index];
    if (!unit || !content) return;
    if (speechAvailable) window.speechSynthesis.cancel();
    approvedAudio.current?.pause();
    if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current);
    approvedAudio.current = null;
    approvedAudioUrl.current = null;
    try {
      const response = await fetch(`${API}/v1/student/documents/${encodeURIComponent(content.id)}/audio/${encodeURIComponent(unit.id)}`, { headers: { "X-Role": "student" } });
      if (response.ok) {
        const url = URL.createObjectURL(await response.blob());
        const audio = new Audio(url);
        approvedAudio.current = audio;
        approvedAudioUrl.current = url;
        audio.onplay = () => setSpeechStatus(`${unit.navigation_label} onaylı sesle okunuyor.`);
        audio.onended = () => { setSpeechStatus(`${unit.navigation_label} tamamlandı.`); URL.revokeObjectURL(url); if (approvedAudioUrl.current === url) approvedAudioUrl.current = null; };
        audio.onerror = () => setSpeechStatus("Onaylı ses dosyası oynatılamadı.");
        await audio.play();
        return;
      }
    } catch { /* A vetted server asset is optional; use the verified browser fallback below. */ }
    if (!speechAvailable) { setSpeechStatus("Bu birim için onaylı ses bulunamadı ve tarayıcı sesli okumayı desteklemiyor."); return; }
    const utterance = new SpeechSynthesisUtterance(unit.spoken_text);
    utterance.lang = "tr-TR";
    utterance.rate = 0.95;
    utterance.onstart = () => setSpeechStatus(`${unit.navigation_label} okunuyor.`);
    utterance.onend = () => setSpeechStatus(`${unit.navigation_label} tamamlandı.`);
    utterance.onerror = () => setSpeechStatus("Sesli okuma bu birimde tamamlanamadı.");
    window.speechSynthesis.speak(utterance);
  }, [content, currentUnit, plan, speechAvailable]);
  const moveUnit = useCallback((change: number) => { if (!plan) return; const next = Math.max(0, Math.min(plan.plan.units.length - 1, currentUnit + change)); setCurrentUnit(next); window.document.getElementById(plan.plan.units[next]?.id)?.focus(); }, [currentUnit, plan]);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if (event.altKey && event.key.toLowerCase() === "h") window.document.querySelector("h1,h2,h3")?.scrollIntoView(); if (event.altKey && event.key.toLowerCase() === "f") window.document.querySelector(".formula")?.scrollIntoView(); if (event.altKey && event.key === "ArrowRight") { event.preventDefault(); moveUnit(1); } if (event.altKey && event.key === "ArrowLeft") { event.preventDefault(); moveUnit(-1); } if (event.altKey && event.key.toLowerCase() === "r") { event.preventDefault(); void speak(); } }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, [moveUnit, speak]);
  if (!content) return <p role="status">İçerik yükleniyor. API çalışmıyorsa önce API'yi başlatın.</p>;
  const unit = plan?.plan.units[currentUnit];
  return <><a className="skip" href="#lesson">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Öğrenci okuyucusu · <kbd>Alt</kbd>+<kbd>H</kbd> başlıklar · <kbd>Alt</kbd>+<kbd>F</kbd> formüller · <kbd>Alt</kbd>+<kbd>R</kbd> oku</p></header><main id="lesson" ref={main} tabIndex={-1}><article><h1>{content.title}</h1><p className="notice">{content.license_notice}</p><section className="reader-controls" aria-labelledby="reader-controls-title"><h2 id="reader-controls-title">Doğrulanmış sesli okuma</h2><p role="status">{speechStatus}</p>{unit && <p>Seçili birim: {unit.navigation_label} · {currentUnit + 1}/{plan?.plan.units.length}</p>}<div><button type="button" onClick={() => moveUnit(-1)} disabled={!plan || currentUnit === 0}>Önceki birim</button><button type="button" onClick={() => void speak()} disabled={!unit}>Seçili birimi oku</button><button type="button" onClick={stop}>Durdur</button><button type="button" onClick={() => moveUnit(1)} disabled={!plan || currentUnit >= (plan.plan.units.length - 1)}>Sonraki birim</button></div>{plan?.unavailable_block_ids.length ? <p>Henüz sesli erişime açılmamış doğrulanmayı bekleyen matematiksel/görsel birimler vardır.</p> : null}</section>{content.blocks.map(block => block.kind === "heading" ? <h2 id={block.id} tabIndex={-1} key={block.id}>{block.text}</h2> : block.kind === "paragraph" ? <p id={block.id} tabIndex={-1} key={block.id}>{block.text}</p> : <Formula key={block.id} block={block} />)}</article></main></>;
}

function TeacherReview() {
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [document, setDocument] = useState<Document | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draftText, setDraftText] = useState("");
  const [message, setMessage] = useState("Belge yükleniyor.");
  useEffect(() => {
    void fetch(`${API}/v1/teacher/documents`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((items: TeacherDocument[]) => {
      const source = items.find(item => item.id.startsWith("source-")) ?? items[0]; setDocuments(items); if (source) setDocumentId(source.id);
    }).catch(() => setMessage("Belge listesi yüklenemedi."));
  }, []);
  const load = async (id = documentId) => { if (!id) return; const r = await fetch(`${API}/v1/teacher/documents/${id}`, { headers: { "X-Role": "teacher" } }); const next = await r.json() as Document; setDocument(next); const first = next.blocks.find(b => b.status === "review_required") ?? next.blocks[0]; setPage(first?.source.page ?? 0); setSelectedId(first?.id ?? ""); setDraftText(first?.text ?? ""); setMessage("Sayfadaki işaretli alanı kaynakla karşılaştırın."); };
  useEffect(() => {
    if (!documentId) return;
    void fetch(`${API}/v1/teacher/documents/${documentId}`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((next: Document) => {
      setDocument(next); const first = next.blocks.find(b => b.status === "review_required") ?? next.blocks[0]; setPage(first?.source.page ?? 0); setSelectedId(first?.id ?? ""); setDraftText(first?.text ?? ""); setMessage("Sayfadaki işaretli alanı kaynakla karşılaştırın.");
    }).catch(() => setMessage("Belge yüklenemedi."));
  }, [documentId]);
  useEffect(() => { if (documentId && page) void fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/preview-metadata`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then(setPageSize).catch(() => setPageSize(null)); }, [documentId, page]);
  useEffect(() => {
    if (!documentId || !page) return;
    let active = true;
    let objectUrl: string | null = null;
    void fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/preview`, { headers: { "X-Role": "teacher" } })
      .then(response => { if (!response.ok) throw new Error("preview"); return response.blob(); })
      .then(blob => { objectUrl = URL.createObjectURL(blob); if (active) setPreviewUrl(objectUrl); })
      .catch(() => { if (active) setPreviewUrl(null); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [documentId, page]);
  const blocks = document?.blocks.filter(b => b.source.page === page) ?? [];
  const selected = blocks.find(b => b.id === selectedId) ?? blocks[0];
  const select = (block: Block) => { setSelectedId(block.id); setDraftText(block.text ?? ""); };
  const submit = async (correct: boolean) => { if (!selected || !documentId) return; const url = correct ? `${API}/v1/teacher/documents/${documentId}/blocks/${selected.id}/text` : `${API}/v1/teacher/documents/${documentId}/blocks/${selected.id}/approve`; const body = correct ? { text: draftText, reason: "Öğretmen kaynak sayfayla karşılaştırarak metni düzeltti.", expected_revision: selected.revision } : { reason: "Öğretmen kaynak sayfayla karşılaştırdı.", expected_revision: selected.revision }; const r = await fetch(url, { method: correct ? "PUT" : "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify(body) }); setMessage(r.ok ? "Taslak güncellendi; yayımlanmadı." : "İşlem tamamlanamadı; sayfayı yenileyin."); if (r.ok) await load(); };
  const approvePage = async () => { if (!documentId || !page || !window.confirm("Bu sayfadaki tüm metin blokları kaynakla karşılaştırıldı mı?")) return; const r = await fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/approve-text`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Öğretmen kaynak sayfayı bütün olarak karşılaştırdı." }) }); setMessage(r.ok ? "Sayfadaki metinler onaylandı; yayımlanmadı." : "Bu sayfada güvenilir olmayan matematiksel metin var; yeniden yapılandırılmış çıkarım bekliyor."); if (r.ok) await load(); };
  const box = selected && pageSize ? { left: `${selected.source.bbox[0] / pageSize.width * 100}%`, top: `${selected.source.bbox[1] / pageSize.height * 100}%`, width: `${(selected.source.bbox[2] - selected.source.bbox[0]) / pageSize.width * 100}%`, height: `${(selected.source.bbox[3] - selected.source.bbox[1]) / pageSize.height * 100}%` } : undefined;
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Kaynak üzerinde öğretmen denetimi</h1><p>PDF’de turuncu çerçeveli alanı okuyun; metni onaylayın veya sade metin olarak düzeltin.</p></header><p role="status">{message}</p><label>Belge<select value={documentId} onChange={e => setDocumentId(e.target.value)}>{documents.map(d => <option key={d.id} value={d.id}>{d.title} · {d.review_required_count} bekleyen</option>)}</select></label><div className="review-layout"><aside><h2>Sayfalar</h2>{[...new Set(document?.blocks.map(b => b.source.page))].map(n => <button className={n === page ? "selected-page" : ""} onClick={() => { setPage(n); const b = document?.blocks.find(x => x.source.page === n); if (b) select(b); }} key={n}>Sayfa {n}</button>)}</aside><section className="page-canvas">{page && <div className="pdf-preview">{previewUrl ? <img alt={`Kaynak PDF sayfası ${page}`} src={previewUrl} /> : <p>Sayfa önizlemesi yükleniyor.</p>}{box && <span className="source-highlight" style={box} />}</div>}<button onClick={() => void approvePage()}>Bu sayfadaki metinleri onayla</button></section><section className="editor">{selected?.kind === "formula-display" ? <div className="edit-card"><h2>Matematiksel ifade</h2><p>Bu ifade özel matematik denetimi gerektirir; teknik LaTeX gösterilmez.</p></div> : selected && <div className="edit-card"><h2>Seçili metin</h2><label htmlFor="review-text">Öğrenciye gösterilecek metin</label><textarea id="review-text" value={draftText} onChange={e => setDraftText(e.target.value)} /><div><button onClick={() => void submit(false)}>Kaynakla aynı, onayla</button><button onClick={() => void submit(true)}>Düzelt ve onayla</button></div></div>}<h2>Sayfadaki bölümler</h2><div className="block-list">{blocks.map(b => <button className={b.id === selected?.id ? "selected-block" : ""} onClick={() => select(b)} key={b.id}>{b.kind === "formula-display" ? "Matematiksel ifade" : b.text}</button>)}</div></section></div></main>;
}

type TeacherDocument = { id: string; title: string; published_revision: number; review_required_count: number };
type GoldItem = { id: string; page: number; kind: string; expected: string };
type TableCell = { row: number; column: number; role: "header" | "data" | "unknown"; text: string };
type TableReview = { id: string; document_id: string; source: { page: number; bbox: number[] }; cells: TableCell[]; status: string; revision: number };
type SymbolEntry = { symbol: string; label: string; category: string; keywords: string };
const TABLE_SYMBOLS: SymbolEntry[] = [
  { symbol: "∈", label: "elemanıdır", category: "Kümeler", keywords: "eleman üye membership" }, { symbol: "∉", label: "elemanı değildir", category: "Kümeler", keywords: "değil üye membership" }, { symbol: "∅", label: "boş küme", category: "Kümeler", keywords: "empty" }, { symbol: "∪", label: "birleşim", category: "Kümeler", keywords: "union" }, { symbol: "∩", label: "kesişim", category: "Kümeler", keywords: "intersection" }, { symbol: "⊂", label: "alt küme", category: "Kümeler", keywords: "subset" }, { symbol: "⊆", label: "alt küme veya eşit", category: "Kümeler", keywords: "subset eşit" }, { symbol: "⊃", label: "üst küme", category: "Kümeler", keywords: "superset" }, { symbol: "⊇", label: "üst küme veya eşit", category: "Kümeler", keywords: "superset eşit" }, { symbol: "\\", label: "küme farkı", category: "Kümeler", keywords: "fark difference" }, { symbol: "′", label: "tümleyen imi", category: "Kümeler", keywords: "tümleyen prime" },
  { symbol: "=", label: "eşittir", category: "İlişkiler", keywords: "eşit" }, { symbol: "≠", label: "eşit değildir", category: "İlişkiler", keywords: "değil" }, { symbol: "<", label: "küçüktür", category: "İlişkiler", keywords: "küçük" }, { symbol: ">", label: "büyüktür", category: "İlişkiler", keywords: "büyük" }, { symbol: "≤", label: "küçük veya eşit", category: "İlişkiler", keywords: "küçük eşit" }, { symbol: "≥", label: "büyük veya eşit", category: "İlişkiler", keywords: "büyük eşit" }, { symbol: "≈", label: "yaklaşık eşittir", category: "İlişkiler", keywords: "yaklaşık" }, { symbol: "≡", label: "özdeş", category: "İlişkiler", keywords: "denk özdeş" }, { symbol: "∝", label: "orantılıdır", category: "İlişkiler", keywords: "orantı" },
  { symbol: "+", label: "artı", category: "İşlemler", keywords: "toplama" }, { symbol: "−", label: "eksi", category: "İşlemler", keywords: "çıkarma minus" }, { symbol: "×", label: "çarpı", category: "İşlemler", keywords: "çarpma" }, { symbol: "÷", label: "bölü", category: "İşlemler", keywords: "bölme" }, { symbol: "±", label: "artı eksi", category: "İşlemler", keywords: "plus minus" }, { symbol: "√", label: "karekök", category: "İşlemler", keywords: "kök root" }, { symbol: "∞", label: "sonsuz", category: "İşlemler", keywords: "infinity" }, { symbol: "·", label: "nokta çarpımı", category: "İşlemler", keywords: "çarpma nokta" }, { symbol: "%", label: "yüzde", category: "İşlemler", keywords: "percent" },
  { symbol: "∀", label: "her", category: "Mantık", keywords: "tüm her" }, { symbol: "∃", label: "vardır", category: "Mantık", keywords: "var exists" }, { symbol: "¬", label: "değil", category: "Mantık", keywords: "olumsuz" }, { symbol: "∧", label: "ve", category: "Mantık", keywords: "and" }, { symbol: "∨", label: "veya", category: "Mantık", keywords: "or" }, { symbol: "⇒", label: "ise", category: "Mantık", keywords: "implication" }, { symbol: "⇔", label: "ancak ve ancak", category: "Mantık", keywords: "eşdeğer" },
  { symbol: "α", label: "alfa", category: "Yunan harfleri", keywords: "alpha" }, { symbol: "β", label: "beta", category: "Yunan harfleri", keywords: "beta" }, { symbol: "γ", label: "gama", category: "Yunan harfleri", keywords: "gamma" }, { symbol: "δ", label: "delta", category: "Yunan harfleri", keywords: "delta" }, { symbol: "θ", label: "teta", category: "Yunan harfleri", keywords: "theta" }, { symbol: "λ", label: "lambda", category: "Yunan harfleri", keywords: "lambda" }, { symbol: "μ", label: "mü", category: "Yunan harfleri", keywords: "mu" }, { symbol: "π", label: "pi", category: "Yunan harfleri", keywords: "pi" }, { symbol: "σ", label: "sigma", category: "Yunan harfleri", keywords: "sigma toplam" },
  { symbol: "∠", label: "açı", category: "Geometri", keywords: "angle" }, { symbol: "°", label: "derece", category: "Geometri", keywords: "degree" }, { symbol: "⊥", label: "dik", category: "Geometri", keywords: "perpendicular" }, { symbol: "∥", label: "paralel", category: "Geometri", keywords: "parallel" }, { symbol: "△", label: "üçgen", category: "Geometri", keywords: "triangle" }, { symbol: "→", label: "ok", category: "Geometri", keywords: "vektör arrow" },
  { symbol: "²", label: "karesi", category: "Üs ve yapı", keywords: "üs kare" }, { symbol: "³", label: "küpü", category: "Üs ve yapı", keywords: "üs küp" }, { symbol: "ⁿ", label: "n üssü", category: "Üs ve yapı", keywords: "üs power" }, { symbol: "|", label: "mutlak değer", category: "Üs ve yapı", keywords: "absolute" }, { symbol: "{", label: "sol küme ayracı", category: "Üs ve yapı", keywords: "brace" }, { symbol: "}", label: "sağ küme ayracı", category: "Üs ve yapı", keywords: "brace" },
];

function TableReviewWorkspace() {
  const [items, setItems] = useState<TableReview[]>([]); const [selected, setSelected] = useState<TableReview | null>(null);
  const [cells, setCells] = useState<TableCell[]>([]); const [image, setImage] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null); const [message, setMessage] = useState("Belirsiz tablolar yükleniyor."); const [activeCell, setActiveCell] = useState<string | null>(null); const [symbolSearch, setSymbolSearch] = useState(""); const [symbolCategory, setSymbolCategory] = useState("Tümü"); const textareaRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const load = async () => { const response = await fetch(`${API}/v1/teacher/table-reviews`, { headers: { "X-Role": "teacher" } }); if (!response.ok) throw new Error("queue"); const next = await response.json() as TableReview[]; setItems(next); const current = next.find(item => item.id === selected?.id) ?? next[0] ?? null; setSelected(current); setCells(current?.cells ?? []); setMessage(current ? "Kaynakta turuncu çerçeveli tabloyu kontrol edin." : "Denetim bekleyen tablo yok."); };
  useEffect(() => { void fetch(`${API}/v1/teacher/table-reviews`, { headers: { "X-Role": "teacher" } }).then(response => { if (!response.ok) throw new Error("queue"); return response.json(); }).then((next: TableReview[]) => { setItems(next); const current = next[0] ?? null; setSelected(current); setCells(current?.cells ?? []); setMessage(current ? "Kaynakta turuncu çerçeveli tabloyu kontrol edin." : "Denetim bekleyen tablo yok."); }).catch(() => setMessage("Tablo denetim kuyruğu yüklenemedi.")); }, []);
  useEffect(() => { if (!selected) return; let url: string | null = null; void fetch(`${API}/v1/teacher/table-reviews/${selected.id}/preview`, { headers: { "X-Role": "teacher" } }).then(response => { if (!response.ok) throw new Error("preview"); const width = Number(response.headers.get("X-Pdf-Page-Width")); const height = Number(response.headers.get("X-Pdf-Page-Height")); if (width > 0 && height > 0) setPageSize({ width, height }); return response.blob(); }).then(blob => { url = URL.createObjectURL(blob); setImage(url); }).catch(() => { setImage(null); setPageSize(null); }); return () => { if (url) URL.revokeObjectURL(url); }; }, [selected]);
  const choose = (item: TableReview) => { setSelected(item); setCells(item.cells); setActiveCell(null); };
  const change = (row: number, column: number, text: string) => setCells(current => current.map(cell => cell.row === row && cell.column === column ? { ...cell, text } : cell));
  const insertSymbol = (symbol: string) => { if (!activeCell) return; const [row, column] = activeCell.split(":").map(Number); const cell = cells.find(value => value.row === row && value.column === column); const textarea = textareaRefs.current[activeCell]; if (!cell) return; const start = textarea?.selectionStart ?? cell.text.length; const end = textarea?.selectionEnd ?? start; const next = `${cell.text.slice(0, start)}${symbol}${cell.text.slice(end)}`; change(row, column, next); requestAnimationFrame(() => { textarea?.focus(); textarea?.setSelectionRange(start + symbol.length, start + symbol.length); }); };
  const clearActiveCell = () => { if (!activeCell) return; const [row, column] = activeCell.split(":").map(Number); change(row, column, ""); };
  const approve = async (corrected: boolean) => { if (!selected) return; const endpoint = corrected ? `${API}/v1/teacher/table-reviews/${selected.id}` : `${API}/v1/teacher/table-reviews/${selected.id}/approve`; const body = corrected ? { cells, reason: "Öğretmen kaynak PDF koordinatındaki tabloyla karşılaştırarak hücreleri düzeltti.", expected_revision: selected.revision } : { reason: "Öğretmen kaynak PDF koordinatındaki tabloyu doğruladı.", expected_revision: selected.revision }; const response = await fetch(endpoint, { method: corrected ? "PUT" : "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify(body) }); setMessage(response.ok ? "Tablo onaylandı; henüz öğrenciye yayımlanmadı." : "İşlem tamamlanamadı; tabloyu yeniden yükleyin."); if (response.ok) await load(); };
  const rows = [...new Set(cells.map(cell => cell.row))]; const columns = [...new Set(cells.map(cell => cell.column))];
  const symbolCategories = ["Tümü", ...new Set(TABLE_SYMBOLS.map(item => item.category))]; const matchingSymbols = TABLE_SYMBOLS.filter(item => (symbolCategory === "Tümü" || item.category === symbolCategory) && `${item.symbol} ${item.label} ${item.category} ${item.keywords}`.toLocaleLowerCase("tr-TR").includes(symbolSearch.toLocaleLowerCase("tr-TR")));
  const box = selected && pageSize ? { left: `${selected.source.bbox[0] / pageSize.width * 100}%`, top: `${selected.source.bbox[1] / pageSize.height * 100}%`, width: `${(selected.source.bbox[2] - selected.source.bbox[0]) / pageSize.width * 100}%`, height: `${(selected.source.bbox[3] - selected.source.bbox[1]) / pageSize.height * 100}%` } : undefined;
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Tablo denetimi</h1><p>Yalnız belirsiz vector/native tablo taslakları burada görünür. Teknik OCR, LaTeX ve model çıktısı gösterilmez.</p></header><p role="status">{message}</p><div className="review-layout"><aside><h2>Bekleyen tablolar</h2>{items.map(item => <button className={item.id === selected?.id ? "selected-page" : ""} onClick={() => choose(item)} key={item.id}>Sayfa {item.source.page} · tablo</button>)}</aside><section className="page-canvas"><div className="pdf-preview">{image ? <img alt={`Kaynak PDF sayfası ${selected?.source.page ?? ""}`} src={image} /> : <p>Kaynak sayfa önizlemesi yükleniyor.</p>}{box && <span className="source-highlight" style={box} />}</div></section><section className="editor">{selected && <><h2>Tablo hücreleri</h2><p className="source-note">Her hücreyi kaynakta turuncu çerçeveli alanla karşılaştırın. Hücreyi seçip sembol paletinden ekleyebilirsiniz; klavyede matematik işareti aramanız gerekmez.</p><fieldset className="symbol-palette"><legend>Matematik sembolleri</legend><label className="symbol-search">Sembol ara<input value={symbolSearch} onChange={event => setSymbolSearch(event.target.value)} placeholder="Örn. boş küme, teta, dik" /></label><label className="symbol-search">Kategori<select value={symbolCategory} onChange={event => setSymbolCategory(event.target.value)}>{symbolCategories.map(category => <option key={category}>{category}</option>)}</select></label><button type="button" disabled={!activeCell} onClick={clearActiveCell}>Seçili hücreyi temizle</button>{matchingSymbols.map(item => <button type="button" disabled={!activeCell} onClick={() => insertSymbol(item.symbol)} aria-label={`${item.label} (${item.category})`} title={`${item.category}: ${item.label}`} key={item.symbol}>{item.symbol}</button>)}{matchingSymbols.length === 0 && <p>Bu adla sembol bulunamadı; hücreye kopyala-yapıştır ile başka Unicode karakter de ekleyebilirsiniz.</p>}</fieldset><div className="table-editor" role="region" aria-label="Tablo hücre düzenleyicisi"><table><tbody>{rows.map(row => <tr key={row}>{columns.map(column => { const cell = cells.find(value => value.row === row && value.column === column); const Tag = cell?.role === "header" ? "th" : "td"; const key = `${row}:${column}`; return <Tag key={column}><label className="sr-only">Satır {row}, sütun {column}</label><textarea ref={element => { textareaRefs.current[key] = element; }} className={activeCell === key ? "active-table-cell" : ""} value={cell?.text ?? ""} onFocus={() => setActiveCell(key)} onChange={event => change(row, column, event.target.value)} /></Tag>; })}</tr>)}</tbody></table></div><div><button onClick={() => void approve(false)}>Kaynakla aynı, onayla</button><button onClick={() => void approve(true)}>Düzelt ve onayla</button></div></>}</section></div></main>;
}

function GoldAnnotationReview() {
  const [items, setItems] = useState<GoldItem[]>([]); const [selected, setSelected] = useState<GoldItem | null>(null); const [text, setText] = useState(""); const [image, setImage] = useState<string | null>(null); const [message, setMessage] = useState("Gold örnekleri yükleniyor.");
  useEffect(() => { void fetch(`${API}/v1/teacher/benchmark/gold-v1/items`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((next: GoldItem[]) => { setItems(next); setSelected(next[0] ?? null); setText(next[0]?.expected ?? ""); }).catch(() => setMessage("Gold kümesi yüklenemedi.")); }, []);
  useEffect(() => { if (!selected) return; let url: string | null = null; void fetch(`${API}/v1/teacher/benchmark/gold-v1/items/${selected.id}/preview`, { headers: { "X-Role": "teacher" } }).then(r => r.blob()).then(blob => { url = URL.createObjectURL(blob); setImage(url); }).catch(() => setImage(null)); return () => { if (url) URL.revokeObjectURL(url); }; }, [selected]);
  const choose = (item: GoldItem) => { setSelected(item); setText(item.expected); };
  const save = async () => { if (!selected) return; const r = await fetch(`${API}/v1/teacher/benchmark/gold-v1/items/${selected.id}`, { method: "PUT", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ expected: text }) }); setMessage(r.ok ? "Gold anotasyonu kaydedildi." : "Kaydetme başarısız."); };
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Gold benchmark anotasyonu</h1><p>Bu içerik öğrenciye yayımlanmaz. Yalnız çıkarıcıların doğruluğunu ölçmek için temsilî bölgeyi doğru ve sade biçimde tanımlayın.</p></header><p role="status">{message}</p><div className="review-layout"><aside><h2>Örnekler</h2>{items.map(item => <button className={item.id === selected?.id ? "selected-page" : ""} onClick={() => choose(item)} key={item.id}>{item.kind} · s. {item.page}</button>)}</aside><section className="page-canvas">{image ? <img alt={`Gold kaynak sayfası ${selected?.page}`} src={image} /> : <p>Sayfa yükleniyor.</p>}</section><section className="editor"><h2>{selected?.kind} · Sayfa {selected?.page}</h2><label htmlFor="gold-text">Doğru erişilebilir içerik</label><textarea id="gold-text" value={text} onChange={event => setText(event.target.value)} placeholder="Örneğin: sıfır virgül iki yüz on dokuz eksi sıfır virgül sıfır sıfır dokuz bölü iki virgül bir" /><button onClick={() => void save()}>Gold anotasyonunu kaydet</button></section></div></main>;
}

function ReviewerPublish() {
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [tables, setTables] = useState<TableReview[]>([]);
  const [message, setMessage] = useState("Yayınlanabilir içerikler yükleniyor.");
  const load = () => Promise.all([fetch(`${API}/v1/teacher/documents`, { headers: { "X-Role": "reviewer" } }).then(r => r.json()) as Promise<TeacherDocument[]>, fetch(`${API}/v1/reviewer/table-reviews`, { headers: { "X-Role": "reviewer" } }).then(r => r.json()) as Promise<TableReview[]>]).then(([nextDocuments, nextTables]) => { setDocuments(nextDocuments); setTables(nextTables); setMessage(nextDocuments.length || nextTables.length ? "Onaylı içeriği yayınlamak için seçin." : "Yayınlanabilir içerik yok."); }).catch(() => setMessage("Yayın listesi yüklenemedi."));
  useEffect(() => { load(); }, []);
  const publish = async (id: string) => { const result = await fetch(`${API}/v1/reviewer/documents/${id}/publish`, { method: "POST", headers: { "X-Role": "reviewer" } }); setMessage(result.ok ? "Belge yayımlandı." : "Yayın engellendi: denetim bekleyen içerikleri kontrol edin."); if (result.ok) load(); };
  const publishTable = async (id: string) => { const result = await fetch(`${API}/v1/reviewer/table-reviews/${id}/publish`, { method: "POST", headers: { "X-Role": "reviewer" } }); setMessage(result.ok ? "Tablo yayımlandı." : "Tablo yayımlanamadı; öğretmen onayı gerekli."); if (result.ok) load(); };
  return <main className="teacher"><h1>Onaylayıcı yayın paneli</h1><p role="status">{message}</p><h2>Belgeler</h2><ul>{documents.map(document => <li key={document.id}><h3>{document.title}</h3><p>Yayın sürümü: {document.published_revision}. Denetim bekleyen blok: {document.review_required_count}.</p><button type="button" disabled={document.review_required_count > 0} onClick={() => publish(document.id)}>Yayımla</button></li>)}</ul><h2>Öğretmen onaylı tablolar</h2><ul>{tables.map(table => <li key={table.id}><h3>Sayfa {table.source.page} · tablo</h3><p>{table.cells.length} hücre. Durum: {table.status === "published" ? "yayımlandı" : "öğretmen onaylı"}.</p><button type="button" disabled={table.status === "published"} onClick={() => publishTable(table.id)}>{table.status === "published" ? "Yayımlandı" : "Tabloyu yayımla"}</button></li>)}</ul></main>;
}

const mode = new URLSearchParams(window.location.search).get("mode");
createRoot(document.getElementById("root")!).render(mode === "teacher" ? <TeacherReview /> : mode === "table-review" ? <TableReviewWorkspace /> : mode === "benchmark" ? <GoldAnnotationReview /> : mode === "reviewer" ? <ReviewerPublish /> : <Reader />);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
