import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLearningSpeech } from "./useLearningSpeech";
import { VoiceCommandPanel } from "./VoiceCommandPanel";
import { LocalDictation } from "./LocalDictation";
import type { VoiceIntent, VoiceKind } from "./voice_commands";

type Slot = { id: string; title: string; base_minutes: number; extra_minutes: number };
type Profile = { id: string; title: string; year: number; verified_at: string; source_url: string; source_section: string; arrangement: string; slots: Slot[] };
type ExamAvailability = { title: string; content_mode: string | null; question_count: number; session_question_count: number };
type Exam = { id: string; revision: number; profile: Profile; slot: Slot; state: "active" | "finished";
  deadline: number; server_now: number; duration_minutes: number; notice: string;
  questions: { id: string; question: string; choices: { id: string; text: string }[] }[];
  answers: Record<string, string | null>; flags: Record<string, boolean>;
  results: { question_id: string; answered: boolean; correct: boolean; correct_answer: string | null; explanation: string | null; coach_turns: number; coach_text: string | null; source_available: boolean }[] | null };
type CoachReply = { stage: string; turn: number; text: string; source_ids: string[]; can_reveal_explanation: boolean; provider?: "local" | "deepseek" };
const SESSION_KEY = "eristem:exam-session:v1";
function readSessionId() { try { return sessionStorage.getItem(SESSION_KEY); } catch { return null; } }

