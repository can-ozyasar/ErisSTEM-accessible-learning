import { useEffect, useRef, useState } from "react";
import type { ElementType, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Block = { id: string; kind: "heading" | "paragraph" | "formula-display"; text?: string; latex?: string; mathml?: string; status: string; revision: number; source: { page: number; bbox: number[]; extraction_step: string }; validation: { confidence: number; reasons: string[] } };
type Document = { id: string; title: string; license_notice: string; blocks: Block[] };
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
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

function TeacherReview() {
  const [item, setItem] = useState<Block | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [latex, setLatex] = useState("a^2 + b^2 = c^2");
  const [message, setMessage] = useState("Düşük güvenli öğe aranıyor.");
  useEffect(() => { fetch(`${API}/v1/teacher/review-queue`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((items: { document_id: string; block: Block }[]) => { const next = items[0]; setItem(next?.block ?? null); setDocumentId(next?.document_id ?? null); if (next?.block.latex) setLatex(next.block.latex); setMessage(items.length ? "Öğretmen denetimi gerekiyor." : "Kuyruk boş."); }).catch(() => setMessage("Kuyruk yüklenemedi.")); }, []);
  const save = async (event: FormEvent) => { event.preventDefault(); if (!item || !documentId) return; const result = await fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ latex, mathml: "<math><mi>a</mi><mo>+</mo><mi>b</mi><mo>=</mo><mi>c</mi></math>", reason: "Kaynak kutusu öğretmen tarafından kontrol edildi.", expected_revision: item.revision }) }); if (!result.ok) { setMessage("Kaydetme başarısız; sayfayı yenileyip tekrar deneyin."); return; } setItem(await result.json()); setMessage("Düzeltme taslakta onaylandı. Yayın için onaylayıcı gerekir."); };
  const approve = async () => { if (!item || !documentId) return; const result = await fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${item.id}/approve`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Kaynak kutusuyla karşılaştırıldı.", expected_revision: item.revision }) }); setMessage(result.ok ? "Metin taslakta onaylandı. Yayın için onaylayıcı gerekir." : "Onay başarısız; sayfayı yenileyin."); if (result.ok) setItem(await result.json()); };
  return <main className="teacher"><h1>Öğretmen denetimi</h1><p role="status">{message}</p>{item && <div className="review-grid"><section aria-labelledby="source-title"><h2 id="source-title">Kaynak kanıtı</h2><p>Sayfa {item.source.page}; PDF kutusu: {item.source.bbox.join(", ")}</p><p>İşlem: {item.source.extraction_step}. Güven: %{Math.round(item.validation.confidence * 100)}.</p><p>{item.validation.reasons.join(" ")}</p></section>{item.kind === "formula-display" ? <form onSubmit={save} aria-labelledby="edit-title"><h2 id="edit-title">Erişilebilir formülü düzelt</h2><label htmlFor="latex">LaTeX</label><textarea id="latex" value={latex} onChange={event => setLatex(event.target.value)} required /><p>MathML, sunucuda şema kontrolünden geçer; ham HTML yayımlanmaz.</p><button type="submit">Düzeltmeyi kaydet</button></form> : <section aria-labelledby="approve-title"><h2 id="approve-title">Metin denetimi</h2><p>{item.text}</p><button type="button" onClick={approve}>Metni onayla</button></section>}</div>}</main>;
}

const teacherMode = new URLSearchParams(window.location.search).get("mode") === "teacher";
createRoot(document.getElementById("root")!).render(teacherMode ? <TeacherReview /> : <Reader />);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
