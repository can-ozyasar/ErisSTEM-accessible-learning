import { useEffect, useState, type FormEvent } from "react";
import type { LearningModule } from "./learning_types";

type Quality = { status: string; content_checksum: string; revision: number; expert_approved: boolean; qualifying_pilots: number; pilot_count: number; blocking_pilots: number };
type ReviewModule = { id: string; title: string; version: string; quality: Quality; content: LearningModule;
  marking_keys: Record<string, { answer: string | number[]; hint?: string; hints?: string[] }>;
  review: { evidence_reference: string; decision: string; note: string } | null };
type Observation = { result: string; researcher_help_count: number; category: string | null; severity: string | null; note: string };
type Pilot = { id: string; revision: number; module_id: string; module_version: string; participant_code: string; state: string;
  kind: string; device: string; access_tool: string; observations: Record<string, Observation> };
type PilotTask = { id: string; title: string };
const CHECKS = { concept_correctness: "Kavram ve ilişkiler doğru", representation_limits: "Temsilin sınırları açık",
  answer_keys: "Soru ve cevap anahtarları doğru", hint_boundaries: "İpuçları ve yardımsız görevler ayrılmış", language_clarity: "Türkçe anlatım anlaşılır" };
const EMPTY_OBSERVATION: Observation = { result: "independent", researcher_help_count: 0, category: null, severity: null, note: "" };