export function ExamPractice({ api, onBack }: { api: string; onBack: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState("yks-reader-2026");
  const [slotId, setSlotId] = useState("ayt");
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
  const [pendingVoiceAction, setPendingVoiceAction] = useState<"save" | "clear" | "finish" | null>(null);
  const [coachReplies, setCoachReplies] = useState<Record<string, CoachReply>>({});
  const [coachResponse, setCoachResponse] = useState<Record<string, string>>({});
  const [externalCoachConsent, setExternalCoachConsent] = useState(false);
  const [externalCoachConfigured, setExternalCoachConfigured] = useState(false);
  const [availability, setAvailability] = useState<ExamAvailability | null>(null);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const { speak, speakUnit, stop, status: voiceStatus } = useLearningSpeech(1);
  const selected = profiles.find(item => item.id === profileId);
  const slot = selected?.slots.find(item => item.id === slotId);
  const question = exam?.questions[index];
  const unsaved = !!exam && !!question && draft !== (exam.answers[question.id] ?? "");
  const remaining = exam?.state === "active" ? Math.max(0, Math.ceil(exam.deadline - (clock - offset) / 1000)) : 0;

  useEffect(() => {
    const controller = new AbortController();
    mounted.current = true;
    const headers = { "X-Role": "student" };
    void fetch(`${api}/v1/student/exams/coach-capabilities`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) return;
      const data = await response.json() as { external_coach_configured?: boolean };
      if (!controller.signal.aborted) setExternalCoachConfigured(data.external_coach_configured === true);
    }).catch(() => { /* Offline or unconfigured: local coach remains available. */ });
    void fetch(`${api}/v1/student/exams/availability`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("availability");
      const data = await response.json() as ExamAvailability;
      if (!controller.signal.aborted) setAvailability(data);
    }).catch(() => { if (!controller.signal.aborted) setAvailability(null); });
    void fetch(`${api}/v1/student/exams/profiles`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("profiles");
      const data = await response.json() as Profile[];
      if (!controller.signal.aborted) { setProfiles(data); setStatus(""); }
    }).catch(() => { if (!controller.signal.aborted) setStatus("Profiller yüklenemedi. Bağlantıyı kontrol edip sayfayı yenileyin."); });
    const sessionId = readSessionId();
    if (sessionId) void fetch(`${api}/v1/student/exams/sessions/${encodeURIComponent(sessionId)}`, { headers, signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("session");
      const data = await response.json() as Exam;
      if (!controller.signal.aborted) { setPendingVoiceAction(null); setExam(data); setDraft(data.answers[data.questions[0]?.id] ?? ""); setOffset(Date.now() - data.server_now * 1000); }
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
    if (data.state !== "active") setPendingVoiceAction(null);
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
      .then(data => { if (!controller.signal.aborted) { setPendingVoiceAction(null); setExam(data); setOffset(Date.now() - data.server_now * 1000); setDraft(""); setStatus("Süre tamamlandı. Kaydedilmiş yanıtlar değerlendirildi."); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Süre tamamlandı; sonuç için bağlantıyı kontrol edip provayı yeniden yükleyin."); });
    return () => controller.abort();
  }, [api, exam, remaining, busy]); // Server enforces the deadline, including after refresh.

  async function start(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      const created = await call("/sessions", "POST", { profile_id: profileId, slot_id: slotId,
        arrangement_confirmed: confirmed, mode, short_minutes: minutes });
      if (!created || !mounted.current) return;
      setPendingVoiceAction(null); setIndex(0); accept(created, Date.now());
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
    stop(); setPendingVoiceAction(null); setIndex(next); setDraft(exam.answers[exam.questions[next].id] ?? "");
  }
  async function refresh() {
    if (!exam) return;
    if (unsaved && !window.confirm("Kaydedilememiş seçiminiz var. Sunucudaki kaydı yüklemek bu seçimi temizleyecek. Devam edilsin mi?")) return;
    await run(async () => { const data = await call(`/sessions/${exam.id}`); if (data && mounted.current) { accept(data, Date.now()); setStatus("Prova yeniden yüklendi."); } });
  }
  async function finish(confirmedByVoice = false) {
    if (!exam || busy || unsaved || (!confirmedByVoice && !window.confirm("Provayı bitirip sonuçları açmak istiyor musunuz? Bundan sonra yanıtlar değiştirilemez."))) return;
    stop();
    await run(async () => { const result = await call(`/sessions/${exam.id}/finish`, "POST", { revision: exam.revision }); if (result && mounted.current) { accept(result, Date.now()); setStatus("Prova tamamlandı. Ham yanıt kayıtları temizlendi."); } });
  }
  async function remove() {
    if (!exam || !window.confirm("Bu provanın sunucudaki yanıt ve sonuç kayıtları tamamen silinsin mi?")) return;
    await run(async () => {
      await call(`/sessions/${exam.id}?revision=${exam.revision}`, "DELETE");
      if (!mounted.current) return;
      setPendingVoiceAction(null); setExam(null); setIndex(0); setDraft(""); setConfirmed(false);
      try { sessionStorage.removeItem(SESSION_KEY); } catch { /* Server data has been erased. */ }
      setStatus("Prova kaydı silindi. Yeni prova başlatabilirsiniz.");
    });
  }

  async function requestCoach(questionId: string, turn: number) {
    if (!exam || exam.state !== "finished") return;
    await run(async () => {
      const response = await fetch(`${api}/v1/student/exams/sessions/${exam.id}/review/${encodeURIComponent(questionId)}/coach`, {
        method: "POST", headers: { "X-Role": "student", "Content-Type": "application/json" },
        body: JSON.stringify({ revision: exam.revision, turn, learner_response: coachResponse[questionId] ?? "", external_coach_consent: externalCoachConsent }),
      });
      if (!response.ok) throw new Error("Kaynaklı koçluk şu anda hazır değil.");
      const data = await response.json() as { reply: CoachReply; exam: Exam };
      if (mounted.current) { setCoachReplies(current => ({ ...current, [questionId]: data.reply })); accept(data.exam, Date.now());
        if (turn === 1 && externalCoachConsent) setStatus(data.reply.provider === "deepseek" ? "Çevrim içi koç yanıtı alındı." : "Çevrim içi koç kullanılamadı veya yanıtı doğrulanamadı; yerel koç kullanıldı."); }
    });
  }

  const readRemaining = () => speak(`Kalan süre ${Math.floor(remaining / 60)} dakika ${remaining % 60} saniye.`);
  const choiceForLabel = (label: string) => question?.choices["ABCDE".indexOf(label)];
  const readUnit = (unit: string) => {
    if (!exam || !question) return;
    const path = `${api}/v1/student/exams/sessions/${encodeURIComponent(exam.id)}/questions/${encodeURIComponent(question.id)}/audio/${encodeURIComponent(unit)}`;
    speakUnit(path, `exam:${exam.id}:${question.id}:${unit}`);
  };
  const voiceCommand = (command: VoiceIntent) => {
    if (!exam || exam.state !== "active" || !question || remaining === 0) return;
    if (command.kind === "read_selected") { readUnit("stem"); return; }
    if (command.kind === "show_choices") { speak(question.choices.map((item, i) => `Şık ${"ABCDE"[i]}. ${item.text}`).join(". ")); return; }
    if (command.kind === "read_choice") {
      const item = choiceForLabel(command.label);
      if (item) readUnit(`choice-${command.label}`);
      return;
    }
    if (command.kind === "select_choice") {
      const item = choiceForLabel(command.label);
      if (!item) return;
      setDraft(item.id); setPendingVoiceAction("save");
      speak(`Şık ${command.label}. ${item.text}. Yanıtı kaydetmek için onayla de.`);
      return;
    }
    if (command.kind === "confirm") {
      const action = pendingVoiceAction;
      setPendingVoiceAction(null);
      if (action === "save") void saveAnswer(draft);
      else if (action === "clear") void saveAnswer("");
      else if (action === "finish") void finish(true);
      else speak("Onay bekleyen bir sesli işlem yok.");
      return;
    }
    if (command.kind === "clear_answer") { setPendingVoiceAction("clear"); speak("Yanıtı temizlemek için onayla de."); return; }
    if (command.kind === "finish_exam") { setPendingVoiceAction("finish"); speak("Denemeyi bitirmek ve sonuçları açmak için onayla de."); return; }
    if (command.kind === "flag_question") {
      if (unsaved) { speak("Önce seçtiğin yanıtı onayla veya temizle."); return; }
      void saveAnswer(draft, !(exam.flags[question.id] ?? false));
      return;
    }
    if (command.kind === "read_time") { readRemaining(); return; }
    if (command.kind === "next_question" && index < exam.questions.length - 1) { move(index + 1); return; }
    if (command.kind === "previous_question" && index > 0) { move(index - 1); return; }
    if (command.kind === "go_question" && command.number <= exam.questions.length) { move(command.number - 1); return; }
    if (command.kind === "stop_audio") stop();
  };

  return <><a className="skip" href="#exam-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Sınav erişim provası</p></header><main id="exam-main" className="student-shell learning-shell">
    <button type="button" onClick={() => { if (!unsaved || window.confirm("Kaydedilmemiş seçiminiz var. Yine de kütüphaneye dönülsün mü?")) { stop(); onBack(); } }}>Kütüphaneye dön</button>
    <h1 ref={heading} tabIndex={-1}>{exam ? exam.state === "finished" ? "Prova sonuçları" : `Soru ${index + 1} / ${exam.questions.length}` : "Sınav düzenlemesini seçin"}</h1>
    <p role="status">{status}</p>
    {!exam ? <form onSubmit={event => void start(event)}>
      <p>{availability ? <>{availability.title}: toplam {availability.question_count} soru. Bu oturumda {availability.session_question_count} soru gösterilir.</> : "Deneme paketi bilgisi yüklenemedi; başlamadan önce bağlantıyı kontrol edin."} Onaylı paket yoksa kısa sentetik sorular yalnız gezinme provası içindir. Kaynaklardaki sınav düzenlemeleri 2026 yılına aittir; başka yıllara otomatik uygulanmaz.</p>
      <label htmlFor="exam-profile">Sınav ve düzenleme<select id="exam-profile" value={profileId} onChange={event => { const next = profiles.find(item => item.id === event.target.value); setProfileId(event.target.value); setSlotId(next?.slots[0]?.id ?? ""); setConfirmed(false); }}>{profiles.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
      {selected && <><p>{selected.arrangement}</p><p><a href={selected.source_url} target="_blank" rel="noreferrer">Resmî {selected.year} kılavuzunu aç</a> · {selected.source_section} · Kaynak kontrolü: {selected.verified_at}</p>
        <label htmlFor="exam-slot">Oturum<select id="exam-slot" value={slotId} onChange={event => setSlotId(event.target.value)}>{selected.slots.map(item => <option value={item.id} key={item.id}>{item.title}: {item.base_minutes} + {item.extra_minutes} dakika</option>)}</select></label></>}
      <label htmlFor="exam-mode">Prova süresi<select id="exam-mode" value={mode} onChange={event => setMode(event.target.value)}><option value="short">Kısa erişim ve gezinme çalışması</option><option value="full">Seçilen düzenlemenin tam süresi</option></select></label>
      {mode === "short" ? <label htmlFor="exam-minutes">Kısa prova: dakika<input id="exam-minutes" type="number" value={minutes} min={1} max={60} onChange={event => setMinutes(Number(event.target.value))} required /></label> : <p>Prova süresi: {slot ? slot.base_minutes + slot.extra_minutes : 0} dakika. Soru sayısı etkin pakete bağlıdır.</p>}
      <label className="learning-option"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Seçtiğim düzenlemeyi kendi sınav giriş belgemle kontrol ettim veya bu profili yalnız gezinme çalışması için seçiyorum. Uygulama sınav hakkı belirlemez.</span></label>
      <p className="notice">Seçimleriniz bu bilgisayarda geçici tutulur. Yanlış seçimler koçluk için saklanır; ilgili koçluk tamamlandığında silinir. Prova verisini tamamen silebilirsiniz; en geç yedi gün sonra kayıt otomatik silinir. Oturum kimliği yalnız bu tarayıcı sekmesinde saklanır.</p>
      <button disabled={busy || !selected || !slot || !confirmed || !availability}>Provayı başlat</button>
    </form> : <>
      <p>{exam.profile.title} · {exam.slot.title} · {exam.duration_minutes} dakika.</p><p className="notice">{exam.notice}</p>
      {exam.state === "active" && question ? <>
        <p aria-live="off">Kalan süre: {Math.floor(remaining / 60)} dakika {remaining % 60} saniye.</p><button type="button" onClick={readRemaining}>Kalan süreyi seslendir</button>
        <nav className="exam-navigation" aria-label="Soru gezinmesi">{exam.questions.map((item, i) => <button type="button" key={item.id} aria-current={i === index ? "step" : undefined} disabled={busy || unsaved} onClick={() => move(i)}>Soru {i + 1}{exam.answers[item.id] ? " · yanıtlı" : " · boş"}{exam.flags[item.id] ? " · gözden geçir" : ""}</button>)}</nav>
        <section className="study-card"><h2>Prova sorusu {index + 1}</h2><p id="exam-question" className="practice-question">{question.question}</p>
          <div className="student-actions"><button type="button" onClick={() => readUnit("stem")}>Soruyu tekrar seslendir</button><button type="button" onClick={stop}>Sesi durdur</button></div><p role="status">{voiceStatus}</p>
          <fieldset disabled={busy || remaining === 0} aria-describedby="exam-question"><legend>Yanıtınız</legend>{question.choices.map(option => <label className="learning-option" key={option.id}><input type="radio" name="exam-answer" checked={draft === option.id} onChange={() => void saveAnswer(option.id)} /><span>{option.text}</span></label>)}</fieldset>
          {unsaved && <button type="button" disabled={busy || remaining === 0} onClick={() => void saveAnswer(draft)}>Seçimi yeniden kaydet</button>}
          <div className="student-actions"><button type="button" disabled={busy || unsaved || remaining === 0} onClick={() => void saveAnswer("", exam.flags[question.id] ?? false)}>Yanıtı temizle</button><button type="button" disabled={busy || unsaved || remaining === 0} onClick={() => void saveAnswer(draft, !exam.flags[question.id])}>{exam.flags[question.id] ? "Gözden geçirme işaretini kaldır" : "Sonra gözden geçirmek için işaretle"}</button></div>
        </section>
        {remaining > 0 && <VoiceCommandPanel key={question.id} title="Denemede sesli yönlendirme" examples={["soruyu oku", "şık B'yi seç", "onayla", "sonraki soru", "süreyi oku"]}
          available={["read_selected", "show_choices", "read_choice", "select_choice", "confirm", "clear_answer", "flag_question", "read_time", "finish_exam", "stop_audio", "next_question", "previous_question", "go_question"] satisfies VoiceKind[]}
          onCommand={voiceCommand} />}
        <div className="student-actions"><button type="button" disabled={busy || unsaved || index === 0} onClick={() => move(index - 1)}>Önceki soru</button><button type="button" disabled={busy || unsaved || index === exam.questions.length - 1} onClick={() => move(index + 1)}>Sonraki soru</button><button type="button" disabled={busy || unsaved} onClick={() => void finish()}>Provayı bitir</button></div>
      </> : <section className="study-card"><h2>Görev sonuçları</h2><p>{exam.results?.filter(item => item.correct).length ?? 0} doğru · {exam.results?.filter(item => item.answered && !item.correct).length ?? 0} yanlış · {exam.results?.filter(item => !item.answered).length ?? 0} boş. Bu, resmî sınav puanı değildir.</p>{externalCoachConfigured && <label className="learning-option"><input type="checkbox" checked={externalCoachConsent} onChange={event => setExternalCoachConsent(event.target.checked)} /><span>İsteğe bağlı çevrim içi koçluğu kabul ediyorum: soru metni, yanlış seçimim, yazdığım düşünce ve kaynak kesiti DeepSeek servisine gönderilebilir. Kullanılamazsa yerel koç çalışır.</span></label>}{exam.results?.map((result, i) => <details key={result.question_id}><summary>Soru {i + 1}: {result.correct ? "doğru" : result.answered ? "yanlış" : "boş"}</summary><p>{exam.questions.find(item => item.id === result.question_id)?.question}</p>{result.correct_answer && <p>Doğru yanıt: {result.correct_answer}. {result.explanation}</p>}{!result.correct && (result.source_available ? <section aria-label={`Soru ${i + 1} kaynaklı koçluk`}>
        {result.coach_text && <><p role="status">{coachReplies[result.question_id]?.text ?? result.coach_text}</p><button type="button" onClick={() => speak(coachReplies[result.question_id]?.text ?? result.coach_text ?? "")}>Koçun yanıtını dinle</button></>}
        {result.coach_turns === 0 && <button type="button" disabled={busy} onClick={() => void requestCoach(result.question_id, 1)}>Kaynakla birlikte çöz</button>}
        {result.coach_turns === 1 && <><label htmlFor={`coach-response-${result.question_id}`}>Soru hakkındaki düşünceniz</label><textarea id={`coach-response-${result.question_id}`} value={coachResponse[result.question_id] ?? ""} maxLength={1000} onChange={event => setCoachResponse(current => ({ ...current, [result.question_id]: event.target.value }))} /><LocalDictation disabled={busy} onText={value => setCoachResponse(current => ({ ...current, [result.question_id]: value }))} /><button type="button" disabled={busy || !(coachResponse[result.question_id] ?? "").trim()} onClick={() => void requestCoach(result.question_id, 2)}>Düşüncemi paylaş ve ikinci ipucunu aç</button></>}
      </section> : <p>Bu prova sorusunda onaylı MEB kanıtı bulunmadığından kaynaklı koçluk ve çözüm gösterilmiyor.</p>)}</details>)}</section>}
      <div className="student-actions"><button type="button" disabled={busy} onClick={() => void refresh()}>Provayı yeniden yükle</button><button type="button" disabled={busy} onClick={() => void remove()}>Prova verisini sil</button></div>
    </>}
  </main></>;
}
