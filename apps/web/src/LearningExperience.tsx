import { useEffect, useRef, useState, type FormEvent } from "react";
import type { LearningExercise, LearningFeedback, LearningModule, LearningStage, ModuleSummary } from "./learning_types";
import { LEARNING_PREFIX, learningKey, markLearningHelp, parseLearningProgress, recordLearningAnswer,
  reviewAvailableAt, skipLearningExercise, stageResults, type LearningProgress } from "./learning_progress";
import { useLearningSpeech } from "./useLearningSpeech";

const STAGE_LABELS: Record<LearningStage, string> = {
  baseline: "Ön bilgi yoklaması", guided: "Rehberli çalışma",
  transfer: "Yeni sorularla yardımsız deneme", review: "Gecikmeli yardımsız deneme",
};
const CONTEXT_LABELS: Record<ModuleSummary["scope"]["applicable_contexts"][number], string> = {
  formal_learning: "Örgün öğrenme", exam_preparation: "Sınava hazırlık",
  higher_education: "Yükseköğretimde pekiştirme", daily_or_professional: "Gündelik veya mesleki öğrenme",
};
const PREFERENCES_KEY = "eristem:learning-preferences:v1";
type Preferences = { detail: "short" | "detailed"; rate: number; largeText: boolean };
function readPreferences(): Preferences {
  const fallback: Preferences = { detail: "short", rate: 1, largeText: false };
  try {
    const raw = window.localStorage.getItem(PREFERENCES_KEY);
    if (!raw || raw.length > 1000) return fallback;
    const data = JSON.parse(raw) as Partial<Preferences> | null;
    if (!data || typeof data !== "object") return fallback;
    return { detail: data.detail === "detailed" ? "detailed" : "short",
      rate: [0.75, 1, 1.25, 1.5, 2].includes(Number(data.rate)) ? Number(data.rate) : 1,
      largeText: data.largeText === true };
  } catch { return fallback; }
}
function loadProgress(module: LearningModule): LearningProgress {
  try { return parseLearningProgress(window.localStorage.getItem(learningKey(module.id, module.version)), module.exercises.map(item => item.id)); }
  catch { return {}; }
}
function pendingLearning(module: LearningModule, progress: LearningProgress): LearningExercise | undefined {
  return module.exercises.find(item => item.stage !== "review" && !progress[item.id]?.completed);
}
function readableDate(value: number): string {
  return new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium", timeStyle: "short" }).format(value);
}

