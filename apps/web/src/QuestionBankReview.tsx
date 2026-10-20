import { useCallback, useEffect, useState } from "react";
import { HistoryRagReview } from "./HistoryRagReview";

type Box = { page: number; bbox: number[]; source_checksum: string };
type Blank = { number: number; marker: string; source: Box; reviewed: boolean };
type Part = { id: string; kind: string; text: string; source: Box; blanks: Blank[] };
type Choice = { label: string; text: string; source: Box };
type Visual = { id: string; kind: string; label: string | null; source: Box; caption: string | null; description: string | null; description_reviewed: boolean };
type Question = { id: string; number: number; question_type: string; source: Box; parts: Part[]; choices: Choice[]; visuals: Visual[]; status: "draft" | "review_required" | "approved"; answer_label: string | null; answer_source_checked?: boolean };
type Item = { question: Question; issues: string[]; revision: number; review_reason: string | null; source_candidate?: Question | null };
type PageContext = { topic: string | null; test_name: string | null; test_number: number | null };
type Summary = { page_count: number; candidate_count: number; approved_count: number; quarantined_count: number; notice: string };
const headers = { "X-Role": "teacher" };

export function QuestionBankReview({ api }: { api: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [page, setPage] = useState(3);
  const [items, setItems] = useState<Item[]>([]);
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Question | null>(null);
  const [revision, setRevision] = useState(0);
  const [image, setImage] = useState("");
  const [pageImage, setPageImage] = useState("");
  const [sourceChecked, setSourceChecked] = useState(false);
  const [choicesChecked, setChoicesChecked] = useState(false);
  const [orderChecked, setOrderChecked] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [message, setMessage] = useState("Soru bankası yükleniyor.");
  const selected = items.find(item => item.question.id === selectedId);
  const selectItem = (item?: Item) => {
    if (item?.question.id === selectedId) return;
    if (item?.question.id !== selectedId && draftDirty && !window.confirm("Kaydedilmemiş düzeltmeler silinsin mi?")) return;
    setSelectedId(item?.question.id ?? "");
    setDraft(item ? structuredClone(item.question) : null);
    setRevision(item?.revision ?? 0);
    setImage("");
    setDraftDirty(false);
  };
  const loadPage = useCallback(async (number: number, preferredId?: string) => {
    const response = await fetch(`${api}/v1/question-bank/teacher/pages/${number}`, { headers });
    if (!response.ok) throw Error("Sayfa okunamadı");
    const result = await response.json() as { questions: Item[]; context: PageContext };
    setItems(result.questions);
    setPageContext(result.context);
    const next = result.questions.find(item => item.question.id === preferredId) ?? result.questions[0];
    setSelectedId(next?.question.id ?? "");
    setDraft(next ? structuredClone(next.question) : null);
    setRevision(next?.revision ?? 0);
    setImage("");
    setDraftDirty(false);
    setMessage(`${number}. sayfada ${result.questions.length} soru adayı bulundu.`);
  }, [api]);
  useEffect(() => {
    void fetch(`${api}/v1/question-bank/teacher/summary`, { headers })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<Summary>; })
      .then(setSummary).catch(() => setMessage("Soru bankası PDF'si veya inceleme hizmeti kullanılamıyor."));
  }, [api]);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${api}/v1/question-bank/teacher/pages/${page}`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<{ questions: Item[]; context: PageContext }>; })
      .then(result => { if (!controller.signal.aborted) {
        setItems(result.questions);
        setPageContext(result.context);
        const first = result.questions[0];
        setSelectedId(first?.question.id ?? "");
        setDraft(first ? structuredClone(first.question) : null);
        setRevision(first?.revision ?? 0);
        setMessage(`${page}. sayfada ${result.questions.length} soru adayı bulundu.`);
      } })
      .catch(() => { if (!controller.signal.aborted) setMessage("Sayfa yüklenemedi."); });
    return () => controller.abort();
  }, [api, page]);
  useEffect(() => {
    let url = "";
    const controller = new AbortController();
    void fetch(`${api}/v1/question-bank/teacher/pages/${page}/image`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.blob(); })
      .then(blob => { if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setPageImage(url); } })
      .catch(() => { if (!controller.signal.aborted) setPageImage(""); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [api, page]);
  useEffect(() => {
    if (!selectedId) return;
    let url = "";
    const controller = new AbortController();
    void fetch(`${api}/v1/question-bank/teacher/questions/${selectedId}/preview`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.blob(); })
      .then(blob => { if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setImage(url); } })
      .catch(() => { if (!controller.signal.aborted) setImage(""); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [api, selectedId]);
  const changePage = (number: number) => {
    if (number === page || (draftDirty && !window.confirm("Kaydedilmemiş düzeltmeler silinsin mi?"))) return;
    setDraftDirty(false);
    setPage(number); setItems([]); setPageContext(null); setSelectedId(""); setDraft(null); setRevision(0); setImage("");
    setSourceChecked(false); setChoicesChecked(false); setOrderChecked(false); setPageImage("");
  };
  const changePart = (id: string, value: string) => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, parts: previous.parts.map(part => part.id === id ? { ...part, text: value } : part) } : previous); };
  const changeChoice = (label: string, value: string) => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, choices: previous.choices.map(choice => choice.label === label ? { ...choice, text: value } : choice) } : previous); };
  const changeBlank = (id: string, number: number, reviewed: boolean) => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, parts: previous.parts.map(part => part.id === id ? { ...part, blanks: part.blanks.map(blank => blank.number === number ? { ...blank, reviewed } : blank) } : part) } : previous); };
  const rebuildBlanks = () => { setDraftDirty(true); setDraft(previous => {
    if (!previous) return previous;
    let nextNumber = 1;
    return { ...previous, parts: previous.parts.map(part => ({ ...part,
      blanks: [...part.text.matchAll(/-{4,}|_{3,}|\.{5,}/g)].map(match => ({
        number: nextNumber++, marker: match[0], source: part.source, reviewed: false,
      })),
    })) };
  }); };
  const changeVisual = (id: string, field: "description" | "kind" | "description_reviewed", value: string | boolean) => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, visuals: previous.visuals.map(visual => visual.id === id ? { ...visual, [field]: value } : visual) } : previous); };
  const restorePageFurniture = () => {
    const source = selected?.source_candidate;
    if (!source) return;
    setDraft(previous => previous ? { ...previous,
      parts: structuredClone(source.parts),
      choices: previous.choices.map(choice => /TARİH\s+SORU\s+BANKASI|9\.\s*SINIF|\b\d{1,2}\s*[-–]\s*[A-E]\b/i.test(choice.text)
        ? { ...choice, text: source.choices.find(item => item.label === choice.label)?.text ?? choice.text } : choice),
    } : previous);
    setDraftDirty(true);
    setMessage("Soru bölümleri kaynak PDF'den yeniden çıkarıldı; önceki bölüm düzeltmeleri yer değiştirmiş olabilir. PDF ile karşılaştırıp onaylayın.");
  };
  const save = async (approve: boolean) => {
    if (!draft) return;
    const question = { ...draft, status: approve ? "approved" : "review_required" };
    setMessage("Denetim kaydediliyor.");
    try {
      const response = await fetch(`${api}/v1/question-bank/teacher/questions/${draft.id}`, {
        method: "PUT", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ question, expected_revision: revision, reason: approve ? "Kaynak PDF ve erişilebilir okuma karşılaştırılarak onaylandı." : "Kaynakla karşılaştırma ve düzeltme sürüyor." }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw Error(typeof body?.detail === "string" ? body.detail : "Kaydedilemedi; alanları kontrol edin.");
      }
      const saved = await response.json() as { revision: number };
      setRevision(saved.revision);
      await loadPage(page, draft.id);
      setMessage(approve ? "Soru kaynakla karşılaştırılıp onaylandı." : "Taslak düzeltmesi kaydedildi.");
      void fetch(`${api}/v1/question-bank/teacher/summary`, { headers }).then(r => r.json() as Promise<Summary>).then(setSummary);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Kaydetme başarısız."); }
  };
  const clean = items.filter(item => !item.issues.length);
  const approveCleanPage = async () => {
    if (draftDirty) { setMessage("Önce açık sorudaki değişiklikleri kaydedin."); return; }
    setMessage("Sayfanın uyarısız soruları kaydediliyor.");
    try {
      const response = await fetch(`${api}/v1/question-bank/teacher/pages/${page}/approve-clean`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ question_ids: clean.map(item => item.question.id), source_checked: sourceChecked,
          choices_checked: choicesChecked, reading_order_checked: orderChecked,
          reason: "Tam PDF sayfası, soru şıkları ve erişilebilir okuma sırası karşılaştırıldı." }),
      });
      if (!response.ok) { const body = await response.json().catch(() => null); throw Error(typeof body?.detail === "string" ? body.detail : "Toplu onay yapılamadı."); }
      const result = await response.json() as { approved_count: number };
      await loadPage(page);
      const updated = await fetch(`${api}/v1/question-bank/teacher/summary`, { headers });
      if (updated.ok) setSummary(await updated.json() as Summary);
      setMessage(`${result.approved_count} uyarısız soru bu sayfadan onaylandı. Riskli sorular ayrı denetimde kaldı.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Toplu onay başarısız."); }
  };
  return <>
    <a className="skip" href="#bank-review">İçeriğe geç</a>
    <header><p className="brand">ErişSTEM · öğretmen denetimi</p></header>
    <main id="bank-review" className="bank-review">
      <p className="eyebrow">KAYNAK DENETİMİ</p><h1>Tarih soru bankası</h1>
      <p className="notice">{summary?.notice ?? "Kaynak kontrol ediliyor."} Öğrenci yalnız kaynağı doğrulanmış soruları görür.</p>
      <p role="status">{message}</p>
      {summary && <div className="review-stats" aria-label="Denetim özeti"><div><strong>{summary.page_count}</strong><span>PDF sayfası</span></div><div><strong>{summary.candidate_count}</strong><span>çıkarılmış soru adayı</span></div><div><strong>{summary.approved_count}</strong><span>öğrenciye açık soru</span></div>{summary.quarantined_count > 0 && <div><strong>{summary.quarantined_count}</strong><span>yeniden denetlenecek onaylı soru</span></div>}</div>}
      {pageContext && <p className="notice">Konu: {pageContext.topic ?? "Başlık doğrulanamadı"} · {pageContext.test_name ?? "Test türü doğrulanamadı"}{pageContext.test_number ? ` ${pageContext.test_number}` : ""}</p>}
      <nav className="history-navigation" aria-label="Soru bankası sayfaları">
        <button type="button" disabled={page <= 3} onClick={() => changePage(page - 1)}>Önceki sayfa</button>
        <label>PDF sayfası <input type="number" value={page} min={3} max={summary?.page_count ?? 58} onChange={event => { const value = Number(event.target.value); if (value >= 3 && value <= (summary?.page_count ?? 58)) changePage(value); }} /></label>
        <button type="button" disabled={page >= (summary?.page_count ?? 58)} onClick={() => changePage(page + 1)}>Sonraki sayfa</button>
      </nav>
      <div className="review-steps" aria-label="Denetim sırası"><span><b>1</b> Soruyu seç</span><span><b>2</b> Kaynakla karşılaştır</span><span><b>3</b> Düzelt ve onayla</span></div>
      <div className="bank-review-grid">
        <aside aria-labelledby="bank-list-title"><h2 id="bank-list-title">Sayfa {page} soruları</h2><ol>{items.map(item => <li key={item.question.id}><button type="button" className={selectedId === item.question.id ? "history-selected" : ""} aria-current={selectedId === item.question.id ? "true" : undefined} onClick={() => selectItem(item)}>Soru {item.question.number}<small>{item.question.status === "approved" ? "Onaylı" : item.issues.length ? `${item.issues.length} denetim uyarısı` : "Kaynak kontrolü bekliyor"}</small></button></li>)}</ol></aside>
        <section aria-labelledby="bank-source-title"><h2 id="bank-source-title">Kaynak PDF</h2><p className="source-note">Soru metnini ve şıkları bu görüntüyle karşılaştırın.</p>{image ? <><img className="bank-source-image" src={image} alt={`PDF sayfası ${page}, soru ${draft?.number} kaynak kırpımı`} /><details className="bank-zoom-details"><summary>Kaynağı büyüterek incele</summary><div className="bank-zoom"><img src={image} alt={`Büyütülmüş PDF kaynağı, soru ${draft?.number}`} /></div></details></> : <p>Kaynak görüntüsü yükleniyor.</p>}</section>
        <section className="bank-editor" aria-labelledby="bank-edit-title"><h2 id="bank-edit-title">{draft ? `Soru ${draft.number} · erişilebilir metin` : "Soru seçin"}</h2>{selected?.issues.length ? <p className="review-warning">Denetim uyarıları: {selected.issues.join(", ")}</p> : <p className="review-clear">Otomatik yapısal uyarı yok. Yine de her alanı kaynakla karşılaştırın.</p>}
          {draft && <><p className="source-note">Tür: {draft.question_type}. Şık sayısı: {draft.choices.length}.</p>
            {selected?.source_candidate && <button type="button" className="quiet-button" onClick={restorePageFurniture}>Soru bölümlerini temiz kaynak çıkarımıyla yenile</button>}
            <h3>Soru metni</h3>{draft.parts.map(part => <div key={part.id}><label>{part.kind}<textarea value={part.text} onChange={event => changePart(part.id, event.target.value)} /></label>{part.blanks.map(blank => <label key={blank.number} className="bank-check"><input type="checkbox" checked={blank.reviewed} onChange={event => changeBlank(part.id, blank.number, event.target.checked)} /> {blank.number}. boşluk işaretini doğruladım ({blank.marker})</label>)}</div>)}
            <button type="button" className="quiet-button" onClick={rebuildBlanks}>Boşlukları yeniden numaralandır</button>
            {draft.visuals.length > 0 && <h3>Görsel betimlemesi</h3>}{draft.visuals.map(visual => <fieldset key={visual.id}><legend>Görsel {visual.label ?? visual.id}</legend>{visual.description && !visual.description_reviewed && <p className="review-warning">Bu yalnız bir taslaktır; kaynak görüntüsüyle doğrulayın.</p>}<label>Tür<select value={visual.kind} onChange={event => changeVisual(visual.id, "kind", event.target.value)}><option value="unknown">Belirsiz</option><option value="photo">Fotoğraf</option><option value="map">Harita</option><option value="diagram">Şekil</option><option value="table">Tablo</option></select></label><label>Öğrenciye sunulacak betimleme<textarea value={visual.description ?? ""} onChange={event => changeVisual(visual.id, "description", event.target.value)} /></label><label className="bank-check"><input type="checkbox" checked={visual.description_reviewed} onChange={event => changeVisual(visual.id, "description_reviewed", event.target.checked)} /> Betimlemeyi kaynakla karşılaştırdım; cevabı ele vermiyor.</label></fieldset>)}
            {draft.choices.length > 0 && <h3>Şıklar</h3>}{draft.choices.map(choice => <label key={choice.label}>Şık {choice.label}<textarea value={choice.text} onChange={event => changeChoice(choice.label, event.target.value)} /></label>)}
            {draft.question_type === "multiple_choice" && <fieldset><legend>Cevap anahtarı · öğrenciye gösterilmez</legend><label>Kaynakta doğrulanmış şık<select value={draft.answer_label ?? ""} onChange={event => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, answer_label: event.target.value || null, answer_source_checked: false } : previous); }}><option value="">Henüz doğrulanmadı</option>{draft.choices.map(choice => <option key={choice.label} value={choice.label}>{choice.label}</option>)}</select></label><label className="bank-check"><input type="checkbox" disabled={!draft.answer_label} checked={Boolean(draft.answer_source_checked)} onChange={event => { setDraftDirty(true); setDraft(previous => previous ? { ...previous, answer_source_checked: event.target.checked } : previous); }} /> Cevabı ayrı cevap anahtarıyla karşılaştırdım.</label></fieldset>}
            <div className="student-actions"><button type="button" className="quiet-button" onClick={() => void save(false)}>Taslağı kaydet</button><button type="button" onClick={() => void save(true)}>Kaynakla karşılaştırdım, onayla</button></div></>}
        </section>
      </div>
      <section className="bank-page-approval" aria-labelledby="bank-batch-title"><p className="eyebrow">İSTEĞE BAĞLI · SAYFA DÜZEYİ</p><h2 id="bank-batch-title">Uyarısız soruları topluca onayla</h2><p>{clean.length} uyarısız soru toplu denetime uygun. Uyarılı sorular yalnız tek tek incelenir. Bu seçenek otomatik doğruluk garantisi değildir.</p><details><summary>Tam PDF sayfasını aç</summary>{pageImage ? <img className="bank-source-image" src={pageImage} alt={`Soru bankası PDF sayfası ${page}; sorular ayrıca metin olarak listelenir.`} /> : <p>Sayfa görüntüsü yükleniyor.</p>}</details><label><input type="checkbox" checked={sourceChecked} onChange={event => setSourceChecked(event.target.checked)} /> Bütün soru metinlerini PDF ile karşılaştırdım.</label><label><input type="checkbox" checked={choicesChecked} onChange={event => setChoicesChecked(event.target.checked)} /> Her sorunun A–E şıklarını karşılaştırdım.</label><label><input type="checkbox" checked={orderChecked} onChange={event => setOrderChecked(event.target.checked)} /> Soru, önerme ve şık okuma sırasını kontrol ettim.</label><button type="button" disabled={draftDirty || !clean.length || clean.some(item => item.revision > 0) || !sourceChecked || !choicesChecked || !orderChecked} onClick={() => void approveCleanPage()}>Doğruladığım {clean.length} soruyu onayla</button></section>
      <HistoryRagReview api={api} />
    </main>
  </>;
}
