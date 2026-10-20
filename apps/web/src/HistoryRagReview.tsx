import { useEffect, useState } from "react";

type Section = { id: string; title: string; start: number; end: number };
type Chunk = { id: string; page: number; bbox: number[]; text: string; approved: boolean; revision: number };
type Summary = { candidate_count: number; approved_count: number; sections: Section[] };
const headers = { "X-Role": "teacher" };

function SourcePreview({ api, chunk }: { api: string; chunk: Chunk }) {
  const [open, setOpen] = useState(false);
  const [image, setImage] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    let url = "";
    void fetch(`${api}/v1/question-bank/teacher/rag/chunks/${chunk.id}/preview`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.blob(); })
      .then(blob => { if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setImage(url); } })
      .catch(() => { if (!controller.signal.aborted) setImage(""); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); setImage(""); };
  }, [api, chunk.id, open]);
  return <details onToggle={event => setOpen(event.currentTarget.open)}><summary>PDF kaynak bölgesini aç</summary>
    {image ? <img className="bank-source-image" src={image} alt={`MEB tarih kitabı ${chunk.page}. sayfadan kaynak kırpımı; metin yukarıda erişilebilir olarak yer alır.`} /> : <p>Kaynak görüntüsü yükleniyor.</p>}
  </details>;
}

export function HistoryRagReview({ api }: { api: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [section, setSection] = useState("");
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [checked, setChecked] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    void fetch(`${api}/v1/question-bank/teacher/rag/summary`, { headers })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<Summary>; })
      .then(value => { setSummary(value); setSection(value.sections[0]?.id ?? ""); })
      .catch(() => setMessage("MEB bilgi dizini hazır değil. Önce çevrimdışı hazırlama komutunu çalıştırın."));
  }, [api]);
  useEffect(() => {
    if (!section) return;
    const controller = new AbortController();
    void fetch(`${api}/v1/question-bank/teacher/rag/sections/${section}`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<Chunk[]>; })
      .then(value => { if (!controller.signal.aborted) setChunks(value); })
      .catch(() => { if (!controller.signal.aborted) setMessage("Konu parçaları yüklenemedi."); });
    return () => controller.abort();
  }, [api, section]);
  const setApproval = async (chunk: Chunk, approved: boolean) => {
    setMessage("Kaynak onayı kaydediliyor.");
    try {
      const response = await fetch(`${api}/v1/question-bank/teacher/rag/chunks/${chunk.id}`, {
        method: "PUT", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ approved, source_checked: approved, fact_only_checked: approved,
          reason: approved ? "PDF bölgesiyle karşılaştırıldı; yalnız ders bilgisi olduğu doğrulandı." : "Kaynak parçası yeniden inceleme için yayından kaldırıldı.", expected_revision: chunk.revision }),
      });
      if (!response.ok) throw Error("Onay kaydedilemedi; kaynağı yeniden yükleyin.");
      setChunks(previous => previous.map(item => item.id === chunk.id ? { ...item, approved, revision: item.revision + 1 } : item));
      setSummary(previous => previous ? { ...previous, approved_count: previous.approved_count + (approved ? 1 : -1) } : previous);
      setChecked(""); setMessage(approved ? "Bilgi parçası öğrenci yardımına açıldı." : "Bilgi parçası yardımdan kaldırıldı.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Onay başarısız."); }
  };
  return <section className="bank-page-approval" aria-labelledby="rag-review-title">
    <p className="eyebrow">MEB KAYNAK HAZIRLIĞI</p><h2 id="rag-review-title">Konu bazlı bilgi parçaları</h2>
    <p>Alıştırma ve görsel adayları ayıklandı. Her metni PDF sayfasıyla karşılaştırıp yalnız ders bilgisi içeriyorsa onaylayın. Onaylar kaynak sürümüne bağlıdır.</p>
    <p>{summary ? `${summary.approved_count} / ${summary.candidate_count} parça onaylı.` : "Dizin yükleniyor."}</p>
    <p role="status">{message}</p>
    {summary && <label>Konu<select value={section} onChange={event => { setSection(event.target.value); setChecked(""); }}>
      {summary.sections.map(item => <option key={item.id} value={item.id}>{item.id} {item.title} · s. {item.start}–{item.end}</option>)}
    </select></label>}
    <ol className="rag-review-list">{chunks.map(chunk => <li key={chunk.id}>
      <p><strong>PDF sayfası {chunk.page}</strong> · {chunk.approved ? "Onaylı" : "İnceleme bekliyor"}</p>
      <p>{chunk.text}</p>
      <SourcePreview api={api} chunk={chunk} />
      {!chunk.approved ? <><label><input type="checkbox" checked={checked === chunk.id} onChange={event => setChecked(event.target.checked ? chunk.id : "")} /> Metni ve ders bilgisi niteliğini kaynakta doğruladım.</label><button type="button" disabled={checked !== chunk.id} onClick={() => void setApproval(chunk, true)}>Bu parçayı onayla</button></>
        : <button type="button" className="quiet-button" onClick={() => void setApproval(chunk, false)}>Onayı geri al</button>}
    </li>)}</ol>
  </section>;
}
