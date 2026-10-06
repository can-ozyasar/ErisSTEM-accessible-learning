import { useEffect, useRef, useState } from "react";
import type { ElementType, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Block = { id: string; kind: "heading" | "paragraph" | "formula-display"; text?: string; latex?: string; mathml?: string; status: string; revision: number; source: { page: number; bbox: number[]; source_checksum: string; extraction_step: string }; validation: { confidence: number; reasons: string[] } };
type Document = { id: string; title: string; license_notice: string; blocks: Block[] };
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
  const main = useRef<HTMLElement>(null);
  useEffect(() => { fetch(`${API}/v1/student/documents/synthetic-geometry-01`, { headers: { "X-Role": "student" } }).then(r => r.json()).then(setContent).catch(() => setContent(null)); }, []);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if (event.altKey && event.key.toLowerCase() === "h") window.document.querySelector("h1,h2,h3")?.scrollIntoView(); if (event.altKey && event.key.toLowerCase() === "f") window.document.querySelector(".formula")?.scrollIntoView(); }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, []);
  if (!content) return <p role="status">İçerik yükleniyor. API çalışmıyorsa önce API'yi başlatın.</p>;
  return <><a className="skip" href="#lesson">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Öğrenci okuyucusu · <kbd>Alt</kbd>+<kbd>H</kbd> başlıklar · <kbd>Alt</kbd>+<kbd>F</kbd> formüller</p></header><main id="lesson" ref={main} tabIndex={-1}><article><h1>{content.title}</h1><p className="notice">{content.license_notice}</p>{content.blocks.map(block => block.kind === "heading" ? <h2 key={block.id}>{block.text}</h2> : block.kind === "paragraph" ? <p key={block.id}>{block.text}</p> : <Formula key={block.id} block={block} />)}</article></main></>;
}

type ReviewItem = { document_id: string; block: Block };

