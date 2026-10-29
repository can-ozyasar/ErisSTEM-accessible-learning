import { useCallback, useEffect, useState } from "react";

type Score = { grade: number; score: number; question_count: number; components: { frequency: number; evidence: number; graph: number; accessibility: number } };
type UnitScore = { unit_id: string; score: number; question_count: number };
type Selection = { approved_tag_count: number; grade_ranking: Score[]; chosen_grade: number | null; unit_ranking: UnitScore[]; selected_units: string[]; ready: boolean };
type Draft = { exam_id: string; year: number; test: "TYT" | "AYT"; question_number: number; grade: number; unit_id: string; concept: string; relation_type: string; visual_dependency: boolean; direct_evidence: boolean; accessible: boolean };

const headers = { "X-Role": "teacher", "Content-Type": "application/json" };
const initial: Draft = { exam_id: "", year: 2026, test: "TYT", question_number: 1, grade: 9, unit_id: "", concept: "", relation_type: "kronoloji", visual_dependency: false, direct_evidence: true, accessible: true };

export function YksScopeReview({ api }: { api: string }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [message, setMessage] = useState("Resmî kitapçıktan doğrulanmış metadata bekleniyor.");
  const load = useCallback(async () => {
    const response = await fetch(`${api}/v1/question-bank/teacher/yks/selection`, { headers: { "X-Role": "teacher" } });
    if (!response.ok) throw Error("YKS kapsam raporu açılamadı.");
    setSelection(await response.json() as Selection);
  }, [api]);
  // Fetch completion, rather than the effect body, updates view state.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load().catch(error => setMessage(error instanceof Error ? error.message : "Rapor yüklenemedi.")); }, [load]);
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft(previous => ({ ...previous, [key]: value }));
  const save = async () => {
    const examId = draft.exam_id.trim();
    if (!examId || !draft.unit_id.trim() || !draft.concept.trim()) { setMessage("Soru kimliği, ünite ve ana kavram gerekli."); return; }
    setMessage("Yalnız metadata kaydediliyor.");
    const response = await fetch(`${api}/v1/question-bank/teacher/yks/tags/${encodeURIComponent(examId)}`, {
      method: "PUT", headers,
      body: JSON.stringify({ ...draft, exam_id: examId, unit_id: draft.unit_id.trim(), concept: draft.concept.trim(), reviewer: "Yerel öğretmen incelemesi", approved: true, expected_revision: 0 }),
    });
    const body = await response.json();
    if (!response.ok) { setMessage(body.detail ?? "Etiket kaydedilemedi."); return; }
    setMessage("Metadata kaydedildi. Soru metni, şıklar ve cevap anahtarı tutulmadı.");
    setDraft(initial); await load();
  };
  return <main className="bank-review" aria-labelledby="yks-scope-title">
    <p className="eyebrow">YKS KAPSAM SEÇİMİ</p><h1 id="yks-scope-title">Tek sınıf ve altı ünite seçimi</h1>
    <p className="notice">2022–2026 resmî TYT/AYT kitapçığını yerelde açın, her tarih sorusu için yalnız aşağıdaki metadata alanlarını girin. Soru metni, şıklar, cevap anahtarı ve PDF bu ekrana yazılmaz.</p>
    <p role="status">{message}</p>
    <section className="bank-page-approval" aria-labelledby="scope-report-title"><h2 id="scope-report-title">Mevcut seçim raporu</h2>
      <p>{selection?.approved_tag_count ?? 0} onaylı etiket var. {selection?.ready ? `Önerilen sınıf: ${selection.chosen_grade}. Sınıf.` : "Altı üniteyi karşılayacak veri henüz yok; seçim yapılmadı."}</p>
      {selection?.grade_ranking.length ? <table><caption>Sınıf puanları</caption><thead><tr><th>Sınıf</th><th>Puan</th><th>Soru</th><th>Sıklık</th><th>Kanıt</th><th>Grafik</th><th>Erişilebilirlik</th></tr></thead><tbody>{selection.grade_ranking.map(row => <tr key={row.grade}><td>{row.grade}. sınıf</td><td>{row.score.toFixed(2)}</td><td>{row.question_count}</td><td>{row.components.frequency.toFixed(2)}</td><td>{row.components.evidence.toFixed(2)}</td><td>{row.components.graph.toFixed(2)}</td><td>{row.components.accessibility.toFixed(2)}</td></tr>)}</tbody></table> : <p>Henüz raporlanacak etiket yok.</p>}
      {selection?.unit_ranking.length ? <ol><li><strong>Önerilen altı ünite:</strong> {selection.selected_units.join(", ") || "henüz yok"}</li>{selection.unit_ranking.map(unit => <li key={unit.unit_id}>{unit.unit_id}: {unit.score.toFixed(2)} puan, {unit.question_count} soru</li>)}</ol> : null}
    </section>
    <section className="bank-page-approval" aria-labelledby="scope-tag-title"><h2 id="scope-tag-title">Öğretmen metadata etiketi</h2><p>Etiketi, yerel resmî kitapçığı açık tutarak girin. “Doğrudan MEB kanıtı” yalnız ilgili sınıf kitabında açık bir kanıt bulduysanız işaretlenir.</p>
      <div className="scope-form"><label>Soru kimliği<input value={draft.exam_id} placeholder="tyt-2025-tarih-01" onChange={event => update("exam_id", event.target.value)} /></label><label>Yıl<select value={draft.year} onChange={event => update("year", Number(event.target.value))}>{[2022, 2023, 2024, 2025, 2026].map(year => <option key={year}>{year}</option>)}</select></label><label>Test<select value={draft.test} onChange={event => update("test", event.target.value as Draft["test"])}><option>TYT</option><option>AYT</option></select></label><label>Soru numarası<input type="number" min="1" max="80" value={draft.question_number} onChange={event => update("question_number", Number(event.target.value))} /></label><label>Sınıf<select value={draft.grade} onChange={event => update("grade", Number(event.target.value))}><option value={9}>9. sınıf</option><option value={10}>10. sınıf</option><option value={11}>11. sınıf</option></select></label><label>Ünite kimliği<input value={draft.unit_id} placeholder="10-1" onChange={event => update("unit_id", event.target.value)} /></label><label>Ana kavram<input value={draft.concept} placeholder="Örn. yerleşme" onChange={event => update("concept", event.target.value)} /></label><label>İlişki türü<select value={draft.relation_type} onChange={event => update("relation_type", event.target.value)}><option value="kisi_olay">Kişi–olay</option><option value="tarih_olay">Tarih–olay</option><option value="yer_olay">Yer–olay</option><option value="kronoloji">Kronoloji</option><option value="neden_sonuc">Neden–sonuç</option><option value="kaynak_yorumu">Kaynak yorumu</option></select></label></div>
      <fieldset><legend>Kaynak ve erişilebilirlik denetimi</legend><label className="bank-check"><input type="checkbox" checked={draft.direct_evidence} onChange={event => update("direct_evidence", event.target.checked)} /> MEB kitabında doğrudan ve kısa kanıt bulunabilir</label><label className="bank-check"><input type="checkbox" checked={draft.accessible} onChange={event => update("accessible", event.target.checked)} /> Soru erişilebilir metinle çözülebilir</label><label className="bank-check"><input type="checkbox" checked={draft.visual_dependency} onChange={event => update("visual_dependency", event.target.checked)} /> Görsel, harita veya tabloya bağımlı</label></fieldset>
      <button type="button" onClick={() => void save()}>Metadata etiketini kaydet</button>
    </section>
  </main>;
}