export function LearningManagement({ api, panel }: { api: string; panel: "review" | "pilot" | "release" }) {
  const role = panel === "release" ? "reviewer" : "teacher";
  const [modules, setModules] = useState<ReviewModule[]>([]);
  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [tasks, setTasks] = useState<PilotTask[]>([]);
  const [moduleId, setModuleId] = useState("circle");
  const [pilotId, setPilotId] = useState("");
  const [taskId, setTaskId] = useState("open-topic");
  const [message, setMessage] = useState("Kayıtlar yükleniyor.");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [decision, setDecision] = useState("approve");
  const [expertise, setExpertise] = useState("special_education");
  const [evidence, setEvidence] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [kind, setKind] = useState("rehearsal");
  const [consent, setConsent] = useState(false);
  const [consentReference, setConsentReference] = useState("");
  const [device, setDevice] = useState("desktop");
  const [tool, setTool] = useState("nvda");
  const [observation, setObservation] = useState<Observation>(EMPTY_OBSERVATION);
  const selected = modules.find(item => item.id === moduleId);
  const pilot = pilots.find(item => item.id === pilotId);

  useEffect(() => {
    const controller = new AbortController();
    const headers = { "X-Role": role };
    void Promise.all([
      fetch(`${api}/v1/teacher/learning/modules`, { headers, signal: controller.signal }),
      fetch(`${api}/v1/teacher/learning/pilots`, { headers, signal: controller.signal }),
      fetch(`${api}/v1/teacher/learning/pilot-tasks`, { headers, signal: controller.signal }),
    ]).then(async responses => {
      if (responses.some(response => !response.ok)) throw new Error("Kayıtlar yüklenemedi.");
      const [nextModules, nextPilots, nextTasks] = await Promise.all(responses.map(response => response.json()));
      if (!controller.signal.aborted) { setModules(nextModules); setPilots(nextPilots); setTasks(nextTasks); setMessage("Kayıtlar güncel."); }
    }).catch(() => { if (!controller.signal.aborted) setMessage("Kayıtlar yüklenemedi. Yeniden yükleyin."); });
    return () => controller.abort();
  }, [api, role, reload]);

  async function mutate(path: string, method: string, body?: unknown): Promise<unknown> {
    const response = await fetch(`${api}${path}`, { method, headers: { "X-Role": role, "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(typeof data?.detail === "string" ? data.detail : "Kayıt reddedildi. Alanları ve güncel sürümü kontrol edin.");
    }
    return response.status === 204 ? null : response.json();
  }
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    try { await action(); setReload(value => value + 1); }
    catch (error) { setMessage(error instanceof Error ? error.message : "İşlem tamamlanamadı."); }
    finally { setBusy(false); }
  }
  async function review(event: FormEvent) {
    event.preventDefault(); if (!selected) return;
    await run(async () => {
      await mutate(`/v1/teacher/learning/modules/${moduleId}/review`, "POST", { revision: selected.quality.revision,
        content_checksum: selected.quality.content_checksum, decision, expertise, evidence_reference: evidence,
        checks: Object.fromEntries(Object.keys(CHECKS).map(key => [key, checks[key] === true])), note: reviewNote });
      setMessage("Uzman inceleme kaydı saklandı. Yayın için gerçek kullanıcı pilotu ve onaylayıcı kararı da gerekir.");
    });
  }
  async function createPilot(event: FormEvent) {
    event.preventDefault(); if (!selected) return;
    await run(async () => {
      const created = await mutate("/v1/teacher/learning/pilots", "POST", { module_id: moduleId, content_checksum: selected.quality.content_checksum,
        kind, adult_consent: consent, consent_reference: consentReference, device, access_tool: tool }) as Pilot;
      setPilotId(created.id); setTaskId("open-topic"); setObservation(EMPTY_OBSERVATION);
      setMessage("Oturum açıldı. Gözlenen görevleri ayrı ayrı kaydedin.");
    });
  }
  async function saveObservation(event: FormEvent) {
    event.preventDefault(); if (!pilot) return;
    await run(async () => {
      await mutate(`/v1/teacher/learning/pilots/${pilot.id}/tasks/${taskId}`, "PUT", { revision: pilot.revision, observation });
      setMessage("Gözlem kaydedildi.");
    });
  }
  function selectPilot(id: string) {
    setPilotId(id); setTaskId("open-topic"); setObservation(pilots.find(item => item.id === id)?.observations["open-topic"] ?? EMPTY_OBSERVATION);
  }
  function selectTask(id: string) { setTaskId(id); setObservation(pilot?.observations[id] ?? EMPTY_OBSERVATION); }
  async function exportPilot() {
    if (!pilot) return;
    // Refresh before export; unsaved drafts and stale cached observations are not evidence.
    const fresh = await mutate(`/v1/teacher/learning/pilots/${pilot.id}`, "GET") as Pilot;
    const blob = new Blob([JSON.stringify(fresh, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `eristem-pilot-${pilot.participant_code}.json`; link.click(); URL.revokeObjectURL(url);
  }

  return <><a className="skip" href="#management-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Öğrenme kalite yönetimi</p></header>
    <main id="management-main" className="student-shell learning-shell">
      <nav className="student-actions" aria-label="Kalite yönetimi"><a href="/?mode=learning-review">Uzman incelemesi</a><a href="/?mode=pilot">Kullanıcı pilotu</a><a href="/?mode=learning-release">Yayın kontrolü</a><a href="/">Öğrenci kütüphanesi</a></nav>
      <h1>{panel === "review" ? "Uzman içerik incelemesi" : panel === "pilot" ? "Kullanıcı pilotu ve gözlemler" : "Öğrenme içeriği yayın kontrolü"}</h1>
      <p className="notice">Bu yerel geliştirme panelidir. Gerçek inceleme ve katılım yapılmadan onay veya kullanıcı kanıtı girilmez. Kayıtlar içerik sürümüne bağlıdır.</p>
      <p role="status">{message}</p><button type="button" disabled={busy} onClick={() => setReload(value => value + 1)}>Kayıtları yeniden yükle</button>
      <label htmlFor="management-module">Öğrenme konusu<select id="management-module" value={moduleId} onChange={event => { setModuleId(event.target.value); setChecks({}); setEvidence(""); setReviewNote(""); }}>{modules.map(item => <option key={item.id} value={item.id}>{item.title} · {item.version}</option>)}</select></label>
      {selected && <section className="study-card"><h2>{selected.title}: kalite durumu</h2><p>{selected.quality.status === "published" ? "Yayın kontrolü geçti" : selected.quality.expert_approved ? "Uzman kaydı onaylı; pilot ve yayın kontrolünü inceleyin" : "Güncel uzman incelemesi bekliyor"}</p><p>Gerçek kullanıcıyla uygun tamamlanmış pilot: {selected.quality.qualifying_pilots}. Yayını engelleyen pilot: {selected.quality.blocking_pilots}.</p>{selected.review && <p>Son inceleme kaydı: {selected.review.evidence_reference}. {selected.review.note}</p>}</section>}

      {panel === "review" && selected && <>
        <details className="student-help"><summary>İncelenecek anlatımlar ve cevap anahtarları</summary>
          {selected.content.lessons.map(lesson => <section key={lesson.id}><h3>{lesson.title}</h3><p>{lesson.short_description}</p><ol>{lesson.detailed_description.map((text, i) => <li key={i}>{text}</li>)}</ol><h4>Nesne veya listeyle keşif</h4><ol>{lesson.exploration.map((text, i) => <li key={i}>{text}</li>)}</ol><p>{lesson.limitation}</p></section>)}
          <h3>Sorular ve denetim anahtarları</h3>{selected.content.exercises.map(task => {
            const key = selected.marking_keys[task.id];
            const answer = Array.isArray(key?.answer) ? `{${key.answer.join(", ")}}` : task.choices.find(option => option.id === key?.answer)?.text;
            return <section key={task.id}><h4>{task.topic} · {task.stage === "guided" ? "Rehberli" : task.stage === "baseline" ? "Ön bilgi" : task.stage === "review" ? "Gecikmeli" : "Yardımsız"}</h4><p>{task.spoken_question}</p><p>Beklenen: {answer}</p>{key?.hint && <p>İpucu: {key.hint}</p>}{key?.hints?.filter(Boolean).map((hint, i) => <p key={i}>İpucu {i + 1}: {hint}</p>)}</section>;
          })}
        </details>
        <form onSubmit={event => void review(event)} className="study-card"><h2>İnceleme sonucunu kaydet</h2>
          <label htmlFor="expertise">İnceleme alanı<select id="expertise" value={expertise} onChange={event => setExpertise(event.target.value)}><option value="special_education">Görme yetersizliği / özel eğitim</option><option value="subject_teacher">Konu öğretimi</option><option value="accessibility">Erişilebilirlik</option></select></label>
          <label htmlFor="review-reference">Private uzman değerlendirme kaydı referansı<input id="review-reference" value={evidence} onChange={event => setEvidence(event.target.value)} minLength={3} maxLength={200} required /></label>
          <fieldset><legend>Gerçek incelemede tamamlanan kontroller</legend>{Object.entries(CHECKS).map(([key, label]) => <label key={key} className="learning-option"><input type="checkbox" checked={checks[key] === true} onChange={event => setChecks({ ...checks, [key]: event.target.checked })} /><span>{label}</span></label>)}</fieldset>
          <label htmlFor="review-decision">Karar<select id="review-decision" value={decision} onChange={event => setDecision(event.target.value)}><option value="approve">İçerik kontrollerini onayla</option><option value="changes_requested">Düzeltme iste</option></select></label>
          <label htmlFor="review-note">İnceleme notu veya istenen düzeltme<textarea id="review-note" value={reviewNote} onChange={event => setReviewNote(event.target.value)} required={decision === "changes_requested"} maxLength={1000} /></label>
          <button disabled={busy || (decision === "approve" && Object.keys(CHECKS).some(key => !checks[key]))}>Uzman incelemesini kaydet</button>
        </form>
      </>}

      {panel === "release" && selected && <section className="study-card"><h2>Yayın kararı</h2><p>Güncel içerik onayı, tüm görevleri kaydedilmiş gerçek katılımcı pilotu ve kritik engel olmaması gerekir. Prova oturumları gerçek kullanıcı kanıtı sayılmaz.</p>
        <button type="button" disabled={busy || !selected.quality.expert_approved || selected.quality.qualifying_pilots === 0 || selected.quality.blocking_pilots > 0} onClick={() => void run(async () => { await mutate(`/v1/reviewer/learning/modules/${moduleId}/publish`, "POST", { revision: selected.quality.revision }); setMessage("Yayın kontrolü geçti."); })}>İçeriğin yayınını onayla</button></section>}

      {panel === "pilot" && selected && <>
        <form className="study-card" onSubmit={event => void createPilot(event)}><h2>Yeni pilot oturumu</h2><p>Katılımcı kodu otomatik üretilir. İsim, iletişim bilgisi, tanı veya ham öğrenci cevabı girmeyin. Yetişkin katılımı içindir; çocuklarla çalışma ayrı kurum ve rıza süreci gerektirir.</p>
          <label htmlFor="pilot-kind">Oturum türü<select id="pilot-kind" value={kind} onChange={event => setKind(event.target.value)}><option value="rehearsal">Araştırmacı provası — kullanıcı kanıtı sayılmaz</option><option value="participant">Gerçek yetişkin katılımcı oturumu</option></select></label>
          {kind === "participant" && <><label className="learning-option"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>Yetişkin katılımcı amacı, bırakma ve veri silme hakkını anlayarak rıza verdi</span></label><label htmlFor="consent-reference">Private rıza kaydı referansı<input id="consent-reference" value={consentReference} onChange={event => setConsentReference(event.target.value)} minLength={3} maxLength={200} required /></label></>}
          <label htmlFor="pilot-device">Cihaz<select id="pilot-device" value={device} onChange={event => setDevice(event.target.value)}><option value="desktop">Bilgisayar</option><option value="android">Android</option><option value="ios">iPhone/iPad</option><option value="other">Diğer</option></select></label>
          <label htmlFor="pilot-tool">Kullanılan erişim aracı<select id="pilot-tool" value={tool} onChange={event => setTool(event.target.value)}><option value="nvda">NVDA</option><option value="talkback">TalkBack</option><option value="voiceover">VoiceOver</option><option value="braille">Braille</option><option value="magnification">Büyütme</option><option value="other">Diğer</option></select></label>
          <button disabled={busy || (kind === "participant" && !consent)}>Pilot oturumu aç</button>
        </form>
        <label htmlFor="pilot-session">Gözlem oturumu<select id="pilot-session" value={pilotId} onChange={event => selectPilot(event.target.value)}><option value="">Bir oturum seçin</option>{pilots.map(item => <option value={item.id} key={item.id}>{item.participant_code} · {item.module_id} · {item.kind === "participant" ? "katılımcı" : "prova"} · {item.state === "active" ? "devam ediyor" : "tamamlandı"}</option>)}</select></label>
        {pilot && <section className="study-card"><h2>{pilot.participant_code}: görev gözlemleri</h2><p>{Object.keys(pilot.observations).length} / {tasks.length} görev kaydedildi. İçerik sürümü: {pilot.module_version}.</p>
          <label htmlFor="pilot-task">Gözlenen görev<select id="pilot-task" value={taskId} onChange={event => selectTask(event.target.value)}>{tasks.map(task => <option key={task.id} value={task.id}>{task.title}{pilot.observations[task.id] ? " · kaydedildi" : ""}</option>)}</select></label>
          <form onSubmit={event => void saveObservation(event)}><fieldset disabled={busy || pilot.state !== "active"}><legend>Görev gözlemi</legend>
            <label htmlFor="observation-result">Sonuç<select id="observation-result" value={observation.result} onChange={event => setObservation({ ...observation, result: event.target.value })}><option value="independent">Araştırmacı yardımı olmadan tamamladı</option><option value="with_help">Araştırmacı yardımıyla tamamladı</option><option value="not_completed">Tamamlayamadı</option><option value="skipped">Katılımcı geçmeyi seçti</option></select></label>
            <label htmlFor="observation-help">Araştırmacı yardım sayısı<input id="observation-help" type="number" min={0} max={100} value={observation.researcher_help_count} onChange={event => setObservation({ ...observation, researcher_help_count: Number(event.target.value) })} required /></label>
            <label htmlFor="observation-category">Gözlenen sorun<select id="observation-category" value={observation.category ?? ""} onChange={event => setObservation({ ...observation, category: event.target.value || null, severity: event.target.value ? observation.severity ?? "minor" : null })}><option value="">Sorun gözlenmedi</option><option value="access">Erişim</option><option value="representation">Temsil veya anlatım</option><option value="concept">Kavram ilişkisi</option><option value="input_format">Giriş biçimi</option><option value="source_error">Kaynak yanlışlığı</option><option value="uncertain">Belirsiz</option></select></label>
            {observation.category && <label htmlFor="observation-severity">Sorunun önemi<select id="observation-severity" value={observation.severity ?? "minor"} onChange={event => setObservation({ ...observation, severity: event.target.value })}><option value="minor">Küçük</option><option value="major">Önemli</option><option value="blocking">Kritik — yayını engeller</option></select></label>}
            <label htmlFor="observation-note">Anonim davranış gözlemi<textarea id="observation-note" value={observation.note} onChange={event => setObservation({ ...observation, note: event.target.value })} maxLength={500} /></label><button>Görev gözlemini kaydet</button>
          </fieldset></form>
          <div className="student-actions"><button type="button" disabled={busy || pilot.state !== "active" || Object.keys(pilot.observations).length !== tasks.length} onClick={() => void run(async () => { await mutate(`/v1/teacher/learning/pilots/${pilot.id}/complete`, "POST", { revision: pilot.revision }); setMessage("Pilot tamamlandı. Prova oturumu kullanıcı kanıtı değildir."); })}>Pilotu tamamla</button>
            <button type="button" onClick={() => void run(exportPilot)}>Kodlanmış pilot kaydını indir</button>
            <button type="button" disabled={busy} onClick={() => { if (window.confirm("Bu pilotun bütün gözlem ve rıza referansları silinsin mi? İlgili yayın onayı yeniden kontrol gerektirecek.")) void run(async () => { await mutate(`/v1/teacher/learning/pilots/${pilot.id}?revision=${pilot.revision}`, "DELETE"); setPilotId(""); setMessage("Pilot kaydı silindi."); }); }}>Pilot verisini sil</button></div>
        </section>}
      </>}
    </main>
  </>;
}
