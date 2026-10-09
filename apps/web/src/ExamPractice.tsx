import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLearningSpeech } from "./useLearningSpeech";

type Slot = { id: string; title: string; base_minutes: number; extra_minutes: number };
type Profile = { id: string; title: string; year: number; verified_at: string; source_url: string; source_section: string; arrangement: string; slots: Slot[] };
type Exam = { id: string; revision: number; profile: Profile; slot: Slot; state: "active" | "finished";
  deadline: number; server_now: number; duration_minutes: number; notice: string;
  questions: { id: string; question: string; choices: { id: string; text: string }[] }[];
  answers: Record<string, string | null>; flags: Record<string, boolean>;
  results: { question_id: string; answered: boolean; correct: boolean; correct_answer: string; explanation: string }[] | null };
const SESSION_KEY = "eristem:exam-session:v1";
function readSessionId() { try { return sessionStorage.getItem(SESSION_KEY); } catch { return null; } }

export function ExamPractice({ api, onBack }: { api: string; onBack: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState("lgs-reader-2026");
  const [slotId, setSlotId] = useState("numeric");
  const [mode, setMode] = useState("short");
  const [minutes, setMinutes] = useState(5);
  const [confirmed, setConfirmed] = useState(false);
  const [exam, setExam] = useState<Exam | null>(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState("Sınav profilleri yükleniyor.");
  const [busy, setBusy] = useState(false);
  const [clock, setClock] = useState(Date.now);
  const [offset, setOffset] = useState(0);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const { speak, stop, status: voiceStatus } = useLearningSpeech(1);
  const selected = profiles.find(item => item.id === profileId);
  const slot = selected?.slots.find(item => item.id === slotId);
  const question = exam?.questions[index];
  const unsaved = !!exam && !!question && draft !== (exam.answers[question.id] ?? "");
  const remaining = exam?.state === "active" ? Math.max(0, Math.ceil(exam.deadline - (clock - offset) / 1000)) : 0;

  useEffect(() => {
    const controller = new AbortController();
    mounted.current = true;
    const headers = { "X-Role": "student" };
    void fetch(`${api}/v1/student/exams/profiles`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("profiles");
      const data = await response.json() as Profile[];
      if (!controller.signal.aborted) { setProfiles(data); setStatus(""); }
    }).catch(() => { if (!controller.signal.aborted) setStatus("Profiller yüklenemedi. Bağlantıyı kontrol edip sayfayı yenileyin."); });
    const sessionId = readSessionId();
    if (sessionId) void fetch(`${api}/v1/student/exams/sessions/${encodeURIComponent(sessionId)}`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("session");
      const data = await response.json() as Exam;
      if (!controller.signal.aborted) { setExam(data); setDraft(data.answers[data.questions[0]?.id] ?? ""); setOffset(Date.now() - data.server_now * 1000); }
    }).catch(() => { if (!controller.signal.aborted) setStatus("Önceki prova yüklenemedi. Yeni prova açabilir veya sayfayı yenileyebilirsiniz."); });
    return () => { controller.abort(); mounted.current = false; };
  }, [api]);
  useEffect(() => { heading.current?.focus(); stop(); }, [index, exam?.id, exam?.state, stop]);
  useEffect(() => {
    if (exam?.state !== "active") return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [exam?.state]);

  async function call(path: string, method = "GET", body?: unknown): Promise<Exam | null> {
    const response = await fetch(`${api}/v1/student/exams${path}`, { method,
      headers: { "X-Role": "student", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(typeof data?.detail === "string" ? data.detail : "İşlem tamamlanamadı; kaydı yeniden yükleyin.");
    }
    return response.status === 204 ? null : response.json();
  }
  function accept(data: Exam, receivedAt: number) {
    setExam(data); setOffset(receivedAt - data.server_now * 1000); setClock(receivedAt);
    setDraft(data.answers[data.questions[index]?.id] ?? "");
  }
  async function run(action: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true);
    try { await action(); }
    catch (error) { if (mounted.current) setStatus(error instanceof Error ? error.message : "Bağlantı sorunu oluştu. Yanıtınızı yeniden kaydedin."); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }
  useEffect(() => {
    if (!exam || exam.state !== "active" || remaining !== 0 || inFlight.current) return;
    const controller = new AbortController();
    void fetch(`${api}/v1/student/exams/sessions/${exam.id}`, { headers: { "X-Role": "student" }, signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error("expired"); return response.json() as Promise<Exam>; })
      .then(data => { if (!controller.signal.aborted) { setExam(data); setOffset(Date.now() - data.server_now * 1000); setDraft(""); setStatus("Süre tamamlandı. Kaydedilmiş yanıtlar değerlendirildi."); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Süre tamamlandı; sonuç için bağlantıyı kontrol edip provayı yeniden yükleyin."); });
    return () => controller.abort();
  }, [api, exam, remaining, busy]); // Server enforces the deadline, including after refresh.

  async function start(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      const created = await call("/sessions", "POST", { profile_id: profileId, slot_id: slotId,
        arrangement_confirmed: confirmed, mode, short_minutes: minutes });
      if (!created || !mounted.current) return;
      setIndex(0); accept(created, Date.now());
      try { sessionStorage.setItem(SESSION_KEY, created.id); setStatus("Prova başladı. Doğruluk ve çözümler bitirene kadar gösterilmeyecek."); }
      catch { setStatus("Prova başladı; bu tarayıcıda oturum kimliği saklanamadı. Yenileme sonrası devam mümkün olmayabilir."); }
    });
  }
  async function saveAnswer(answer: string, flagged = question ? exam?.flags[question.id] ?? false : false) {
    if (!exam || !question || inFlight.current) return;
    setDraft(answer);
    await run(async () => {
      const saved = await call(`/sessions/${exam.id}/answer`, "PUT", { revision: exam.revision,
        question_id: question.id, answer: answer || null, flagged });
      if (saved && mounted.current) { accept(saved, Date.now()); setStatus("Yanıt ve gözden geçirme işareti kaydedildi."); }
    });
  }
  function move(next: number) {
    if (!exam || busy || unsaved) return;
    stop(); setIndex(next); setDraft(exam.answers[exam.questions[next].id] ?? "");
  }
  async function refresh() {
    if (!exam) return;
    if (unsaved && !window.confirm("Kaydedilememiş seçiminiz var. Sunucudaki kaydı yüklemek bu seçimi temizleyecek. Devam edilsin mi?")) return;
    await run(async () => { const data = await call(`/sessions/${exam.id}`); if (data && mounted.current) { accept(data, Date.now()); setStatus("Prova yeniden yüklendi."); } });
  }
  async function finish() {
    if (!exam || busy || unsaved || !window.confirm("Provayı bitirip sonuçları açmak istiyor musunuz? Bundan sonra yanıtlar değiştirilemez.")) return;
    stop();
    await run(async () => { const result = await call(`/sessions/${exam.id}/finish`, "POST", { revision: exam.revision }); if (result && mounted.current) { accept(result, Date.now()); setStatus("Prova tamamlandı. Ham yanıt kayıtları temizlendi."); } });
  }
  async function remove() {
    if (!exam || !window.confirm("Bu provanın sunucudaki yanıt ve sonuç kayıtları tamamen silinsin mi?")) return;
    await run(async () => {
      await call(`/sessions/${exam.id}?revision=${exam.revision}`, "DELETE");
      if (!mounted.current) return;
      setExam(null); setIndex(0); setDraft(""); setConfirmed(false);
      try { sessionStorage.removeItem(SESSION_KEY); } catch { /* Server data has been erased. */ }
      setStatus("Prova kaydı silindi. Yeni prova başlatabilirsiniz.");
    });
  }

  return <><a className="skip" href="#exam-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Sınav erişim provası</p></header><main id="exam-main" className="student-shell learning-shell">
    <button type="button" onClick={() => { if (!unsaved || window.confirm("Kaydedilmemiş seçiminiz var. Yine de kütüphaneye dönülsün mü?")) { stop(); onBack(); } }}>Kütüphaneye dön</button>
    <h1 ref={heading} tabIndex={-1}>{exam ? exam.state === "finished" ? "Prova sonuçları" : `Soru ${index + 1} / ${exam.questions.length}` : "Sınav düzenlemesini seçin"}</h1>
    <p role="status">{status}</p>
    {!exam ? <form onSubmit={event => void start(event)}>
      <p>Bu bölüm okuyucu, süre ve yanıt gezinmesini çalıştırır. Altı sentetik soru, tam müfredat sınavı değildir. Kaynaklar 2026 yılına aittir; başka yıllara otomatik uygulanmaz.</p>
      <label htmlFor="exam-profile">Sınav ve düzenleme<select id="exam-profile" value={profileId} onChange={event => { const next = profiles.find(item => item.id === event.target.value); setProfileId(event.target.value); setSlotId(next?.slots[0]?.id ?? ""); setConfirmed(false); }}>{profiles.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
      {selected && <><p>{selected.arrangement}</p><p><a href={selected.source_url} target="_blank" rel="noreferrer">Resmî {selected.year} kılavuzunu aç</a> · {selected.source_section} · Kaynak kontrolü: {selected.verified_at}</p>
        <label htmlFor="exam-slot">Oturum<select id="exam-slot" value={slotId} onChange={event => setSlotId(event.target.value)}>{selected.slots.map(item => <option value={item.id} key={item.id}>{item.title}: {item.base_minutes} + {item.extra_minutes} dakika</option>)}</select></label></>}
      <label htmlFor="exam-mode">Prova süresi<select id="exam-mode" value={mode} onChange={event => setMode(event.target.value)}><option value="short">Kısa erişim ve gezinme çalışması</option><option value="full">Seçilen düzenlemenin tam süresi</option></select></label>
      {mode === "short" ? <label htmlFor="exam-minutes">Kısa prova: dakika<input id="exam-minutes" type="number" value={minutes} min={1} max={60} onChange={event => setMinutes(Number(event.target.value))} required /></label> : <p>Prova süresi: {slot ? slot.base_minutes + slot.extra_minutes : 0} dakika. Soru sayısı yine altıdır.</p>}
      <label className="learning-option"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Seçtiğim düzenlemeyi kendi sınav giriş belgemle kontrol ettim veya bu profili yalnız gezinme çalışması için seçiyorum. Uygulama sınav hakkı belirlemez.</span></label>
      <p className="notice">Prova sırasında seçimleriniz sunucuda geçici tutulur; bitince ham seçimler silinir ve görev sonuçları kalır. Prova verisini tamamen silebilirsiniz. Oturum kimliği yalnız bu tarayıcı sekmesinde saklanır.</p>
      <button disabled={busy || !selected || !slot || !confirmed}>Provayı başlat</button>
    </form> : <>
      <p>{exam.profile.title} · {exam.slot.title} · {exam.duration_minutes} dakika.</p><p className="notice">{exam.notice}</p>
      {exam.state === "active" && question ? <>
        <p aria-live="off">Kalan süre: {Math.floor(remaining / 60)} dakika {remaining % 60} saniye.</p><button type="button" onClick={() => speak(`Kalan süre ${Math.floor(remaining / 60)} dakika ${remaining % 60} saniye.`)}>Kalan süreyi seslendir</button>
        <nav className="exam-navigation" aria-label="Soru gezinmesi">{exam.questions.map((item, i) => <button type="button" key={item.id} aria-current={i === index ? "step" : undefined} disabled={busy || unsaved} onClick={() => move(i)}>Soru {i + 1}{exam.answers[item.id] ? " · yanıtlı" : " · boş"}{exam.flags[item.id] ? " · gözden geçir" : ""}</button>)}</nav>
        <section className="study-card"><h2>Prova sorusu {index + 1}</h2><p id="exam-question" className="practice-question">{question.question}</p>
          <div className="student-actions"><button type="button" onClick={() => speak(question.question)}>Soruyu tekrar seslendir</button><button type="button" onClick={stop}>Sesi durdur</button></div><p role="status">{voiceStatus}</p>
          <fieldset disabled={busy || remaining === 0} aria-describedby="exam-question"><legend>Yanıtınız</legend>{question.choices.map(option => <label className="learning-option" key={option.id}><input type="radio" name="exam-answer" checked={draft === option.id} onChange={() => void saveAnswer(option.id)} /><span>{option.text}</span></label>)}</fieldset>
          {unsaved && <button type="button" disabled={busy || remaining === 0} onClick={() => void saveAnswer(draft)}>Seçimi yeniden kaydet</button>}
          <div className="student-actions"><button type="button" disabled={busy || unsaved || remaining === 0} onClick={() => void saveAnswer("", exam.flags[question.id] ?? false)}>Yanıtı temizle</button><button type="button" disabled={busy || unsaved || remaining === 0} onClick={() => void saveAnswer(draft, !exam.flags[question.id])}>{exam.flags[question.id] ? "Gözden geçirme işaretini kaldır" : "Sonra gözden geçirmek için işaretle"}</button></div>
        </section>
        <div className="student-actions"><button type="button" disabled={busy || unsaved || index === 0} onClick={() => move(index - 1)}>Önceki soru</button><button type="button" disabled={busy || unsaved || index === exam.questions.length - 1} onClick={() => move(index + 1)}>Sonraki soru</button><button type="button" disabled={busy || unsaved} onClick={() => void finish()}>Provayı bitir</button></div>
      </> : <section className="study-card"><h2>Görev sonuçları</h2><p>{exam.results?.filter(item => item.correct).length ?? 0} doğru · {exam.results?.filter(item => item.answered && !item.correct).length ?? 0} yanlış · {exam.results?.filter(item => !item.answered).length ?? 0} boş. Bu, resmî sınav puanı değildir.</p>{exam.results?.map((result, i) => <details key={result.question_id}><summary>Soru {i + 1}: {result.correct ? "doğru" : result.answered ? "yanlış" : "boş"}</summary><p>{exam.questions.find(item => item.id === result.question_id)?.question}</p><p>Doğru yanıt: {result.correct_answer}. {result.explanation}</p></details>)}</section>}
      <div className="student-actions"><button type="button" disabled={busy} onClick={() => void refresh()}>Provayı yeniden yükle</button><button type="button" disabled={busy} onClick={() => void remove()}>Prova verisini sil</button></div>
    </>}
  </main></>;
}
