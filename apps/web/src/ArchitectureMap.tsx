import { useEffect, useMemo, useState } from "react";

type Section = { id: string; title: string; start_page?: number; end_page?: number; candidate_atoms: number; approved_atoms?: number; pre_review: Record<string, number>; quality_warnings: Record<string, number> };
type Book = { grade?: number | null; source_name?: string; source_checksum: string; section_count: number; candidate_atoms: number; sections: Section[] };
type Manifest = {
  schema: string; source_checksum: string; source_policy_version: string; books: Book[];
  evidence_atoms: { candidate_count: number; approved_count: number; pending_count: number; excluded_by_type: Record<string, number> };
  knowledge_graph: { approved_question_graphs: number; approved_bundle_count: number; node_kinds: Record<string, number>; relation_kinds: Record<string, number>; temporal_precision: Record<string, number>; review_policy: string };
  retrieval: { active_method: string; hybrid_status: string; acceptance_thresholds: { recall_at_3_gain: number; mrr_at_3_gain: number; wrong_evidence_rate_increase: number; p95_ms_max: number }; hybrid_metrics?: Record<string, number>; hybrid_delta_vs_bm25?: Record<string, number> };
  stale_records: Record<string, number>; pipeline: string[]; privacy: Record<string, boolean>;
  ayt_pilot?: { corpus_checksum: string; books: Book[] };
};

const headers = { "X-Role": "teacher" };
const nodeLabels: Record<string, string> = { kisi: "Kişi", olay: "Olay", tarih_donem: "Tarih / dönem", yer: "Yer", kavram: "Kavram" };
const relationLabels: Record<string, string> = { gerceklesti_tarih: "Tarih ilişkisi", gerceklesti_yer: "Yer ilişkisi", once_geldi: "Önce gelir", sonra_geldi: "Sonra gelir", neden_oldu: "Neden", sonuc_oldu: "Sonuç", gerceklestirdi: "Kişi–olay", tanımlar: "Tanım", iliskilidir: "İlgili" };
const shortChecksum = (value: string) => value ? `${value.slice(0, 12)}…` : "Yok";
const items = (value: Record<string, number>, labels: Record<string, string> = {}) => Object.entries(value).map(([key, count]) => ({ label: labels[key] ?? key.replaceAll("_", " "), count }));

function Counts({ value, labels }: { value: Record<string, number>; labels?: Record<string, string> }) {
  const rows = items(value, labels);
  return rows.length ? <ul className="architecture-counts">{rows.map(row => <li key={row.label}><span>{row.label}</span><strong>{row.count}</strong></li>)}</ul> : <p className="architecture-empty">Henüz onaylı kayıt yok.</p>;
}

