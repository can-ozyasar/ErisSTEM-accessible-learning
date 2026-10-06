import { useEffect, useRef, useState } from "react";
import type { ElementType } from "react";
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
  const approvePage = async () => { if (!documentId || !page || !window.confirm("Bu sayfadaki tüm metin blokları kaynakla karşılaştırıldı mı?")) return; const r = await fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/approve-text`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Öğretmen kaynak sayfayı bütün olarak karşılaştırdı." }) }); setMessage(r.ok ? "Sayfadaki metinler onaylandı; yayımlanmadı." : "Sayfa onayı tamamlanamadı."); if (r.ok) await load(); };
  const box = selected && pageSize ? { left: `${selected.source.bbox[0] / pageSize.width * 100}%`, top: `${selected.source.bbox[1] / pageSize.height * 100}%`, width: `${(selected.source.bbox[2] - selected.source.bbox[0]) / pageSize.width * 100}%`, height: `${(selected.source.bbox[3] - selected.source.bbox[1]) / pageSize.height * 100}%` } : undefined;
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Kaynak üzerinde öğretmen denetimi</h1><p>PDF’de turuncu çerçeveli alanı okuyun; metni onaylayın veya sade metin olarak düzeltin.</p></header><p role="status">{message}</p><label>Belge<select value={documentId} onChange={e => setDocumentId(e.target.value)}>{documents.map(d => <option key={d.id} value={d.id}>{d.title} · {d.review_required_count} bekleyen</option>)}</select></label><div className="review-layout"><aside><h2>Sayfalar</h2>{[...new Set(document?.blocks.map(b => b.source.page))].map(n => <button className={n === page ? "selected-page" : ""} onClick={() => { setPage(n); const b = document?.blocks.find(x => x.source.page === n); if (b) select(b); }} key={n}>Sayfa {n}</button>)}</aside><section className="page-canvas">{page && <div className="pdf-preview">{previewUrl ? <img alt={`Kaynak PDF sayfası ${page}`} src={previewUrl} /> : <p>Sayfa önizlemesi yükleniyor.</p>}{box && <span className="source-highlight" style={box} />}</div>}<button onClick={() => void approvePage()}>Bu sayfadaki metinleri onayla</button></section><section className="editor">{selected?.kind === "formula-display" ? <div className="edit-card"><h2>Matematiksel ifade</h2><p>Bu ifade özel matematik denetimi gerektirir; teknik LaTeX gösterilmez.</p></div> : selected && <div className="edit-card"><h2>Seçili metin</h2><label htmlFor="review-text">Öğrenciye gösterilecek metin</label><textarea id="review-text" value={draftText} onChange={e => setDraftText(e.target.value)} /><div><button onClick={() => void submit(false)}>Kaynakla aynı, onayla</button><button onClick={() => void submit(true)}>Düzelt ve onayla</button></div></div>}<h2>Sayfadaki bölümler</h2><div className="block-list">{blocks.map(b => <button className={b.id === selected?.id ? "selected-block" : ""} onClick={() => select(b)} key={b.id}><strong>{b.status === "review_required" ? "Denetle" : "Onaylı"}</strong> {b.kind === "formula-display" ? "Matematiksel ifade" : b.text}</button>)}</div></section></div></main>;
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
