import { useEffect, useMemo, useState } from "react";
import { QuestionBankQuestion, type QuestionBankQuestionData, type QuestionBankUnit } from "./QuestionBankQuestion";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

type Context = { topic: string | null; test_name: string | null; test_number: number | null };
type Summary = { id: string; number: number; page: number; question_type: string; context: Context };
const headers = { "X-Role": "student" };

export function QuestionBankStudent({ api, onBack }: { api: string; onBack: () => void }) {
  const [list, setList] = useState<Summary[]>([]);
  const [index, setIndex] = useState(0);
  const [topicFilter, setTopicFilter] = useState("");
  const [testFilter, setTestFilter] = useState("");
  const [question, setQuestion] = useState<QuestionBankQuestionData | null>(null);
  const [units, setUnits] = useState<QuestionBankUnit[]>([]);
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
    void fetch(`${api}/v1/question-bank/student/questions/${item.id}`, { headers, signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<{ question: QuestionBankQuestionData; units: QuestionBankUnit[] }>; })
      .then(value => { if (!controller.signal.aborted) { setQuestion(value.question); setUnits(value.units); setStatus(`PDF sayfası ${item.page}, soru ${item.number}.`); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Soru yüklenemedi."); });
    return () => controller.abort();
  }, [api, index, visibleList]);
  const chooseIndex = (next: number) => { setIndex(next); setStatus(`Soru ${visibleList[next]?.number ?? ""} yükleniyor.`); };
  const active = visibleList[index];
  return <><a className="skip" href="#question-bank-student">İçeriğe geç</a><header><p className="brand">Tarih soru bankası</p></header><main id="question-bank-student" className="student-shell learning-shell"><button type="button" onClick={onBack}>← Kütüphaneye dön</button><p className="eyebrow">SORU ÇALIŞMASI</p><h1>Bir soruya odaklan.</h1><p className="notice">Yalnız kaynakla doğrulanmış sorular sunulur. Şıkları hazır olduğunda açabilir, her bölümü ayrı dinleyebilirsin. Doğrulanmış cevap anahtarı olmadan puanlama yapılmaz.</p><p role="status">{status}</p>{list.length > 0 && <nav className="question-picker" aria-label="Soru seçimi"><p>{visibleList.length} onaylı soru bu seçime uyuyor.</p><label>Konu seç<select value={topicFilter} onChange={event => { setTopicFilter(event.target.value); setTestFilter(""); setIndex(0); }}><option value="">Tüm konular</option>{topics.map(topic => <option key={topic} value={topic}>{topic}</option>)}</select></label><label>Test seç<select value={testFilter} onChange={event => { setTestFilter(event.target.value); setIndex(0); }}><option value="">Tüm testler</option>{testOptions.map(([key, context]) => <option key={key} value={key}>{context.test_name}{context.test_number ? ` ${context.test_number}` : ""}</option>)}</select></label>{visibleList.length > 0 && <label>Soruya git<select value={index} onChange={event => chooseIndex(Number(event.target.value))}>{visibleList.map((item, position) => <option key={item.id} value={position}>Sayfa {item.page} · Soru {item.number}</option>)}</select></label>}</nav>}{active && <p className="source-note">Konu: {active.context.topic ?? "Başlık doğrulanmadı"} · {active.context.test_name ?? "Test türü doğrulanmadı"}{active.context.test_number ? ` ${active.context.test_number}` : ""}</p>}{question?.id === active?.id && units.length > 0 && <QuestionBankQuestion key={question.id} question={question} units={units} api={api} onBack={onBack} onPrevious={index > 0 ? () => chooseIndex(index - 1) : undefined} onNext={index < visibleList.length - 1 ? () => chooseIndex(index + 1) : undefined} />}{loaded && !list.length && <section className="empty-state" aria-label="Henüz soru yok"><h2>Çalışma alanı hazırlanıyor</h2><p>Öğretmen kaynak PDF'deki soruları ve görselleri kontrol ettikten sonra bu alanda görünecekler.</p><VoiceCommandPanel title="Soru bankasında sesli yönlendirme" examples={["kütüphaneye dön"]} available={["back"]} onCommand={command => { if (command.kind === "back") onBack(); }} /><button type="button" onClick={onBack}>Kütüphaneye dön</button></section>}{loaded && list.length > 0 && !visibleList.length && <p className="empty-state">Bu konu ve test için henüz onaylı soru yok. Başka bir seçim yapın.</p>}</main></>;
}