export function ArchitectureMap({ api }: { api: string }) {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [bookKey, setBookKey] = useState("");
  const [message, setMessage] = useState("Mimari harita yükleniyor.");
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${api}/v1/question-bank/teacher/architecture/manifest`, { headers, signal: controller.signal })
      .then(response => response.ok ? response.json() as Promise<Manifest> : Promise.reject(new Error("Mimari özeti yüklenemedi.")))
      .then(value => { if (!controller.signal.aborted) { setManifest(value); setBookKey(value.books[0]?.source_checksum ?? ""); setMessage("Mimari özeti güncel kaynak sürümünden hazırlandı."); } })
      .catch(error => { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Mimari özeti yüklenemedi."); });
    return () => controller.abort();
  }, [api]);
  const books = useMemo(() => manifest?.ayt_pilot?.books?.length ? manifest.ayt_pilot.books : manifest?.books ?? [], [manifest]);
  const selected = books.find(book => book.source_checksum === bookKey) ?? books[0];
  const stale = manifest ? Object.values(manifest.stale_records).reduce((sum, value) => sum + value, 0) : 0;
  return <main className="bank-review architecture-map" aria-labelledby="architecture-title">
    <p className="eyebrow">MİMARİ HARİTASI</p><h1 id="architecture-title">Kaynak bağlı tarih bilgi grafiği</h1>
    <p>Bu ekran yalnız yapı, sürüm ve kalite durumlarını gösterir. Kaynak metni, soru, cevap anahtarı ve öğrenci verisi burada yer almaz.</p>
    <p role="status">{message}</p>
    {!manifest ? null : <>
      <section className="review-stats" aria-label="Mimari özeti">
        <div><strong>{manifest.evidence_atoms.candidate_count}</strong><span>kanıt atomu adayı</span></div>
        <div><strong>{manifest.evidence_atoms.approved_count}</strong><span>onaylı kaynak atomu</span></div>
        <div><strong>{manifest.knowledge_graph.approved_question_graphs}</strong><span>onaylı soru grafiği</span></div>
        <div><strong>{manifest.knowledge_graph.approved_bundle_count}</strong><span>onaylı kanıt demeti</span></div>
      </section>
      <section className="architecture-panel" aria-labelledby="architecture-flow-title"><h2 id="architecture-flow-title">Sistemde bilgi nasıl ilerliyor?</h2>
        <ol className="architecture-flow">{manifest.pipeline.map((step, index) => <li key={step}><span aria-hidden="true">{index + 1}</span><strong>{step}</strong></li>)}</ol>
        <p className="notice">Başlık ağacı konu filtresi, bilgi grafiği ilişki denetimi, indeks ise aday getirme içindir. Bir katmanın puanı diğerinin kanıtı sayılmaz.</p>
      </section>
      <section className="architecture-grid">
        <article className="architecture-panel"><h2>Kaynak ve sürüm</h2><dl className="architecture-details"><dt>Etkin kaynak checksum’ı</dt><dd><code>{shortChecksum(manifest.source_checksum)}</code></dd><dt>Parça politikası</dt><dd>{manifest.source_policy_version}</dd><dt>Hibrit retrieval</dt><dd>{manifest.retrieval.hybrid_status === "accepted" ? "Kabul edildi" : manifest.retrieval.hybrid_status === "not_configured" ? "Henüz yapılandırılmadı; BM25 taban çizgisi etkin" : "Kabul edilmedi veya deney bekliyor"}</dd></dl>
          {stale > 0 ? <p className="review-warning">{stale} eski sürüme bağlı kayıt öğrenci akışında kullanılamaz; kaynak sürümüyle yeniden incelenmelidir.</p> : <p className="review-clear">Eski kaynak sürümüne bağlı etkin kayıt bulunmuyor.</p>}</article>
        <article className="architecture-panel"><h2>Arama kabul kapısı</h2><dl className="architecture-details"><dt>Recall@3 artışı</dt><dd>en az +{manifest.retrieval.acceptance_thresholds.recall_at_3_gain.toFixed(2)}</dd><dt>MRR@3 artışı</dt><dd>en az +{manifest.retrieval.acceptance_thresholds.mrr_at_3_gain.toFixed(2)}</dd><dt>p95 retrieval</dt><dd>en fazla {manifest.retrieval.acceptance_thresholds.p95_ms_max} ms</dd><dt>Yanlış kanıt oranı</dt><dd>artış kabul edilmez</dd></dl>
          {manifest.retrieval.hybrid_metrics && <Counts value={manifest.retrieval.hybrid_metrics} />}</article>
      </section>
      <section className="architecture-panel" aria-labelledby="architecture-books-title"><h2 id="architecture-books-title">Kitap ağacı ve kanıt atomları</h2>
        {books.length > 1 && <label>Kitap<select value={selected?.source_checksum ?? ""} onChange={event => setBookKey(event.target.value)}>{books.map(book => <option key={book.source_checksum} value={book.source_checksum}>{book.grade ? `${book.grade}. sınıf · ` : ""}{book.source_name ?? "Yerel kaynak"}</option>)}</select></label>}
        {selected && <><p><strong>{selected.grade ? `${selected.grade}. sınıf · ` : ""}{selected.source_name ?? "Yerel MEB tarih kitabı"}</strong> · {selected.section_count} bölüm · {selected.candidate_atoms} aday atom · checksum <code>{shortChecksum(selected.source_checksum)}</code></p>
          <div className="architecture-table-wrap"><table><caption>Başlık ağacı: her satır PDF bölümü içinde aday ve onay durumunu gösterir.</caption><thead><tr><th>Bölüm</th><th>Sayfalar</th><th>Aday</th><th>Onaylı</th><th>Ön inceleme</th><th>Kalite uyarısı</th></tr></thead><tbody>{selected.sections.map(section => <tr key={section.id}><th scope="row">{section.id} · {section.title}</th><td>{section.start_page ?? "–"}–{section.end_page ?? "–"}</td><td>{section.candidate_atoms}</td><td>{section.approved_atoms ?? "Pilot özeti"}</td><td><Counts value={section.pre_review} /></td><td><Counts value={section.quality_warnings} /></td></tr>)}</tbody></table></div></>}
      </section>
      <section className="architecture-grid">
        <article className="architecture-panel"><h2>Onaylı anlamsal grafik</h2><p>İlişki önerileri ancak PDF kesiti ve insan incelemesi sonrası grafiğe girer.</p><h3>Düğüm türleri</h3><Counts value={manifest.knowledge_graph.node_kinds} labels={nodeLabels} /><h3>İlişki türleri</h3><Counts value={manifest.knowledge_graph.relation_kinds} labels={relationLabels} /></article>
        <article className="architecture-panel"><h2>Zaman çizelgesi</h2><p>Tarihler normalleştirilmiş aralık olarak tutulur. Belirsiz tarih kesin yıl gibi kullanılmaz.</p><Counts value={manifest.knowledge_graph.temporal_precision} labels={{ year: "Tek yıl", range: "Aralık", century: "Yüzyıl", period: "Dönem", unknown: "Belirsiz" }} /><h3>Öğrenci güvenliği</h3><p>Alias ve anahtar kelimeler yalnız arama genişletir. İlişki iddiası için kaynak alıntısı ve onay gereklidir.</p></article>
      </section>
    </>}
  </main>;
}
