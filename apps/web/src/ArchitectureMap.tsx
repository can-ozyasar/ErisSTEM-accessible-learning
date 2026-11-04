import { useEffect, useMemo, useState } from "react";

type Section = { id: string; title: string; start_page?: number; end_page?: number; candidate_atoms: number; approved_atoms?: number; pre_review: Record<string, number>; quality_warnings: Record<string, number> };
type Book = { grade?: number | null; source_name?: string; source_checksum: string; section_count: number; candidate_atoms: number; sections: Section[] };
type Manifest = {
  schema: string; source_checksum: string; source_policy_version: string; books: Book[];
  evidence_atoms: { candidate_count: number; approved_count: number; pending_count: number; excluded_by_type: Record<string, number> };
  knowledge_graph: { approved_question_graphs: number; approved_bundle_count: number; node_kinds: Record<string, number>; relation_kinds: Record<string, number>; temporal_precision: Record<string, number>; review_policy: string };
  retrieval: { active_method: string; hybrid_status: string; decision_policy: string; hybrid_metrics?: Record<string, number>; hybrid_delta_vs_bm25?: Record<string, number> };
  stale_records: Record<string, number>; pipeline: string[]; privacy: Record<string, boolean>;
  ayt_pilot?: { corpus_checksum: string; books: Book[] };
  experiments: {
    graph_prefill?: { question_count?: number; required_claim_count?: number; literal_claim_coverage?: number; edge_proposal_count?: number; reviewable_case_count?: number; insufficient_case_count?: number; relation_types?: Record<string, number>; unapproved_edge_count?: number } | null;
    external_evidence_evaluation?: { provider_model: string; evaluated_count: number; verdicts: Record<string, number>; latency_ms: { p50: number | null; p95: number | null; mean: number | null }; answer_key_accessed: boolean; is_teacher_approval: boolean; runtime_enabled: boolean; purpose: string } | null;
    source_relation_proposals?: { provider_model: string; source_count: number; proposed_relation_count: number; rejected_relation_count: number; invalid_json_retries: number; invalid_json_final_failures: number; relation_types: Record<string, number>; latency_ms: { p50: number | null; p95: number | null }; answer_key_accessed: boolean; question_text_accessed: boolean; is_teacher_approval: boolean; runtime_enabled: boolean } | null;
  };
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
        <article className="architecture-panel"><h2>Arama kabul kapısı</h2><p>Kaynak incelemesi tamamlanan aynı sorularda doğruluk, tam kanıt kapsamı ve süre karşılaştırılır. Yanlış kanıt artışı veya ölçülmemiş sonuç kabul edilmez. Yöntem değişikliğini öğretmen gerekçesiyle onaylar; sabit bir hız yüzdesi şartı yoktur.</p>
          {manifest.retrieval.hybrid_metrics && <Counts value={manifest.retrieval.hybrid_metrics} />}</article>
      </section>
      <section className="architecture-grid" aria-label="AYT pilot deneyleri">
        <article className="architecture-panel"><h2>Grafik ön doldurma deneyi</h2>
          {manifest.experiments.graph_prefill ? <><p>Bu ölçüm yalnız iki uçlu, metinde birebir görünen ilişkileri öneriye alır. Öğrenciye açık veya onaylı bir grafik üretmez.</p><dl className="architecture-details"><dt>İncelenen soru</dt><dd>{manifest.experiments.graph_prefill.question_count ?? 0}</dd><dt>Zorunlu iddia</dt><dd>{manifest.experiments.graph_prefill.required_claim_count ?? 0}</dd><dt>Birebir kanıt kapsamı</dt><dd>%{((manifest.experiments.graph_prefill.literal_claim_coverage ?? 0) * 100).toFixed(1)}</dd><dt>Önerilen kenar</dt><dd>{manifest.experiments.graph_prefill.edge_proposal_count ?? 0}</dd><dt>Onaysız kenar</dt><dd>{manifest.experiments.graph_prefill.unapproved_edge_count ?? 0}</dd></dl>{manifest.experiments.graph_prefill.edge_proposal_count === 0 && <p className="review-warning">Kapsam yeterli olmadığı için otomatik ilişki önerisi üretilmedi. Bu, eksik kanıtı görünür kılan güvenli sonuçtur.</p>}</> : <p className="architecture-empty">Pilot grafik ön doldurma ölçümü henüz yüklenmedi.</p>}
        </article>
        <article className="architecture-panel"><h2>Özel ikinci görüş deneyi</h2>
          {manifest.experiments.external_evidence_evaluation ? <><p>Harici değerlendirici yalnız PDF kesiti inceleme sırasını önceliklendirir. Kaynak onayı, retrieval, öğrenci yanıtı ve QLoRA için kullanılmaz.</p><dl className="architecture-details"><dt>İncelenen aday</dt><dd>{manifest.experiments.external_evidence_evaluation.evaluated_count}</dd><dt>Model</dt><dd>{manifest.experiments.external_evidence_evaluation.provider_model}</dd><dt>p50 / p95 süre</dt><dd>{manifest.experiments.external_evidence_evaluation.latency_ms.p50 ?? "–"} ms / {manifest.experiments.external_evidence_evaluation.latency_ms.p95 ?? "–"} ms</dd><dt>Cevap anahtarı erişimi</dt><dd>{manifest.experiments.external_evidence_evaluation.answer_key_accessed ? "Var" : "Yok"}</dd><dt>Öğretmen onayı</dt><dd>{manifest.experiments.external_evidence_evaluation.is_teacher_approval ? "Var" : "Yok"}</dd></dl><h3>Karar dağılımı</h3><Counts value={manifest.experiments.external_evidence_evaluation.verdicts} labels={{ direct: "Doğrudan", partial: "Kısmi", irrelevant: "İlgisiz", unreadable_or_visual: "Okunamaz / görsel" }} /><p className="review-warning">Bu deney canlı öğrenci akışında kapalıdır; her adayın PDF kesiti insan tarafından ayrıca incelenir.</p></> : <p className="architecture-empty">Harici değerlendirme deneyi henüz yüklenmedi.</p>}
        </article>
        <article className="architecture-panel"><h2>Kaynak içi ilişki pilotu</h2>
          {manifest.experiments.source_relation_proposals ? <><p>Bu pilot, seçilmiş MEB kesitlerinden yalnız metinde görünen iki uçlu ilişkileri önerir. İlişki türü ve kaynak fiili PDF kesitiyle doğrulanmadan grafiğe girmez.</p><dl className="architecture-details"><dt>İncelenen kesit</dt><dd>{manifest.experiments.source_relation_proposals.source_count}</dd><dt>Yerelde doğrulanan öneri</dt><dd>{manifest.experiments.source_relation_proposals.proposed_relation_count}</dd><dt>Yerelde reddedilen öneri</dt><dd>{manifest.experiments.source_relation_proposals.rejected_relation_count}</dd><dt>p50 / p95 süre</dt><dd>{manifest.experiments.source_relation_proposals.latency_ms.p50 ?? "–"} ms / {manifest.experiments.source_relation_proposals.latency_ms.p95 ?? "–"} ms</dd><dt>Soru / cevap anahtarı erişimi</dt><dd>{manifest.experiments.source_relation_proposals.question_text_accessed || manifest.experiments.source_relation_proposals.answer_key_accessed ? "Var" : "Yok"}</dd></dl><h3>Öneri türleri</h3><Counts value={manifest.experiments.source_relation_proposals.relation_types} labels={relationLabels} /><p className="review-warning">Bu ilişkiler yalnız private PDF kesiti inceleme paketindedir; öğrenci grafiği ve QLoRA için kapalıdır.</p></> : <p className="architecture-empty">Kaynak içi ilişki pilotu henüz yüklenmedi.</p>}
        </article>
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