function TeacherReview() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [index, setIndex] = useState(0);
  const [latex, setLatex] = useState("a^2 + b^2 = c^2");
  const [message, setMessage] = useState("Düşük güvenli öğe aranıyor.");
  const load = async () => {
    try {
      const response = await fetch(`${API}/v1/teacher/review-queue`, { headers: { "X-Role": "teacher" } });
      if (!response.ok) throw new Error("queue");
      const next = await response.json() as ReviewItem[];
      setItems(next);
      setIndex(current => Math.min(current, Math.max(next.length - 1, 0)));
      if (next[0]?.block.latex) setLatex(next[0].block.latex);
      setMessage(next.length ? "Öğretmen denetimi gerekiyor." : "Kuyruk boş.");
    } catch {
      setMessage("Kuyruk yüklenemedi.");
    }
  };
  useEffect(() => {
    let active = true;
    void fetch(`${API}/v1/teacher/review-queue`, { headers: { "X-Role": "teacher" } })
      .then(response => {
        if (!response.ok) throw new Error("queue");
        return response.json() as Promise<ReviewItem[]>;
      })
      .then(next => {
        if (!active) return;
        setItems(next);
        if (next[0]?.block.latex) setLatex(next[0].block.latex);
        setMessage(next.length ? "Öğretmen denetimi gerekiyor." : "Kuyruk boş.");
      })
      .catch(() => { if (active) setMessage("Kuyruk yüklenemedi."); });
    return () => { active = false; };
  }, []);
  const current = items[index];
  const item = current?.block;
  const documentId = current?.document_id;
  const navigate = (direction: number) => {
    const nextIndex = Math.min(Math.max(index + direction, 0), items.length - 1);
    const next = items[nextIndex];
    setIndex(nextIndex);
    if (next?.block.latex) setLatex(next.block.latex);
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!item || !documentId) return;
    const result = await fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ latex, mathml: "<math><mi>a</mi><mo>+</mo><mi>b</mi><mo>=</mo><mi>c</mi></math>", reason: "Kaynak kutusu öğretmen tarafından kontrol edildi.", expected_revision: item.revision }) });
    if (!result.ok) { setMessage("Kaydetme başarısız; kuyruğu yenileyip tekrar deneyin."); return; }
    setMessage("Düzeltme taslakta onaylandı. Sıradaki öğe yüklendi; yayın için onaylayıcı gerekir.");
    await load();
  };
  const approve = async () => {
    if (!item || !documentId) return;
    const result = await fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${item.id}/approve`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Kaynak kutusuyla karşılaştırıldı.", expected_revision: item.revision }) });
    if (!result.ok) { setMessage("Onay başarısız; kuyruğu yenileyip tekrar deneyin."); return; }
    setMessage("Metin taslakta onaylandı. Sıradaki öğe yüklendi; yayın için onaylayıcı gerekir.");
    await load();
  };
  return <main className="teacher"><h1>Öğretmen denetimi</h1><p role="status">{message}</p>{item && <><nav className="review-navigation" aria-label="Denetim kuyruğu"><p>Öğe {index + 1} / {items.length} · Belge: {documentId}</p><button type="button" onClick={() => navigate(-1)} disabled={index === 0}>Önceki</button><button type="button" onClick={() => navigate(1)} disabled={index === items.length - 1}>Sonraki</button></nav><div className="review-grid"><section aria-labelledby="source-title"><h2 id="source-title">Kaynak kanıtı</h2><dl><dt>PDF sayfası</dt><dd>{item.source.page}</dd><dt>Kaynak kutusu</dt><dd>{item.source.bbox.join(", ")}</dd><dt>İşlem adımı</dt><dd>{item.source.extraction_step}</dd><dt>Güven</dt><dd>%{Math.round(item.validation.confidence * 100)}</dd></dl><p>{item.validation.reasons.join(" ")}</p></section>{item.kind === "formula-display" ? <form onSubmit={save} aria-labelledby="edit-title"><h2 id="edit-title">Erişilebilir formülü düzelt</h2><label htmlFor="latex">LaTeX</label><textarea id="latex" value={latex} onChange={event => setLatex(event.target.value)} required /><p>MathML, sunucuda şema kontrolünden geçer; ham HTML yayımlanmaz.</p><button type="submit">Düzeltmeyi kaydet</button></form> : <section aria-labelledby="approve-title"><h2 id="approve-title">Metin denetimi</h2><p>{item.text}</p><button type="button" onClick={approve}>Metni onayla</button></section>}</div></>}</main>;
}

type TeacherDocument = { id: string; title: string; published_revision: number; review_required_count: number };

function ReviewerPublish() {
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [message, setMessage] = useState("Yayınlanabilir belgeler yükleniyor.");
  const load = () => fetch(`${API}/v1/teacher/documents`, { headers: { "X-Role": "reviewer" } }).then(r => r.json()).then((items: TeacherDocument[]) => { setDocuments(items); setMessage(items.length ? "Belge seçin." : "Belge bulunamadı."); }).catch(() => setMessage("Belge listesi yüklenemedi."));
  useEffect(() => { load(); }, []);
  const publish = async (id: string) => { const result = await fetch(`${API}/v1/reviewer/documents/${id}/publish`, { method: "POST", headers: { "X-Role": "reviewer" } }); setMessage(result.ok ? "Belge yayımlandı." : "Yayın engellendi: denetim bekleyen içerikleri kontrol edin."); if (result.ok) load(); };
  return <main className="teacher"><h1>Onaylayıcı yayın paneli</h1><p role="status">{message}</p><ul>{documents.map(document => <li key={document.id}><h2>{document.title}</h2><p>Yayın sürümü: {document.published_revision}. Denetim bekleyen blok: {document.review_required_count}.</p><button type="button" disabled={document.review_required_count > 0} onClick={() => publish(document.id)}>Yayımla</button></li>)}</ul></main>;
}

const mode = new URLSearchParams(window.location.search).get("mode");
createRoot(document.getElementById("root")!).render(mode === "teacher" ? <TeacherReview /> : mode === "reviewer" ? <ReviewerPublish /> : <Reader />);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