function ModuleSession({ module, api, preferences, onBack }: {
  module: LearningModule; api: string; preferences: Preferences; onBack: () => void;
}) {
  const [progress, setProgress] = useState<LearningProgress>(() => loadProgress(module));
  const progressRef = useRef(progress);
  const [currentId, setCurrentId] = useState<string | null>(() => pendingLearning(module, loadProgress(module))?.id ?? null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<LearningFeedback | null>(null);
  const [requestError, setRequestError] = useState("");
  const [checking, setChecking] = useState(false);
  const [storageStatus, setStorageStatus] = useState("");
  const [lessonOpen, setLessonOpen] = useState(false);
  const [now, setNow] = useState(Date.now);
  const heading = useRef<HTMLHeadingElement>(null);
  const answerField = useRef<HTMLInputElement>(null);
  const feedbackRegion = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const active = module.exercises.find(item => item.id === currentId);
  const record = active ? progress[active.id] : undefined;
  const locked = record?.completed === true;
  const lesson = module.lessons.find(item => item.id === active?.lesson_id);
  const { speak, stop, status: voiceStatus } = useLearningSpeech(preferences.rate);
  const dueAt = reviewAvailableAt(module.exercises, progress, module.review_delay_hours);
  const reviewPending = module.exercises.filter(item => item.stage === "review" && !progress[item.id]?.completed);
  const reviewDue = dueAt !== null && dueAt <= now;

  useEffect(() => {
    heading.current?.focus();
    stop();
  }, [currentId, stop]);
  useEffect(() => {
    if (locked && feedback) feedbackRegion.current?.focus();
  }, [locked, feedback]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => { window.clearInterval(timer); request.current?.abort(); };
  }, []);

  function commit(next: LearningProgress) {
    progressRef.current = next;
    setProgress(next);
    try {
      window.localStorage.setItem(learningKey(module.id, module.version), JSON.stringify(next));
      setStorageStatus("");
    } catch { setStorageStatus("Bu cihazda ilerleme kaydedilemedi. Bu oturumda devam edebilirsiniz; sayfa yenilendiğinde kayıt kaybolabilir."); }
  }
  function move(id: string | null) {
    if (inFlight.current) return;
    stop(); setCurrentId(id); setAnswer(""); setFeedback(null); setRequestError(""); setLessonOpen(false);
  }
  function advance() {
    if (!active) return;
    const next = active.stage === "review"
      ? module.exercises.find(item => item.stage === "review" && !progress[item.id]?.completed)
      : pendingLearning(module, progress);
    move(next?.id ?? null);
  }
  function skip() {
    if (!active || inFlight.current) return;
    const next = skipLearningExercise(progress, active.id, Date.now());
    commit(next);
    const following = active.stage === "review"
      ? module.exercises.find(item => item.stage === "review" && !next[item.id]?.completed)
      : pendingLearning(module, next);
    move(following?.id ?? null);
  }
  async function check(event: FormEvent) {
    event.preventDefault();
    if (!active || locked || inFlight.current || !answer.trim()) return;
    inFlight.current = true; setChecking(true); setRequestError("");
    const helpAtSubmission = progressRef.current[active.id]?.helpUsed ?? false;
    const controller = new AbortController();
    request.current = controller;
    try {
      const response = await fetch(`${api}/v1/student/learning/modules/${encodeURIComponent(module.id)}/exercises/${encodeURIComponent(active.id)}/check`, {
        method: "POST", headers: { "X-Role": "student", "Content-Type": "application/json" },
        body: JSON.stringify({ answer, attempt: Math.min((record?.attempts ?? 0) + 1, 100) }), signal: controller.signal,
      });
      if (!response.ok) throw new Error("check");
      const result = await response.json() as LearningFeedback;
      if (controller.signal.aborted) return;
      setFeedback(result);
      if (result.valid) commit(recordLearningAnswer(progressRef.current, active, result.correct, !!result.hint, Date.now(), helpAtSubmission));
      if (!result.valid || (active.stage === "guided" && !result.correct)) answerField.current?.focus();
      setNow(Date.now());
    } catch {
      if (!controller.signal.aborted) setRequestError("Yanıt kontrol edilemedi. Yanıtınız korunuyor; yeniden deneyin.");
    } finally {
      if (!controller.signal.aborted) { inFlight.current = false; setChecking(false); }
    }
  }
  function restart() {
    if (inFlight.current || !window.confirm("Bu içeriğin cihazdaki çalışma kaydı silinip yeni bir çalışma başlatılsın mı?")) return;
    try { window.localStorage.removeItem(learningKey(module.id, module.version)); setStorageStatus(""); }
    catch { setStorageStatus("Cihazdaki kayıt silinemedi. Bu oturumdaki ilerleme sıfırlandı."); }
    progressRef.current = {}; setProgress({}); move(module.exercises.find(item => item.stage !== "review")?.id ?? null);
  }

  return <>
    <button type="button" onClick={() => { stop(); onBack(); }}>Öğrenme konularına dön</button>
    <h1 ref={heading} tabIndex={-1}>{module.title}{active ? ` — ${STAGE_LABELS[active.stage]}` : " — Çalışma özeti"}</h1>
    <p>{module.goal}</p>
    <p className="source-note">{module.scope.context_note}</p>
    <p className="notice">{module.provenance}</p>
    <p role="status">{storageStatus}</p>
    {active ? <section className="study-card" aria-labelledby="learning-question-title">
      <p className="learning-stage">{STAGE_LABELS[active.stage]} · Soru {module.exercises.filter(item => item.stage === active.stage).findIndex(item => item.id === active.id) + 1} / {module.exercises.filter(item => item.stage === active.stage).length}</p>
      <h2 id="learning-question-title">{active.topic}</h2>
      <p>{active.stage === "guided" ? "Açıklamayı ihtiyaç duyduğunuzda açın. Yanlış yanıtta ilişkiyi kontrol etmenize yardımcı bir ipucu sunulur." : "İlk yanıtınızı deneyin. Bu bölümde açıklama ve ipucu sunulmaz; bir geçerli yanıtın ardından ilerleyebilirsiniz. Soruyu geçmek başarı sayılmaz."}</p>

      {active.stage === "guided" && lesson && <details className="learning-lesson" open={lessonOpen} onToggle={event => {
        const opened = event.currentTarget.open;
        setLessonOpen(opened);
        if (opened && !progressRef.current[active.id]?.helpUsed && !locked) commit(markLearningHelp(progressRef.current, active.id));
      }}>
        <summary>Kavramı keşfet: {lesson.title}</summary>
        <p>{lesson.short_description}</p>
        {preferences.detail === "detailed" && <ol>{lesson.detailed_description.map((text, index) => <li key={index}>{text}</li>)}</ol>}
        <button type="button" onClick={() => speak([lesson.short_description, ...(preferences.detail === "detailed" ? lesson.detailed_description : [])].join(" "))}>Açıklamayı seslendir</button>
        {preferences.detail === "short" && <details><summary>Ayrıntılı ilişki açıklaması</summary><ol>{lesson.detailed_description.map((text, index) => <li key={index}>{text}</li>)}</ol><button type="button" onClick={() => speak(lesson.detailed_description.join(" "))}>Ayrıntıyı seslendir</button></details>}
        <details><summary>İsteğe bağlı nesne veya listeyle keşif</summary><p>{module.materials}</p><ol>{lesson.exploration.map((text, index) => <li key={index}>{text}</li>)}</ol><button type="button" onClick={() => speak([...lesson.exploration, lesson.limitation].join(" "))}>Keşif yönergesini seslendir</button></details>
        <p className="notice">{lesson.limitation}</p>
      </details>}

      <p id="learning-question" className="practice-question" lang="tr"><span aria-hidden="true">{active.question}</span><span className="sr-only">{active.spoken_question}</span></p>
      <div className="student-actions"><button type="button" onClick={() => speak(active.spoken_question)}>Soruyu seslendir</button><button type="button" onClick={stop}>Sesi durdur</button></div>
      <p role="status">{voiceStatus}</p>
      <form onSubmit={event => void check(event)}>
        {active.answer_kind === "choice" ? <fieldset disabled={checking || locked} aria-describedby="learning-question learning-feedback">
          <legend>Yanıtınız</legend>
          {active.choices.map((option, index) => <label className="learning-option" key={option.id}>
            <input ref={index === 0 ? answerField : undefined} type="radio" name="learning-choice" value={option.id} checked={answer === option.id} onChange={() => setAnswer(option.id)} />
            <span>{option.text}</span>
          </label>)}
        </fieldset> : <>
          <label htmlFor="learning-answer">Sonuç kümesi</label>
          <p id="learning-format">{active.answer_format} Standart klavye veya cihazınızın Braille girişini kullanabilirsiniz.</p>
          <input id="learning-answer" ref={answerField} type="text" lang="tr" inputMode="text" autoComplete="off" spellCheck={false} maxLength={100}
            aria-describedby="learning-question learning-format learning-feedback" value={answer} onChange={event => setAnswer(event.target.value)} disabled={checking || locked} required />
        </>}
        {!locked && <button type="submit" disabled={checking || !answer.trim()}>{checking ? "Kontrol ediliyor…" : "Yanıtı gönder"}</button>}
      </form>
      <div id="learning-feedback" ref={feedbackRegion} tabIndex={-1} role="status" aria-live="polite" aria-atomic="true">
        {feedback && <><p>{feedback.message}</p>{feedback.hint && <p>İpucu: {feedback.hint}</p>}</>}
        {record?.attempts && record.firstCorrect === true ? <p>{record.firstHelpUsed ? "İlk yanıtınız açıklama yardımıyla doğruydu." : "İlk yanıtınız uygulama yardımı almadan doğruydu."}</p> : null}
        {locked && record?.firstCorrect === false && active.stage === "guided" && <p>{record.helpUsed ? "İpucu veya açıklamayla çalışmayı tamamladınız." : "Yeniden deneyerek çalışmayı tamamladınız."} İlk yanıtınız ayrı tutulur.</p>}
        {feedback?.error_kind === "format" && <p>Bu bir giriş biçimi sorunudur; geçerli yanıt denemesi olarak sayılmadı.</p>}
        {requestError && <p>{requestError}</p>}
      </div>
      {feedback?.hint && <button type="button" onClick={() => speak(feedback.hint ?? "")}>İpucunu seslendir</button>}
      <div className="student-actions">{locked ? <button type="button" onClick={advance}>Sonraki adıma geç</button> : <button type="button" disabled={checking} className="learning-secondary" onClick={skip}>Bu soruyu geç</button>}</div>
    </section> : <section className="study-card" aria-labelledby="learning-summary-title">
      <h2 id="learning-summary-title">Çalışma sonuçları</h2>
      <p>Bu sayılar cihazınızdaki çalışma gözlemleridir; sınav notu veya kalıcı öğrenme kanıtı değildir.</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Çalışma sonuçları tablosu; yatay kaydırılabilir"><table className="learning-results"><caption>İlk yanıtlar, yardım ve geçilen sorular ayrı gösterilir</caption><thead><tr><th scope="col">Bölüm</th><th scope="col">Yanıt verilen</th><th scope="col">İlk yanıtta doğru</th><th scope="col">İlk yanıtta yardımsız doğru</th><th scope="col">Yardım kullanılan</th><th scope="col">Geçilen</th></tr></thead><tbody>
        {(["baseline", "guided", "transfer", "review"] as LearningStage[]).map(stage => {
          const result = stageResults(module.exercises, progress, stage);
          return <tr key={stage}><th scope="row">{STAGE_LABELS[stage]}</th><td>{result.answered} / {result.total}</td><td>{result.firstCorrect}</td><td>{result.independent}</td><td>{result.helped}</td><td>{result.skipped}</td></tr>;
        })}
      </tbody></table></div>
      {dueAt !== null && reviewPending.length > 0 && <>
        <p>{reviewDue ? "Farklı sorularla gecikmeli denemeniz hazır." : `Farklı sorularla gecikmeli deneme ${readableDate(dueAt)} itibarıyla açılacak (${module.review_delay_hours} saat sonra).`}</p>
        <button type="button" disabled={!reviewDue} onClick={() => move(reviewPending[0]?.id ?? null)}>Gecikmeli denemeyi {reviewPending.length < module.exercises.filter(item => item.stage === "review").length ? "sürdür" : "başlat"}</button>
        <p>Bu içeriği daha sonra tekrar açarak devam edebilirsiniz. Araştırma oturumunda aradaki başka çalışmalar da ayrıca dikkate alınmalıdır.</p>
      </>}
      {reviewPending.length === 0 && <p>Gecikmeli deneme tamamlandı. Sonuçları ön bilgi ve ilk yardımsız denemeyle birlikte inceleyebilirsiniz.</p>}
      <button type="button" className="learning-secondary" onClick={restart}>Kaydı sil ve yeni çalışma başlat</button>
    </section>}
    <details className="student-help"><summary>Erişimde veya anlatımda zorlandım</summary>
      <p>Yanıtın yanlış olması her zaman kavram eksikliği anlamına gelmez. Soruyu veya seçenekleri okuyamadıysanız soruyu geçebilirsiniz. Öğretmeninize hangi adımda zorlandığınızı anlatın: metni bulma, anlatımı anlama, ilişkiyi kurma veya yanıt girme.</p>
      <p>Bu sürüm öğretmene otomatik bildirim göndermez. Braille girişi cihazınıza bağlıdır; matematiksel Braille çıktısı bu atölyede sunulmuyor.</p>
    </details>
  </>;
}

