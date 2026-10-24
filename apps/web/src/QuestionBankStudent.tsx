import { useEffect, useMemo, useState } from "react";
import { QuestionBankQuestion, type QuestionBankQuestionData, type QuestionBankUnit } from "./QuestionBankQuestion";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

type Context = { topic: string | null; test_name: string | null; test_number: number | null };
type Summary = { id: string; number: number; page: number; question_type: string; context: Context };
type QuestionPayload = { question: QuestionBankQuestionData; units: QuestionBankUnit[]; audio_segments: { id: string; spoken_text: string }[] };
const headers = { "X-Role": "student" };
const questionCache = new Map<string, QuestionPayload>();
const MAX_CACHED_QUESTIONS = 40;

function rememberQuestion(id: string, value: QuestionPayload) {
  if (questionCache.has(id)) questionCache.delete(id);
  questionCache.set(id, value);
  if (questionCache.size > MAX_CACHED_QUESTIONS) questionCache.delete(questionCache.keys().next().value!);
}

export function QuestionBankStudent({ api, onBack }: { api: string; onBack: () => void }) {
  const [list, setList] = useState<Summary[]>([]);
  const [index, setIndex] = useState(0);
  const [topicFilter, setTopicFilter] = useState("");
  const [testFilter, setTestFilter] = useState("");
  const [question, setQuestion] = useState<QuestionBankQuestionData | null>(null);
  const [units, setUnits] = useState<QuestionBankUnit[]>([]);
  const [audioSegments, setAudioSegments] = useState<QuestionPayload["audio_segments"]>([]);
  const [status, setStatus] = useState("Onaylı sorular yükleniyor.");
  const [loaded, setLoaded] = useState(false);
  const topics = useMemo(() => [...new Set(list.map(item => item.context.topic).filter((value): value is string => Boolean(value)))], [list]);
  const testOptions = useMemo(() => [...new Map(list.filter(item => !topicFilter || item.context.topic === topicFilter)
    .filter(item => item.context.test_name)
    .map(item => [`${item.context.test_name}:${item.context.test_number ?? ""}`, item.context])).entries()], [list, topicFilter]);
  const visibleList = useMemo(() => list.filter(item => (!topicFilter || item.context.topic === topicFilter)
    && (!testFilter || `${item.context.test_name}:${item.context.test_number ?? ""}` === testFilter)), [list, topicFilter, testFilter]);
  useEffect(() => {
    void fetch(`${api}/v1/question-bank/student/questions`, { headers }).then(response => {
      if (!response.ok) throw Error(); return response.json() as Promise<Summary[]>;
    }).then(value => { setList(value); setLoaded(true); setStatus(value.length ? `${value.length} onaylı soru hazır.` : "Öğretmen tarafından onaylanmış soru henüz yok. Taslaklar öğrenciye açılmaz."); })
      .catch(() => { setLoaded(true); setStatus("Soru bankası hizmeti kullanılamıyor."); });
  }, [api]);
  useEffect(() => {
    const item = visibleList[index];
    if (!item) return;
    const controller = new AbortController();
    const cached = questionCache.get(item.id);
    if (cached) {
      queueMicrotask(() => {
        if (controller.signal.aborted) return;
        setQuestion(cached.question); setUnits(cached.units); setAudioSegments(cached.audio_segments); setStatus(`PDF sayfası ${item.page}, soru ${item.number}.`);
      });
      return () => controller.abort();
    }
    void fetch(`${api}/v1/question-bank/student/questions/${item.id}`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<QuestionPayload>; })
      .then(value => { if (!controller.signal.aborted) { rememberQuestion(item.id, value); setQuestion(value.question); setUnits(value.units); setAudioSegments(value.audio_segments); setStatus(`PDF sayfası ${item.page}, soru ${item.number}.`); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Soru yüklenemedi."); });
    return () => controller.abort();
  }, [api, index, visibleList]);
  const chooseIndex = (next: number) => { setIndex(next); setStatus(`Soru ${visibleList[next]?.number ?? ""} yükleniyor.`); };
  const active = visibleList[index];
  return <><a className="skip" href="#question-bank-student">İçeriğe geç</a><header><p className="brand">Tarih soruları</p></header>
    <main id="question-bank-student" className="student-shell learning-shell question-study-shell">
      <button type="button" className="quiet-button" onClick={onBack}>← Kütüphaneye dön</button>
      <h1 tabIndex={-1}>Soruyu çöz</h1>
      {active && <p className="question-context">{active.context.topic ?? "Tarih"} · PDF s. {active.page} · {index + 1}/{visibleList.length}</p>}
      {list.length > 0 && <details className="question-switcher"><summary>Soru veya konu değiştir</summary>
        <nav className="question-picker" aria-label="Soru seçimi">
          <label>Konu<select value={topicFilter} onChange={event => { setTopicFilter(event.target.value); setTestFilter(""); setIndex(0); }}><option value="">Tüm konular</option>{topics.map(topic => <option key={topic} value={topic}>{topic}</option>)}</select></label>
          <label>Test<select value={testFilter} onChange={event => { setTestFilter(event.target.value); setIndex(0); }}><option value="">Tüm testler</option>{testOptions.map(([key, context]) => <option key={key} value={key}>{context.test_name}{context.test_number ? ` ${context.test_number}` : ""}</option>)}</select></label>
          {visibleList.length > 0 && <label>Soru<select value={index} onChange={event => chooseIndex(Number(event.target.value))}>{visibleList.map((item, position) => <option key={item.id} value={position}>Sayfa {item.page} · Soru {item.number}</option>)}</select></label>}
        </nav></details>}
      <p role="status" className="question-load-status">{status}</p>
      {question?.id === active?.id && units.length > 0 && <QuestionBankQuestion key={question.id} question={question} units={units} segments={audioSegments} api={api} onPrevious={index > 0 ? () => chooseIndex(index - 1) : undefined} onNext={index < visibleList.length - 1 ? () => chooseIndex(index + 1) : undefined} />}
      {loaded && !list.length && <section className="empty-state" aria-label="Henüz soru yok"><h2>Çalışma alanı hazırlanıyor</h2><p>Öğretmen soruları kaynak PDF ile kontrol ettiğinde burada görünecekler.</p><VoiceCommandPanel title="Sesli yönlendirme" examples={["kütüphaneye dön"]} available={["back"]} onCommand={command => { if (command.kind === "back") onBack(); }} /></section>}
      {loaded && list.length > 0 && !visibleList.length && <p className="empty-state">Bu seçimde henüz onaylı soru yok. Başka bir konu veya test seç.</p>}
    </main></>;
}