export function LearningExperience({ api, onBack }: { api: string; onBack: () => void }) {
  const [catalog, setCatalog] = useState<ModuleSummary[]>([]);
  const [module, setModule] = useState<LearningModule | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [preferences, setPreferences] = useState<Preferences>(readPreferences);
  const [preferencesStatus, setPreferencesStatus] = useState("");
  const [retry, setRetry] = useState(0);
  const request = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${api}/v1/student/learning/modules`, { headers: { "X-Role": "student" }, signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("catalog"); return response.json() as Promise<ModuleSummary[]>; })
      .then(items => { if (!controller.signal.aborted) { setCatalog(items); setStatus(""); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Öğrenme konuları yüklenemedi. Bağlantıyı kontrol edip yeniden deneyin."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); request.current?.abort(); };
  }, [api, retry]);
  useEffect(() => { if (!module) heading.current?.focus(); }, [module]);

  function updatePreferences(next: Preferences) {
    setPreferences(next);
    try { window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next)); setPreferencesStatus(""); }
    catch { setPreferencesStatus("Tercihler bu oturumda geçerli; cihazda kaydedilemedi."); }
  }
  async function openModule(id: string) {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setLoading(true); setStatus("Öğrenme içeriği yükleniyor.");
    try {
      const response = await fetch(`${api}/v1/student/learning/modules/${encodeURIComponent(id)}`, { headers: { "X-Role": "student" }, signal: controller.signal });
      if (!response.ok) throw new Error("module");
      const data = await response.json() as LearningModule;
      if (!controller.signal.aborted) { setModule(data); setStatus(""); }
    } catch { if (!controller.signal.aborted) setStatus("İçerik yüklenemedi. Konuyu tekrar seçebilirsiniz."); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }
  function clearDeviceData() {
    if (!window.confirm("Bu cihazdaki tüm öğrenme atölyesi kayıtları ve tercihler silinsin mi?")) return;
    try {
      const keys = Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i));
      keys.filter((key): key is string => !!key && (key.startsWith(LEARNING_PREFIX) || key === PREFERENCES_KEY)).forEach(key => window.localStorage.removeItem(key));
      setPreferences({ detail: "short", rate: 1, largeText: false }); setStatus("Öğrenme atölyesi kayıtları ve tercihleri bu cihazdan silindi.");
    } catch { setStatus("Cihazdaki kayıtlar tamamen silinemedi. Tarayıcınızın site verisi ayarlarını kontrol edin."); }
  }

  return <><a className="skip" href="#learning-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Öğrenme atölyesi</p></header>
    <main id="learning-main" className={`student-shell learning-shell${preferences.largeText ? " learning-large-text" : ""}`}>
      <button type="button" onClick={() => { request.current?.abort(); onBack(); }}>Kütüphaneye dön</button>
      <details className="learning-preferences"><summary>Anlatım ve görünüm tercihleri</summary>
        <label htmlFor="learning-detail">Açıklama ayrıntısı<select id="learning-detail" value={preferences.detail} onChange={event => updatePreferences({ ...preferences, detail: event.target.value === "detailed" ? "detailed" : "short" })}><option value="short">Kısa; ayrıntıyı isteyince aç</option><option value="detailed">Ayrıntılı açıklama</option></select></label>
        <label htmlFor="learning-rate">Uygulamanın seslendirme hızı<select id="learning-rate" value={preferences.rate} onChange={event => updatePreferences({ ...preferences, rate: Number(event.target.value) })}>{[0.75, 1, 1.25, 1.5, 2].map(rate => <option value={rate} key={rate}>{rate.toLocaleString("tr-TR")} kat</option>)}</select></label>
        <label className="learning-option"><input type="checkbox" checked={preferences.largeText} onChange={event => updatePreferences({ ...preferences, largeText: event.target.checked })} /><span>Daha büyük metin</span></label>
        <p>Metin her zaman erişilebilir. Ses yalnız siz başlattığınızda çalar; cihazınızın ekran okuyucusunu da kullanabilirsiniz. Tercihlerinizi istediğiniz zaman değiştirebilirsiniz.</p><p role="status">{preferencesStatus}</p>
      </details>
      {module ? <ModuleSession key={`${module.id}:${module.version}`} module={module} api={api} preferences={preferences} onBack={() => setModule(null)} /> : <>
        <h1 ref={heading} tabIndex={-1}>Neyi öğrenmek istersiniz?</h1>
        <p>Önce bildiklerinizi yoklayın, ardından ilişkileri keşfedip yeni sorularda deneyin. Soruları geçebilir, açıklama düzeyini seçebilir ve kaldığınız yerden devam edebilirsiniz.</p>
        <p className="notice">Çalışma kayıtları ve tercihler yalnız bu tarayıcıda tutulur. Yanıt metinleri kaydedilmez. Paylaşılan cihazda aşağıdaki silme düğmesini kullanın.</p>
        <p role="status">{loading ? status || "Öğrenme konuları yükleniyor." : status}</p>
        {!loading && catalog.length === 0 && <button type="button" onClick={() => { setLoading(true); setRetry(value => value + 1); }}>Yeniden yükle</button>}
        <ul className="learning-catalog">{catalog.map(item => <li className="study-card" key={item.id}><h2>{item.title}</h2><p>{item.goal}</p><p><strong>Çalışma bağlamları:</strong> {item.scope.applicable_contexts.map(context => CONTEXT_LABELS[context]).join(", ")}.</p><p>{item.materials}</p><details><summary>Temsil ve erişim seçenekleri</summary><p>{item.scope.context_note}</p><ul>{item.scope.representation_options.map(option => <li key={option}>{option}</li>)}</ul></details><button type="button" disabled={loading} onClick={() => void openModule(item.id)}>{item.title}: çalışmayı aç</button></li>)}</ul>
        <button type="button" className="learning-secondary" onClick={clearDeviceData}>Bu cihazdaki atölye kayıtlarını ve tercihleri sil</button>
      </>}
    </main>
  </>;
}
