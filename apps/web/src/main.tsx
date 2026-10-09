import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { dueUnitIds, parseProgress, progressKey, progressPrefix, recordSelfReview, type ReviewProgress } from "./study_progress";
import { turkishVoices } from "./speech_voices";
import { cellNavigationLabel, cellSpeechLabel } from "./table_reading";
import { SetPractice } from "./SetPractice";
import { ExamPractice } from "./ExamPractice";
import { LearningManagement } from "./LearningManagement";

type Block = { id: string; kind: "heading" | "paragraph" | "formula-display"; text?: string; latex?: string; mathml?: string; status: string; revision: number; source: { page: number; bbox: number[]; source_checksum: string; extraction_step: string }; validation: { confidence: number; reasons: string[] } };
type Document = { id: string; title: string; license_notice: string; published_revision: number; blocks: Block[] };
type ReadingUnit = { id: string; kind: string; navigation_label: string; spoken_text: string; braille_available: boolean; reading_order: number };
type ReadingPlanResponse = { plan: { units: ReadingUnit[] }; unavailable_block_ids: string[] };
type StudentDocumentSummary = { id: string; title: string; published_revision: number; block_count: number };
type StudentTable = { id: string; cells: TableCell[] };
// Üretimde istekler aynı-origin nginx proxy'si üzerinden gider; uzak/IDE önizlemelerinde
// tarayıcının kendi localhost'una yanlışlıkla bağlanılmaz.
const API = import.meta.env.VITE_API_URL ?? "/api";
function Formula({ block, reading, onSelect }: { block: Block; reading?: ReadingUnit; onSelect: () => void }) {
  return <section id={block.id} className="formula" aria-labelledby={`${block.id}-label`} tabIndex={0} onFocus={onSelect}><h2 id={`${block.id}-label`}>Formül</h2><p>{reading ? reading.spoken_text : "Bu formülün doğrulanmış Türkçe okunuşu henüz hazır değil. Teknik gösterim erişilebilir okuma yerine kullanılmaz."}</p><p>{reading ? "Formülü seslendirmek için seçili birimi oku düğmesini kullanın. Matematiksel Braille henüz sunulmuyor." : ""}</p><details><summary>Kaynak ve doğrulama bilgisi</summary><p>Sayfa {block.source.page}, kutu: {block.source.bbox.join(", ")}. Güven: %{Math.round(block.validation.confidence * 100)}.</p></details></section>;
}

function PublishedTableView({ table, onSpeak }: { table: StudentTable; onSpeak: (spoken: string | null, label: string) => void }) {
  const rows = [...new Set(table.cells.map(cell => cell.row))].sort((a, b) => a - b);
  const columns = [...new Set(table.cells.map(cell => cell.column))].sort((a, b) => a - b);
  const headingRow = rows.find(row => table.cells.some(cell => cell.row === row && cell.role === "header"));
  const ordered = [...table.cells].sort((a, b) => a.row - b.row || a.column - b.column);
  const [cellIndex, setCellIndex] = useState(0);
  const cellRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const focusCell = (index: number) => { const next = Math.max(0, Math.min(ordered.length - 1, index)); setCellIndex(next); const cell = ordered[next]; if (cell) cellRefs.current[`${cell.row}:${cell.column}`]?.focus(); };
  const selected = ordered[cellIndex];
  const selectedLabel = selected ? cellNavigationLabel(selected, table.cells) : "";
  const selectedSpeech = selected ? cellSpeechLabel(selected, table.cells) : null;
  return <section className="published-table" aria-labelledby={`${table.id}-title`}><h2 id={`${table.id}-title`}>Yayımlanmış tablo</h2><p>{rows.length} satır, {columns.length} sütun. Ekran okuyucuyla hücre düğmelerine sağa/sola kaydırarak gidin; önceki/sonraki hücre düğmeleriyle de ilerleyebilirsiniz.</p><div className="table-row-controls"><button type="button" onClick={() => focusCell(cellIndex - 1)} disabled={cellIndex === 0}>Önceki hücre</button><button type="button" onClick={() => focusCell(cellIndex + 1)} disabled={cellIndex >= ordered.length - 1}>Sonraki hücre</button><button type="button" onClick={() => onSpeak(selectedSpeech, selectedLabel)} disabled={!selected}>Seçili hücreyi seslendir</button><span>Hücre {ordered.length ? cellIndex + 1 : 0}/{ordered.length}</span></div><div className="table-scroll"><table><caption>Öğretmen ve onaylayıcı tarafından yayımlanmış tablo</caption><tbody>{rows.map(row => <tr key={row}>{columns.map(column => { const cell = table.cells.find(item => item.row === row && item.column === column); const columnHeader = headingRow !== undefined && table.cells.some(item => item.row === headingRow && item.column === column && item.role === "header"); const rowHeader = table.cells.some(item => item.row === row && item.column === columns[0] && item.role === "header"); const headerIds = [columnHeader && row !== headingRow ? `${table.id}-col-${column}` : "", rowHeader && column !== columns[0] ? `${table.id}-row-${row}` : ""].filter(Boolean).join(" "); const button = cell ? <button type="button" className="table-cell-focus" ref={element => { cellRefs.current[`${row}:${column}`] = element; }} onFocus={() => setCellIndex(ordered.findIndex(item => item.row === row && item.column === column))} aria-label={cellNavigationLabel(cell, table.cells)}>{cell.text || "Boş hücre"}</button> : null; return cell?.role === "header" ? <th key={column} id={row === headingRow ? `${table.id}-col-${column}` : column === columns[0] ? `${table.id}-row-${row}` : undefined} scope={row === headingRow ? "col" : "row"}>{button}</th> : <td key={column} headers={headerIds || undefined}>{button}</td>; })}</tr>)}</tbody></table></div><p>Bir hücrede tanınmayan matematik işareti varsa uygulama ona sesli anlam uydurmaz; kaynak hücre metni ekranda ve ekran okuyucuya açık kalır. Matematiksel Braille henüz sunulmuyor.</p></section>;
}

function Reader({ documentId, onBack }: { documentId: string; onBack: () => void }) {
  const [content, setContent] = useState<Document | null>(null);
  const [plan, setPlan] = useState<ReadingPlanResponse | null>(null);
  const [tables, setTables] = useState<StudentTable[]>([]);
  const [loadStatus, setLoadStatus] = useState("Yayımlanmış belgeler yükleniyor.");
  const [currentUnit, setCurrentUnit] = useState(0);
  const [speechStatus, setSpeechStatus] = useState("Sesli okuma hazırlanıyor.");
  const [rate, setRate] = useState(1);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceURI, setVoiceURI] = useState("");
  const [paused, setPaused] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [braille, setBraille] = useState<{ unitId: string; cells: string; code: string; engine_version: string } | null>(null);
  const [brailleErrorId, setBrailleErrorId] = useState<string | null>(null);
  const [studyMode, setStudyMode] = useState(false);
  const [answerVisible, setAnswerVisible] = useState(false);
  const [progress, setProgress] = useState<ReviewProgress>({});
  const [reviewNow, setReviewNow] = useState(() => Date.now());
  const [studyStatus, setStudyStatus] = useState("Çalışma geçmişi yalnız bu cihazda tutulur.");
  const studyHeading = useRef<HTMLHeadingElement>(null);
  const answerHeading = useRef<HTMLHeadingElement>(null);
  const main = useRef<HTMLElement>(null);
  const approvedAudio = useRef<HTMLAudioElement | null>(null);
  const approvedAudioUrl = useRef<string | null>(null);
  const requestSerial = useRef(0);
  const navigationCursor = useRef({ heading: -1, formula: -1 });
  const speechAvailable = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  useEffect(() => {
    if (!speechAvailable) return;
    const refresh = () => setVoices(turkishVoices(window.speechSynthesis.getVoices()));
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", refresh);
  }, [speechAvailable]);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      fetch(`${API}/v1/student/documents/${encodeURIComponent(documentId)}`, { headers: { "X-Role": "student" }, signal: controller.signal }).then(r => r.ok ? r.json() as Promise<Document> : Promise.reject()),
      fetch(`${API}/v1/student/documents/${encodeURIComponent(documentId)}/reading-plan`, { headers: { "X-Role": "student" }, signal: controller.signal }).then(r => r.ok ? r.json() as Promise<ReadingPlanResponse> : null),
      fetch(`${API}/v1/student/documents/${encodeURIComponent(documentId)}/tables`, { headers: { "X-Role": "student" }, signal: controller.signal }).then(r => r.ok ? r.json() as Promise<StudentTable[]> : Promise.reject()),
    ]).then(([document, readingPlan, publishedTables]) => { if (controller.signal.aborted) return; setContent(document); setPlan(readingPlan); setTables(publishedTables); setLoadStatus(""); setSpeechStatus(readingPlan ? "Doğrulanmış okuma planı hazır." : "Bu belgede sesli okunabilecek doğrulanmış metin yok."); try { setProgress(parseProgress(window.localStorage.getItem(progressKey(document.id, document.published_revision)), readingPlan?.plan.units.map(unit => unit.id) ?? [])); } catch { setProgress({}); setStudyStatus("Bu tarayıcıda çalışma geçmişi saklanamıyor; oturum boyunca çalışabilirsiniz."); } }).catch(() => { if (!controller.signal.aborted) setLoadStatus("Belge yüklenemedi."); });
    return () => controller.abort();
  }, [documentId]);
  useEffect(() => { if (content) main.current?.querySelector<HTMLElement>("h1")?.focus(); }, [content]);
  useEffect(() => { if (studyMode) studyHeading.current?.focus(); }, [studyMode, currentUnit]);
  useEffect(() => { if (answerVisible) answerHeading.current?.focus(); }, [answerVisible]);
  useEffect(() => () => { requestSerial.current += 1; if (speechAvailable) window.speechSynthesis.cancel(); approvedAudio.current?.pause(); if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current); }, [speechAvailable]);
  const stop = useCallback(() => {
    requestSerial.current += 1;
    if (speechAvailable) window.speechSynthesis.cancel();
    approvedAudio.current?.pause();
    approvedAudio.current = null;
    if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current);
    approvedAudioUrl.current = null;
    setPaused(false);
    setIsPlaying(false);
    setSpeechStatus("Sesli okuma durduruldu.");
  }, [speechAvailable]);
  const speak = useCallback(async (index = currentUnit) => {
    const unit = plan?.plan.units[index];
    if (!unit || !content) return;
    const serial = ++requestSerial.current;
    if (speechAvailable) window.speechSynthesis.cancel();
    approvedAudio.current?.pause();
    if (approvedAudioUrl.current) URL.revokeObjectURL(approvedAudioUrl.current);
    approvedAudio.current = null;
    approvedAudioUrl.current = null;
    setPaused(false);
    try {
      const response = await fetch(`${API}/v1/student/documents/${encodeURIComponent(content.id)}/audio/${encodeURIComponent(unit.id)}`, { headers: { "X-Role": "student" } });
      if (serial !== requestSerial.current) return;
      if (response.ok) {
        const url = URL.createObjectURL(await response.blob());
        if (serial !== requestSerial.current) { URL.revokeObjectURL(url); return; }
        const audio = new Audio(url);
        audio.playbackRate = rate;
        approvedAudio.current = audio;
        approvedAudioUrl.current = url;
        audio.onplay = () => { setIsPlaying(true); setSpeechStatus(`${unit.navigation_label} onaylı sesle okunuyor.`); };
        audio.onended = () => { if (serial === requestSerial.current) { setIsPlaying(false); setSpeechStatus(`${unit.navigation_label} tamamlandı.`); } URL.revokeObjectURL(url); if (approvedAudioUrl.current === url) approvedAudioUrl.current = null; };
        audio.onerror = () => { setIsPlaying(false); setSpeechStatus("Onaylı ses dosyası oynatılamadı."); };
        await audio.play();
        return;
      }
      if (response.status !== 404) { setSpeechStatus("Onaylı ses hizmeti yanıt vermedi; otomatik yedeğe geçilmedi."); return; }
    } catch { if (serial !== requestSerial.current) return; setSpeechStatus("Ses hizmetine erişilemedi veya ses oynatılamadı. Tekrar deneyin."); return; }
    if (serial !== requestSerial.current) return;
    if (!speechAvailable) { setSpeechStatus("Bu birim için onaylı ses bulunamadı ve tarayıcı sesli okumayı desteklemiyor."); return; }
    const voice = voices.find(item => item.voiceURI === voiceURI) ?? voices[0];
    if (!voice) { setSpeechStatus("Bu cihazda yerel Türkçe ses bulunamadı. Cihazınızın konuşma ayarlarından Türkçe ses yükleyin veya ekran okuyucunuzla metni okuyun."); return; }
    const utterance = new SpeechSynthesisUtterance(unit.spoken_text);
    utterance.lang = "tr-TR";
    utterance.voice = voice;
    utterance.rate = rate;
    utterance.onstart = () => { setIsPlaying(true); setSpeechStatus(`${unit.navigation_label} okunuyor.`); };
    utterance.onend = () => { setIsPlaying(false); setSpeechStatus(`${unit.navigation_label} tamamlandı.`); };
    utterance.onerror = () => { setIsPlaying(false); setSpeechStatus("Sesli okuma bu birimde tamamlanamadı."); };
    window.speechSynthesis.speak(utterance);
  }, [content, currentUnit, plan, rate, speechAvailable, voices, voiceURI]);
  const speakTableCell = useCallback((spoken: string | null, label: string) => {
    stop();
    if (!spoken) { setSpeechStatus("Bu hücrede desteklenmeyen bir işaret var; yanlış okunuş üretilmedi. Ekran okuyucunuzla kaynak metni inceleyin."); return; }
    if (!speechAvailable) { setSpeechStatus("Bu cihaz sesli okumayı desteklemiyor; hücreye odaklanıp ekran okuyucunuzu kullanın."); return; }
    const voice = voices.find(item => item.voiceURI === voiceURI) ?? voices[0];
    if (!voice) { setSpeechStatus("Yerel Türkçe ses bulunamadı; hücreye odaklanıp ekran okuyucunuzu kullanın."); return; }
    const utterance = new SpeechSynthesisUtterance(spoken);
    utterance.lang = "tr-TR";
    utterance.voice = voice;
    utterance.rate = rate;
    utterance.onstart = () => { setIsPlaying(true); setSpeechStatus(`${label} okunuyor.`); };
    utterance.onend = () => { setIsPlaying(false); setSpeechStatus("Hücre okundu."); };
    utterance.onerror = () => { setIsPlaying(false); setSpeechStatus("Hücre seslendirilemedi."); };
    window.speechSynthesis.speak(utterance);
  }, [rate, speechAvailable, stop, voices, voiceURI]);
  const togglePause = () => {
    if (approvedAudio.current) { if (paused) void approvedAudio.current.play(); else approvedAudio.current.pause(); }
    else if (speechAvailable) { if (paused) window.speechSynthesis.resume(); else window.speechSynthesis.pause(); }
    setPaused(!paused);
    setSpeechStatus(paused ? "Sesli okuma sürüyor." : "Sesli okuma duraklatıldı.");
  };
  const moveUnit = useCallback((change: number) => { if (!plan) return; const next = Math.max(0, Math.min(plan.plan.units.length - 1, currentUnit + change)); stop(); setCurrentUnit(next); setAnswerVisible(false); if (!studyMode) window.document.getElementById(plan.plan.units[next]?.id)?.focus(); }, [currentUnit, plan, stop, studyMode]);
  const unit = plan?.plan.units[currentUnit];
  const startStudy = () => { if (!plan) return; const now = Date.now(); setReviewNow(now); stop(); setAnswerVisible(false); const due = dueUnitIds(plan.plan.units.map(item => item.id), progress, now); const first = plan.plan.units.findIndex(item => item.id === due[0]); if (first >= 0) setCurrentUnit(first); setStudyMode(true); setStudyStatus(due.length ? `${due.length} birim tekrar için hazır.` : "Şu anda zamanı gelmiş tekrar yok; isterseniz bütün birimleri çalışabilirsiniz."); };
  const finishStudy = () => { stop(); setStudyMode(false); setAnswerVisible(false); setStudyStatus("Çalışma modu kapatıldı."); };
  const selfReview = (remembered: boolean) => {
    if (!content || !plan || !unit || !answerVisible) return;
    const now = Date.now();
    setReviewNow(now);
    const next = recordSelfReview(progress, unit.id, remembered, now);
    setProgress(next);
    try { window.localStorage.setItem(progressKey(content.id, content.published_revision), JSON.stringify(next)); setStudyStatus(remembered ? "Hatırladım işaretlendi. Sonraki tekrar zamanı bu cihazda saklandı." : "Tekrar çalışacağım işaretlendi. Bu birim tekrar listesinde kaldı."); }
    catch { setStudyStatus("İşaretleme yalnız bu oturumda kaldı; tarayıcı depolaması kullanılamıyor."); }
    const due = dueUnitIds(plan.plan.units.map(item => item.id), next, now).filter(id => id !== unit.id);
    const nextIndex = plan.plan.units.findIndex(item => item.id === due[0]);
    if (nextIndex >= 0) { stop(); setCurrentUnit(nextIndex); setAnswerVisible(false); }
  };
  const clearStudy = () => { if (!content || !window.confirm("Bu belge için bu cihazdaki çalışma geçmişi silinsin mi?")) return; let cleared = true; try { const prefix = progressPrefix(content.id); const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index)).filter((key): key is string => typeof key === "string" && key.startsWith(prefix)); keys.forEach(key => window.localStorage.removeItem(key)); } catch { cleared = false; } setProgress({}); setStudyStatus(cleared ? "Bu belgenin yerel çalışma geçmişi silindi." : "Oturum geçmişi temizlendi; tarayıcı depolamasının silindiği doğrulanamadı."); };
  useEffect(() => {
    const unit = plan?.plan.units[currentUnit];
    if (!content || !unit?.braille_available) return;
    const controller = new AbortController();
    void fetch(`${API}/v1/student/documents/${encodeURIComponent(content.id)}/braille/${encodeURIComponent(unit.id)}`, { headers: { "X-Role": "student" }, signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("braille"); return response.json() as Promise<{ cells: string; code: string; engine_version: string }>; })
      .then(result => { if (!controller.signal.aborted) setBraille({ ...result, unitId: unit.id }); })
      .catch(() => { if (!controller.signal.aborted) setBrailleErrorId(unit.id); });
    return () => controller.abort();
  }, [content, currentUnit, plan]);
  useEffect(() => { if (approvedAudio.current) approvedAudio.current.playbackRate = rate; }, [rate]);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if (!event.altKey) return; const key = event.key.toLowerCase(); if (!studyMode && (key === "h" || key === "f")) { const kind = key === "h" ? "heading" : "formula"; const targets = Array.from(main.current?.querySelectorAll<HTMLElement>(key === "h" ? "article h1,article h2" : ".formula") ?? []); if (targets.length) { event.preventDefault(); navigationCursor.current[kind] = (navigationCursor.current[kind] + 1) % targets.length; targets[navigationCursor.current[kind]].focus(); } } if (event.key === "ArrowRight") { event.preventDefault(); moveUnit(1); } if (event.key === "ArrowLeft") { event.preventDefault(); moveUnit(-1); } if (key === "r" && (!studyMode || answerVisible)) { event.preventDefault(); void speak(); } }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, [moveUnit, speak, studyMode, answerVisible]);
  if (!content) return <main id="lesson"><button type="button" onClick={onBack}>Kütüphaneye dön</button><h1>Öğrenci okuyucusu</h1><p role="status">{loadStatus}</p></main>;
  const selectedBraille = braille?.unitId === unit?.id ? braille : null;
  const brailleStatus = !unit?.braille_available ? "Bu birimde doğrulanmış metin Braille'i bulunmuyor." : selectedBraille ? "Türkçe edebî metin Braille'i hazır." : brailleErrorId === unit.id ? "Bu birim için doğrulanmış metin Braille'i kullanılamıyor." : "Türkçe metin Braille'i hazırlanıyor.";
  const dueCount = dueUnitIds(plan?.plan.units.map(item => item.id) ?? [], progress, reviewNow).length;
  return <><a className="skip" href="#lesson">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>{studyMode ? <>Tekrar çalışması · <kbd>Alt</kbd>+<kbd>←</kbd>/<kbd>→</kbd> birim değiştir · Kaynak açılınca <kbd>Alt</kbd>+<kbd>R</kbd> oku</> : <>Öğrenci okuyucusu · <kbd>Alt</kbd>+<kbd>H</kbd> başlık · <kbd>Alt</kbd>+<kbd>F</kbd> formül · <kbd>Alt</kbd>+<kbd>R</kbd> oku · <kbd>Alt</kbd>+<kbd>←</kbd>/<kbd>→</kbd> birim değiştir</>}</p></header><main id="lesson" ref={main} tabIndex={-1}><button type="button" onClick={() => { stop(); onBack(); }}>Kütüphaneye dön</button><h1 tabIndex={-1}>{content.title}</h1><p className="notice">{content.license_notice}</p>
    <section className="reader-controls" aria-labelledby="study-title"><h2 id="study-title">Kendini yokla</h2><p>Yalnız yayımlanmış, doğrulanmış metin birimleriyle çalışır. Sorular veya doğru-yanlış notları yapay zekâ tarafından üretilmez; hatırlama durumunu siz işaretlersiniz.</p><p role="status">{studyStatus}</p><p>{dueCount} birim tekrar listesinde.</p><div>{studyMode ? <button type="button" onClick={finishStudy}>Normal okumaya dön</button> : <button type="button" onClick={startStudy} disabled={!unit}>Tekrar çalışmasını başlat</button>}<button type="button" onClick={clearStudy} disabled={!Object.keys(progress).length}>Bu cihazdaki geçmişi sil</button></div><p className="source-note">Yalnız birim kimliği, deneme sayısı ve tekrar zamanı bu tarayıcıda saklanır; metin, yanıt veya ses sunucuya gönderilmez. Paylaşılan cihazda geçmişi silin.</p>
      {studyMode && unit && <div className="study-card"><h3 tabIndex={-1} ref={studyHeading}>Birim {currentUnit + 1}/{plan?.plan.units.length}</h3><p>Bu birimi kaynaktan ne kadar hatırlıyorsunuz? Hazır olduğunuzda doğrulanmış metni açın.</p><div><button type="button" onClick={() => moveUnit(-1)} disabled={currentUnit === 0}>Önceki birim</button><button type="button" onClick={() => moveUnit(1)} disabled={currentUnit >= (plan?.plan.units.length ?? 0) - 1}>Sonraki birim</button><button type="button" onClick={() => setAnswerVisible(true)} disabled={answerVisible}>Kaynak metni göster</button></div>{answerVisible && <div className="study-answer"><h4 tabIndex={-1} ref={answerHeading}>Doğrulanmış kaynak metni</h4><p>{unit.spoken_text}</p><div><button type="button" onClick={() => selfReview(true)}>Hatırladım</button><button type="button" onClick={() => selfReview(false)}>Tekrar çalışacağım</button></div></div>}</div>}
    </section>
    {(!studyMode || answerVisible) && <><section className="reader-controls" aria-labelledby="reader-controls-title"><h2 id="reader-controls-title">Doğrulanmış sesli okuma</h2><p role="status">{speechStatus}</p>{unit && <p>Seçili birim: {unit.navigation_label} · {currentUnit + 1}/{plan?.plan.units.length}</p>}<div><button type="button" onClick={() => moveUnit(-1)} disabled={!plan || currentUnit === 0}>Önceki birim</button><button type="button" onClick={() => void speak()} disabled={!unit}>Seçili birimi oku</button><button type="button" onClick={togglePause} disabled={!isPlaying}>{paused ? "Devam et" : "Duraklat"}</button><button type="button" onClick={stop}>Durdur</button><button type="button" onClick={() => moveUnit(1)} disabled={!plan || currentUnit >= (plan.plan.units.length - 1)}>Sonraki birim</button></div><label className="reader-rate">Okuma hızı <select value={rate} onChange={event => setRate(Number(event.target.value))}><option value="0.75">0,75×</option><option value="1">1×</option><option value="1.25">1,25×</option><option value="1.5">1,5×</option></select></label><label className="reader-rate">Cihazdaki yerel Türkçe ses <select value={voiceURI} onChange={event => setVoiceURI(event.target.value)} disabled={!voices.length}><option value="">{voices.length ? "Önerilen yerel Türkçe ses" : "Yerel Türkçe ses bulunamadı"}</option>{voices.map(voice => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} ({voice.lang})</option>)}</select></label><p className="source-note">Cihaz sesi onaylı model sesi değildir. Yerel Türkçe ses yoksa sistem başka dildeki veya uzak servis sesini otomatik seçmez.</p>{plan?.unavailable_block_ids.length ? <p>Henüz sesli erişime açılmamış matematiksel veya görsel birimler vardır.</p> : null}</section><section className="reader-controls" aria-labelledby="braille-title"><h2 id="braille-title">Türkçe Braille</h2><p role="status">{brailleStatus}</p>{selectedBraille && <><p>Türkçe kabartma yazı, 1. derece · Liblouis {selectedBraille.engine_version}</p><output className="braille-cells" aria-label="Seçili birimin Braille hücreleri">{selectedBraille.cells}</output><button type="button" onClick={() => void navigator.clipboard.writeText(selectedBraille.cells)}>Braille hücrelerini kopyala</button></>}</section></>}
    {!studyMode && <article>{content.blocks.map(block => block.kind === "heading" ? <h2 id={block.id} tabIndex={-1} key={block.id}>{block.text}</h2> : block.kind === "paragraph" ? <p id={block.id} tabIndex={-1} key={block.id}>{block.text}</p> : <Formula key={block.id} block={block} reading={plan?.plan.units.find(item => item.id === block.id && item.kind === "formula")} onSelect={() => { const index = plan?.plan.units.findIndex(item => item.id === block.id) ?? -1; if (index >= 0) setCurrentUnit(index); }} />)}{tables.map(table => <PublishedTableView key={table.id} table={table} onSpeak={speakTableCell} />)}</article>}</main></>;
}

type StudentView = "library" | "reader" | "writing" | "practice" | "exam";

function currentStudentRoute(): { view: StudentView; documentId: string } {
  const url = new URL(window.location.href);
  const view = url.searchParams.get("view");
  const documentId = url.searchParams.get("document") ?? "";
  return { view: view === "reader" && documentId ? "reader" : view === "writing" ? "writing" : view === "practice" ? "practice" : view === "exam" ? "exam" : "library", documentId };
}

function StudentApp() {
  const [route, setRoute] = useState(currentStudentRoute);
  const [documents, setDocuments] = useState<StudentDocumentSummary[]>([]);
  const [catalogStatus, setCatalogStatus] = useState("Yayımlanmış belgeler yükleniyor.");
  const [search, setSearch] = useState("");
  const [writing, setWriting] = useState("");
  const [writingStatus, setWritingStatus] = useState("Bu yazı yalnız bu oturumda tutulur; sunucuya gönderilmez.");
  const writingInput = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API}/v1/student/documents`, { headers: { "X-Role": "student" }, signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("catalog"); return response.json() as Promise<StudentDocumentSummary[]>; })
      .then(items => { if (!controller.signal.aborted) { setDocuments(items); setCatalogStatus(items.length ? "" : "Henüz yayımlanmış belge bulunmuyor."); } })
      .catch(() => { if (!controller.signal.aborted) setCatalogStatus("Belge listesi yüklenemedi."); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const onHistory = () => setRoute(currentStudentRoute());
    window.addEventListener("popstate", onHistory);
    return () => window.removeEventListener("popstate", onHistory);
  }, []);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => window.document.querySelector<HTMLElement>("main h1")?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [route]);
  const navigate = (view: StudentView, documentId = "") => {
    const url = new URL(window.location.href);
    url.searchParams.delete("view"); url.searchParams.delete("document");
    if (view !== "library") url.searchParams.set("view", view);
    if (view === "reader") url.searchParams.set("document", documentId);
    window.history.pushState({ eristemStudentView: true }, "", url);
    setRoute({ view, documentId });
  };
  const back = () => {
    if (window.history.state?.eristemStudentView) window.history.back();
    else {
      const url = new URL(window.location.href);
      url.searchParams.delete("view"); url.searchParams.delete("document");
      window.history.replaceState(null, "", url);
      setRoute({ view: "library", documentId: "" });
    }
  };
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || route.view === "library" || event.target instanceof HTMLTextAreaElement) return;
      event.preventDefault(); back();
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  });
  if (route.view === "reader") return <Reader key={route.documentId} documentId={route.documentId} onBack={back} />;
  if (route.view === "practice") return <SetPractice api={API} onBack={back} />;
  if (route.view === "exam") return <ExamPractice api={API} onBack={back} />;
  if (route.view === "writing") return <><a className="skip" href="#writing-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p></header><main id="writing-main" className="student-shell"><button type="button" onClick={back}>Geri dön</button><h1 tabIndex={-1}>Braille klavyeyle yazma alanı</h1><p>Bu alan standart metin girişidir. Telefonunuzda TalkBack veya VoiceOver açıksa metin alanına odaklanıp çift dokunun; destekleniyorsa cihazınızın Braille giriş yöntemini seçin. Uygulama ekran okuyucu hareketlerini değiştirmez.</p><label htmlFor="student-writing">Yazınız</label><textarea id="student-writing" ref={writingInput} lang="tr" inputMode="text" autoComplete="off" spellCheck={false} value={writing} onChange={event => setWriting(event.target.value)} maxLength={5000} /><p role="status">{writingStatus}</p><div className="student-actions"><button type="button" onClick={() => writingInput.current?.focus()}>Yazı alanına odaklan</button><button type="button" disabled={!writing} onClick={() => { void navigator.clipboard.writeText(writing).then(() => setWritingStatus("Yazı panoya kopyalandı.")).catch(() => setWritingStatus("Panoya kopyalanamadı; metni seçerek kopyalayın.")); }}>Yazıyı kopyala</button><button type="button" disabled={!writing} onClick={() => { if (window.confirm("Bu oturumdaki yazı silinsin mi?")) { setWriting(""); setWritingStatus("Yazı temizlendi."); writingInput.current?.focus(); } }}>Yazıyı temizle</button></div><p className="notice">Bu alan henüz ödev veya mesaj göndermez. Yazı sunucuya kaydedilmez ve sayfa yenilenirse kaybolur.</p></main></>;
  const matches = documents.filter(item => item.title.toLocaleLowerCase("tr").includes(search.toLocaleLowerCase("tr")));
  return <><a className="skip" href="#student-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p><p>Öğrenci kütüphanesi</p></header><main id="student-main" className="student-shell"><h1 tabIndex={-1}>Dersleri seçin</h1><p>Sağa ve sola kaydırarak öğeler arasında gezinin; odaklanan düğmeyi çift dokunarak açın. Bu hareketleri telefonunuzun ekran okuyucusu yönetir.</p><nav aria-label="Ana menü" className="student-menu"><button type="button" onClick={() => navigate("practice")}>Öğrenme atölyesi: kümeler, çember ve uçak</button><button type="button" onClick={() => navigate("exam")}>Sınav erişim provası</button><button type="button" onClick={() => navigate("writing")}>Braille klavyeyle yazma alanı</button></nav><label htmlFor="student-search">Derslerde ara</label><input id="student-search" type="search" lang="tr" value={search} onChange={event => setSearch(event.target.value)} placeholder="Ders adı" /><p role="status">{catalogStatus || `${matches.length} yayımlanmış belge bulundu.`}</p><ul className="student-document-list">{matches.map(item => <li key={item.id}><button type="button" onClick={() => navigate("reader", item.id)}>{item.title} · {item.block_count} bölüm · Okumayı aç</button></li>)}</ul><details className="student-help"><summary>Dokunmatik kullanım yardımı</summary><p>TalkBack ve VoiceOver ile sağa/sola kaydırma öğe seçer, çift dokunma etkinleştirir. Geri dönmek için ekrandaki Geri düğmesini veya cihazın geri hareketini kullanın. Klavyede Escape de geri döner. Yazı girişinde cihazın kendi Braille klavyesini kullanabilirsiniz; dil desteği cihaza bağlıdır.</p></details></main></>;
}

function TeacherReview() {
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [document, setDocument] = useState<Document | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draftText, setDraftText] = useState("");
  const [message, setMessage] = useState("Belge yükleniyor.");
  const [formulaProposal, setFormulaProposal] = useState<{ blockId: string; revision: number; spoken: string } | null>(null);
  const [formulaProposalStatus, setFormulaProposalStatus] = useState("Türkçe okunuş önerisi hazırlanıyor.");
  useEffect(() => {
    void fetch(`${API}/v1/teacher/documents`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((items: TeacherDocument[]) => {
      const source = items.find(item => item.id.startsWith("source-")) ?? items[0]; setDocuments(items); if (source) setDocumentId(source.id);
    }).catch(() => setMessage("Belge listesi yüklenemedi."));
  }, []);
  const load = async (id = documentId) => { if (!id) return; const r = await fetch(`${API}/v1/teacher/documents/${id}`, { headers: { "X-Role": "teacher" } }); const next = await r.json() as Document; setDocument(next); const first = next.blocks.find(b => b.status === "review_required") ?? next.blocks[0]; setPage(first?.source.page ?? 0); setSelectedId(first?.id ?? ""); setDraftText(first?.text ?? ""); setFormulaProposal(null); setFormulaProposalStatus("Türkçe okunuş önerisi hazırlanıyor."); setMessage("Sayfadaki işaretli alanı kaynakla karşılaştırın."); };
  useEffect(() => {
    if (!documentId) return;
    void fetch(`${API}/v1/teacher/documents/${documentId}`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((next: Document) => {
      setDocument(next); const first = next.blocks.find(b => b.status === "review_required") ?? next.blocks[0]; setPage(first?.source.page ?? 0); setSelectedId(first?.id ?? ""); setDraftText(first?.text ?? ""); setMessage("Sayfadaki işaretli alanı kaynakla karşılaştırın.");
    }).catch(() => setMessage("Belge yüklenemedi."));
  }, [documentId]);
  useEffect(() => { if (documentId && page) void fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/preview-metadata`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then(setPageSize).catch(() => setPageSize(null)); }, [documentId, page]);
  useEffect(() => {
    if (!documentId || !page) return;
    let active = true;
    let objectUrl: string | null = null;
    void fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/preview`, { headers: { "X-Role": "teacher" } })
      .then(response => { if (!response.ok) throw new Error("preview"); return response.blob(); })
      .then(blob => { objectUrl = URL.createObjectURL(blob); if (active) setPreviewUrl(objectUrl); })
      .catch(() => { if (active) setPreviewUrl(null); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [documentId, page]);
  const blocks = document?.blocks.filter(b => b.source.page === page) ?? [];
  const selected = blocks.find(b => b.id === selectedId) ?? blocks[0];
  const formulaId = selected?.kind === "formula-display" ? selected.id : "";
  const formulaRevision = selected?.revision;
  useEffect(() => {
    if (!documentId || !formulaId) return;
    const controller = new AbortController();
    void fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${formulaId}/speech-proposal`, { headers: { "X-Role": "teacher" }, signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("unsupported"); return response.json() as Promise<{ block_id: string; expected_revision: number; proposed_spoken_text: string }>; })
      .then(result => { if (!controller.signal.aborted) { setFormulaProposal({ blockId: result.block_id, revision: result.expected_revision, spoken: result.proposed_spoken_text }); setFormulaProposalStatus(""); } })
      .catch(() => { if (!controller.signal.aborted) setFormulaProposalStatus("Bu formül için güvenli otomatik Türkçe okunuş önerisi yok; özel denetim gerekiyor."); });
    return () => controller.abort();
  }, [documentId, formulaId, formulaRevision]);
  const select = (block: Block) => { setSelectedId(block.id); setDraftText(block.text ?? ""); setFormulaProposal(null); setFormulaProposalStatus("Türkçe okunuş önerisi hazırlanıyor."); };
  const submit = async (correct: boolean) => { if (!selected || !documentId) return; const url = correct ? `${API}/v1/teacher/documents/${documentId}/blocks/${selected.id}/text` : `${API}/v1/teacher/documents/${documentId}/blocks/${selected.id}/approve`; const body = correct ? { text: draftText, reason: "Öğretmen kaynak sayfayla karşılaştırarak metni düzeltti.", expected_revision: selected.revision } : { reason: "Öğretmen kaynak sayfayla karşılaştırdı.", expected_revision: selected.revision }; const r = await fetch(url, { method: correct ? "PUT" : "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify(body) }); setMessage(r.ok ? "Taslak güncellendi; yayımlanmadı." : "İşlem tamamlanamadı; sayfayı yenileyin."); if (r.ok) await load(); };
  const approvePage = async () => { if (!documentId || !page || !window.confirm("Bu sayfadaki tüm metin blokları kaynakla karşılaştırıldı mı?")) return; const r = await fetch(`${API}/v1/teacher/documents/${documentId}/pages/${page}/approve-text`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Öğretmen kaynak sayfayı bütün olarak karşılaştırdı." }) }); setMessage(r.ok ? "Sayfadaki metinler onaylandı; yayımlanmadı." : "Bu sayfada güvenilir olmayan matematiksel metin var; yeniden yapılandırılmış çıkarım bekliyor."); if (r.ok) await load(); };
  const approveFormula = async () => { if (!selected || !documentId || selected.kind !== "formula-display" || formulaProposal?.blockId !== selected.id || formulaProposal.revision !== selected.revision || !window.confirm("Türkçe okunuş kaynak PDF'deki işaretli formülle tamamen aynı mı?")) return; const r = await fetch(`${API}/v1/teacher/documents/${documentId}/blocks/${selected.id}/approve-formula`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ reason: "Öğretmen Türkçe okunuş önerisini kaynak PDF formülüyle karşılaştırdı.", expected_revision: selected.revision }) }); setMessage(r.ok ? "Formül okunuşu onaylandı; henüz yayımlanmadı." : "Formül onaylanamadı; kaynağı yeniden yükleyin."); if (r.ok) await load(); };
  const box = selected && pageSize ? { left: `${selected.source.bbox[0] / pageSize.width * 100}%`, top: `${selected.source.bbox[1] / pageSize.height * 100}%`, width: `${(selected.source.bbox[2] - selected.source.bbox[0]) / pageSize.width * 100}%`, height: `${(selected.source.bbox[3] - selected.source.bbox[1]) / pageSize.height * 100}%` } : undefined;
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Kaynak üzerinde öğretmen denetimi</h1><p>PDF’de turuncu çerçeveli alanı okuyun; metni onaylayın veya sade metin olarak düzeltin.</p></header><p role="status">{message}</p><label>Belge<select value={documentId} onChange={e => setDocumentId(e.target.value)}>{documents.map(d => <option key={d.id} value={d.id}>{d.title} · {d.review_required_count} bekleyen</option>)}</select></label><div className="review-layout"><aside><h2>Sayfalar</h2>{[...new Set(document?.blocks.map(b => b.source.page))].map(n => <button className={n === page ? "selected-page" : ""} onClick={() => { setPage(n); const b = document?.blocks.find(x => x.source.page === n); if (b) select(b); }} key={n}>Sayfa {n}</button>)}</aside><section className="page-canvas">{page && <div className="pdf-preview">{previewUrl ? <img alt={`Kaynak PDF sayfası ${page}`} src={previewUrl} /> : <p>Sayfa önizlemesi yükleniyor.</p>}{box && <span className="source-highlight" style={box} />}</div>}<button onClick={() => void approvePage()}>Bu sayfadaki metinleri onayla</button></section><section className="editor">{selected?.kind === "formula-display" ? <div className="edit-card"><h2>Matematiksel ifade</h2><p>Turuncu alandaki formülle aşağıdaki Türkçe okunuşu karşılaştırın. Teknik LaTeX gösterilmez; yanlışsa onaylamayın.</p><p role="status">{formulaProposalStatus}</p>{formulaProposal?.blockId === selected.id && formulaProposal.revision === selected.revision && <><p className="formula-proposal">{formulaProposal.spoken}</p><button type="button" onClick={() => void approveFormula()} disabled={selected.status !== "review_required"}>Kaynakla aynı, okunuşu onayla</button></>}</div> : selected && <div className="edit-card"><h2>Seçili metin</h2><label htmlFor="review-text">Öğrenciye gösterilecek metin</label><textarea id="review-text" value={draftText} onChange={e => setDraftText(e.target.value)} /><div><button onClick={() => void submit(false)}>Kaynakla aynı, onayla</button><button onClick={() => void submit(true)}>Düzelt ve onayla</button></div></div>}<h2>Sayfadaki bölümler</h2><div className="block-list">{blocks.map(b => <button className={b.id === selected?.id ? "selected-block" : ""} onClick={() => select(b)} key={b.id}>{b.kind === "formula-display" ? "Matematiksel ifade" : b.text}</button>)}</div></section></div></main>;
}

type TeacherDocument = { id: string; title: string; published_revision: number; review_required_count: number };
type GoldItem = { id: string; page: number; kind: string; expected: string };
type TableCell = { row: number; column: number; role: "header" | "data" | "unknown"; text: string; spoken_text?: string | null };
type TableReview = { id: string; document_id: string; source: { page: number; bbox: number[] }; cells: TableCell[]; status: string; revision: number };
type SymbolEntry = { symbol: string; label: string; category: string; keywords: string };
const TABLE_SYMBOLS: SymbolEntry[] = [
  { symbol: "∈", label: "elemanıdır", category: "Kümeler", keywords: "eleman üye membership" }, { symbol: "∉", label: "elemanı değildir", category: "Kümeler", keywords: "değil üye membership" }, { symbol: "∅", label: "boş küme", category: "Kümeler", keywords: "empty" }, { symbol: "∪", label: "birleşim", category: "Kümeler", keywords: "union" }, { symbol: "∩", label: "kesişim", category: "Kümeler", keywords: "intersection" }, { symbol: "⊂", label: "alt küme", category: "Kümeler", keywords: "subset" }, { symbol: "⊆", label: "alt küme veya eşit", category: "Kümeler", keywords: "subset eşit" }, { symbol: "⊃", label: "üst küme", category: "Kümeler", keywords: "superset" }, { symbol: "⊇", label: "üst küme veya eşit", category: "Kümeler", keywords: "superset eşit" }, { symbol: "\\", label: "küme farkı", category: "Kümeler", keywords: "fark difference" }, { symbol: "′", label: "tümleyen imi", category: "Kümeler", keywords: "tümleyen prime" },
  { symbol: "=", label: "eşittir", category: "İlişkiler", keywords: "eşit" }, { symbol: "≠", label: "eşit değildir", category: "İlişkiler", keywords: "değil" }, { symbol: "<", label: "küçüktür", category: "İlişkiler", keywords: "küçük" }, { symbol: ">", label: "büyüktür", category: "İlişkiler", keywords: "büyük" }, { symbol: "≤", label: "küçük veya eşit", category: "İlişkiler", keywords: "küçük eşit" }, { symbol: "≥", label: "büyük veya eşit", category: "İlişkiler", keywords: "büyük eşit" }, { symbol: "≈", label: "yaklaşık eşittir", category: "İlişkiler", keywords: "yaklaşık" }, { symbol: "≡", label: "özdeş", category: "İlişkiler", keywords: "denk özdeş" }, { symbol: "∝", label: "orantılıdır", category: "İlişkiler", keywords: "orantı" },
  { symbol: "+", label: "artı", category: "İşlemler", keywords: "toplama" }, { symbol: "−", label: "eksi", category: "İşlemler", keywords: "çıkarma minus" }, { symbol: "×", label: "çarpı", category: "İşlemler", keywords: "çarpma" }, { symbol: "÷", label: "bölü", category: "İşlemler", keywords: "bölme" }, { symbol: "±", label: "artı eksi", category: "İşlemler", keywords: "plus minus" }, { symbol: "√", label: "karekök", category: "İşlemler", keywords: "kök root" }, { symbol: "∞", label: "sonsuz", category: "İşlemler", keywords: "infinity" }, { symbol: "·", label: "nokta çarpımı", category: "İşlemler", keywords: "çarpma nokta" }, { symbol: "%", label: "yüzde", category: "İşlemler", keywords: "percent" },
  { symbol: "∀", label: "her", category: "Mantık", keywords: "tüm her" }, { symbol: "∃", label: "vardır", category: "Mantık", keywords: "var exists" }, { symbol: "¬", label: "değil", category: "Mantık", keywords: "olumsuz" }, { symbol: "∧", label: "ve", category: "Mantık", keywords: "and" }, { symbol: "∨", label: "veya", category: "Mantık", keywords: "or" }, { symbol: "⇒", label: "ise", category: "Mantık", keywords: "implication" }, { symbol: "⇔", label: "ancak ve ancak", category: "Mantık", keywords: "eşdeğer" },
  { symbol: "α", label: "alfa", category: "Yunan harfleri", keywords: "alpha" }, { symbol: "β", label: "beta", category: "Yunan harfleri", keywords: "beta" }, { symbol: "γ", label: "gama", category: "Yunan harfleri", keywords: "gamma" }, { symbol: "δ", label: "delta", category: "Yunan harfleri", keywords: "delta" }, { symbol: "θ", label: "teta", category: "Yunan harfleri", keywords: "theta" }, { symbol: "λ", label: "lambda", category: "Yunan harfleri", keywords: "lambda" }, { symbol: "μ", label: "mü", category: "Yunan harfleri", keywords: "mu" }, { symbol: "π", label: "pi", category: "Yunan harfleri", keywords: "pi" }, { symbol: "σ", label: "sigma", category: "Yunan harfleri", keywords: "sigma toplam" },
  { symbol: "∠", label: "açı", category: "Geometri", keywords: "angle" }, { symbol: "°", label: "derece", category: "Geometri", keywords: "degree" }, { symbol: "⊥", label: "dik", category: "Geometri", keywords: "perpendicular" }, { symbol: "∥", label: "paralel", category: "Geometri", keywords: "parallel" }, { symbol: "△", label: "üçgen", category: "Geometri", keywords: "triangle" }, { symbol: "→", label: "ok", category: "Geometri", keywords: "vektör arrow" },
  { symbol: "²", label: "karesi", category: "Üs ve yapı", keywords: "üs kare" }, { symbol: "³", label: "küpü", category: "Üs ve yapı", keywords: "üs küp" }, { symbol: "ⁿ", label: "n üssü", category: "Üs ve yapı", keywords: "üs power" }, { symbol: "|", label: "mutlak değer", category: "Üs ve yapı", keywords: "absolute" }, { symbol: "{", label: "sol küme ayracı", category: "Üs ve yapı", keywords: "brace" }, { symbol: "}", label: "sağ küme ayracı", category: "Üs ve yapı", keywords: "brace" },
];

function TableReviewWorkspace() {
  const [items, setItems] = useState<TableReview[]>([]); const [selected, setSelected] = useState<TableReview | null>(null);
  const [cells, setCells] = useState<TableCell[]>([]); const [image, setImage] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null); const [message, setMessage] = useState("Belirsiz tablolar yükleniyor."); const [activeCell, setActiveCell] = useState<string | null>(null); const [symbolSearch, setSymbolSearch] = useState(""); const [symbolCategory, setSymbolCategory] = useState("Tümü"); const textareaRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const load = async () => { const response = await fetch(`${API}/v1/teacher/table-reviews`, { headers: { "X-Role": "teacher" } }); if (!response.ok) throw new Error("queue"); const next = await response.json() as TableReview[]; setItems(next); const current = next.find(item => item.id === selected?.id) ?? next[0] ?? null; setSelected(current); setCells(current?.cells ?? []); setMessage(current ? "Kaynakta turuncu çerçeveli tabloyu kontrol edin." : "Denetim bekleyen tablo yok."); };
  useEffect(() => { void fetch(`${API}/v1/teacher/table-reviews`, { headers: { "X-Role": "teacher" } }).then(response => { if (!response.ok) throw new Error("queue"); return response.json(); }).then((next: TableReview[]) => { setItems(next); const current = next[0] ?? null; setSelected(current); setCells(current?.cells ?? []); setMessage(current ? "Kaynakta turuncu çerçeveli tabloyu kontrol edin." : "Denetim bekleyen tablo yok."); }).catch(() => setMessage("Tablo denetim kuyruğu yüklenemedi.")); }, []);
  useEffect(() => { if (!selected) return; let url: string | null = null; void fetch(`${API}/v1/teacher/table-reviews/${selected.id}/preview`, { headers: { "X-Role": "teacher" } }).then(response => { if (!response.ok) throw new Error("preview"); const width = Number(response.headers.get("X-Pdf-Page-Width")); const height = Number(response.headers.get("X-Pdf-Page-Height")); if (width > 0 && height > 0) setPageSize({ width, height }); return response.blob(); }).then(blob => { url = URL.createObjectURL(blob); setImage(url); }).catch(() => { setImage(null); setPageSize(null); }); return () => { if (url) URL.revokeObjectURL(url); }; }, [selected]);
  const choose = (item: TableReview) => { setSelected(item); setCells(item.cells); setActiveCell(null); };
  const change = (row: number, column: number, text: string) => setCells(current => current.map(cell => cell.row === row && cell.column === column ? { ...cell, text, spoken_text: null } : cell));
  const changeSpeech = (row: number, column: number, spoken: string) => setCells(current => current.map(cell => cell.row === row && cell.column === column ? { ...cell, spoken_text: spoken || null } : cell));
  const insertSymbol = (symbol: string) => { if (!activeCell) return; const [row, column] = activeCell.split(":").map(Number); const cell = cells.find(value => value.row === row && value.column === column); const textarea = textareaRefs.current[activeCell]; if (!cell) return; const start = textarea?.selectionStart ?? cell.text.length; const end = textarea?.selectionEnd ?? start; const next = `${cell.text.slice(0, start)}${symbol}${cell.text.slice(end)}`; change(row, column, next); requestAnimationFrame(() => { textarea?.focus(); textarea?.setSelectionRange(start + symbol.length, start + symbol.length); }); };
  const clearActiveCell = () => { if (!activeCell) return; const [row, column] = activeCell.split(":").map(Number); change(row, column, ""); };
  const approve = async (corrected: boolean) => { if (!selected) return; const endpoint = corrected ? `${API}/v1/teacher/table-reviews/${selected.id}` : `${API}/v1/teacher/table-reviews/${selected.id}/approve`; const body = corrected ? { cells, reason: "Öğretmen kaynak PDF koordinatındaki tabloyla karşılaştırarak hücreleri düzeltti.", expected_revision: selected.revision } : { reason: "Öğretmen kaynak PDF koordinatındaki tabloyu doğruladı.", expected_revision: selected.revision }; const response = await fetch(endpoint, { method: corrected ? "PUT" : "POST", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify(body) }); setMessage(response.ok ? "Tablo onaylandı; henüz öğrenciye yayımlanmadı." : "İşlem tamamlanamadı; tabloyu yeniden yükleyin."); if (response.ok) await load(); };
  const rows = [...new Set(cells.map(cell => cell.row))]; const columns = [...new Set(cells.map(cell => cell.column))];
  const symbolCategories = ["Tümü", ...new Set(TABLE_SYMBOLS.map(item => item.category))]; const matchingSymbols = TABLE_SYMBOLS.filter(item => (symbolCategory === "Tümü" || item.category === symbolCategory) && `${item.symbol} ${item.label} ${item.category} ${item.keywords}`.toLocaleLowerCase("tr-TR").includes(symbolSearch.toLocaleLowerCase("tr-TR")));
  const box = selected && pageSize ? { left: `${selected.source.bbox[0] / pageSize.width * 100}%`, top: `${selected.source.bbox[1] / pageSize.height * 100}%`, width: `${(selected.source.bbox[2] - selected.source.bbox[0]) / pageSize.width * 100}%`, height: `${(selected.source.bbox[3] - selected.source.bbox[1]) / pageSize.height * 100}%` } : undefined;
  const active = cells.find(cell => `${cell.row}:${cell.column}` === activeCell);
  const hasEdits = selected ? JSON.stringify(cells) !== JSON.stringify(selected.cells) : false;
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Tablo denetimi</h1><p>Yalnız belirsiz vector/native tablo taslakları burada görünür. Teknik OCR, LaTeX ve model çıktısı gösterilmez.</p></header><p role="status">{message}</p><div className="review-layout"><aside><h2>Bekleyen tablolar</h2>{items.map(item => <button className={item.id === selected?.id ? "selected-page" : ""} onClick={() => choose(item)} key={item.id}>Sayfa {item.source.page} · tablo</button>)}</aside><section className="page-canvas"><div className="pdf-preview">{image ? <img alt={`Kaynak PDF sayfası ${selected?.source.page ?? ""}`} src={image} /> : <p>Kaynak sayfa önizlemesi yükleniyor.</p>}{box && <span className="source-highlight" style={box} />}</div></section><section className="editor">{selected && <><h2>Tablo hücreleri</h2><p className="source-note">Her hücreyi kaynakta turuncu çerçeveli alanla karşılaştırın. Hücreyi seçip sembol paletinden ekleyebilirsiniz; klavyede matematik işareti aramanız gerekmez.</p><fieldset className="symbol-palette"><legend>Matematik sembolleri</legend><label className="symbol-search">Sembol ara<input value={symbolSearch} onChange={event => setSymbolSearch(event.target.value)} placeholder="Örn. boş küme, teta, dik" /></label><label className="symbol-search">Kategori<select value={symbolCategory} onChange={event => setSymbolCategory(event.target.value)}>{symbolCategories.map(category => <option key={category}>{category}</option>)}</select></label><button type="button" disabled={!activeCell} onClick={clearActiveCell}>Seçili hücreyi temizle</button>{matchingSymbols.map(item => <button type="button" disabled={!activeCell} onClick={() => insertSymbol(item.symbol)} aria-label={`${item.label} (${item.category})`} title={`${item.category}: ${item.label}`} key={item.symbol}>{item.symbol}</button>)}{matchingSymbols.length === 0 && <p>Bu adla sembol bulunamadı; hücreye kopyala-yapıştır ile başka Unicode karakter de ekleyebilirsiniz.</p>}</fieldset><div className="table-editor" role="region" aria-label="Tablo hücre düzenleyicisi"><table><tbody>{rows.map(row => <tr key={row}>{columns.map(column => { const cell = cells.find(value => value.row === row && value.column === column); const Tag = cell?.role === "header" ? "th" : "td"; const key = `${row}:${column}`; return <Tag key={column}><label className="sr-only">Satır {row}, sütun {column}</label><textarea ref={element => { textareaRefs.current[key] = element; }} className={activeCell === key ? "active-table-cell" : ""} value={cell?.text ?? ""} onFocus={() => setActiveCell(key)} onChange={event => change(row, column, event.target.value)} /></Tag>; })}</tr>)}</tbody></table></div>{active && <div className="cell-pronunciation"><label htmlFor="cell-spoken">Seçili hücrenin Türkçe okunuşu · satır {active.row}, sütun {active.column}</label><input id="cell-spoken" value={active.spoken_text ?? ""} onChange={event => changeSpeech(active.row, active.column, event.target.value)} maxLength={1000} placeholder="Yalnız otomatik okunuş yanlış veya eksikse yazın" /><p>Bu alan isteğe bağlıdır. Yazdığınız okunuş yayımlandığında yalnız bu hücre için kullanılır; hücre metni değişirse okunuş temizlenir.</p></div>}<div><button onClick={() => void approve(false)} disabled={hasEdits}>Kaynakla aynı, onayla</button><button onClick={() => void approve(true)}>Düzelt ve onayla</button></div></>}</section></div></main>;
}

function GoldAnnotationReview() {
  const [items, setItems] = useState<GoldItem[]>([]); const [selected, setSelected] = useState<GoldItem | null>(null); const [text, setText] = useState(""); const [image, setImage] = useState<string | null>(null); const [message, setMessage] = useState("Gold örnekleri yükleniyor.");
  useEffect(() => { void fetch(`${API}/v1/teacher/benchmark/gold-v1/items`, { headers: { "X-Role": "teacher" } }).then(r => r.json()).then((next: GoldItem[]) => { setItems(next); setSelected(next[0] ?? null); setText(next[0]?.expected ?? ""); }).catch(() => setMessage("Gold kümesi yüklenemedi.")); }, []);
  useEffect(() => { if (!selected) return; let url: string | null = null; void fetch(`${API}/v1/teacher/benchmark/gold-v1/items/${selected.id}/preview`, { headers: { "X-Role": "teacher" } }).then(r => r.blob()).then(blob => { url = URL.createObjectURL(blob); setImage(url); }).catch(() => setImage(null)); return () => { if (url) URL.revokeObjectURL(url); }; }, [selected]);
  const choose = (item: GoldItem) => { setSelected(item); setText(item.expected); };
  const save = async () => { if (!selected) return; const r = await fetch(`${API}/v1/teacher/benchmark/gold-v1/items/${selected.id}`, { method: "PUT", headers: { "Content-Type": "application/json", "X-Role": "teacher" }, body: JSON.stringify({ expected: text }) }); setMessage(r.ok ? "Gold anotasyonu kaydedildi." : "Kaydetme başarısız."); };
  return <main className="teacher review-workspace"><header><p className="brand">ErişSTEM</p><h1>Gold benchmark anotasyonu</h1><p>Bu içerik öğrenciye yayımlanmaz. Yalnız çıkarıcıların doğruluğunu ölçmek için temsilî bölgeyi doğru ve sade biçimde tanımlayın.</p></header><p role="status">{message}</p><div className="review-layout"><aside><h2>Örnekler</h2>{items.map(item => <button className={item.id === selected?.id ? "selected-page" : ""} onClick={() => choose(item)} key={item.id}>{item.kind} · s. {item.page}</button>)}</aside><section className="page-canvas">{image ? <img alt={`Gold kaynak sayfası ${selected?.page}`} src={image} /> : <p>Sayfa yükleniyor.</p>}</section><section className="editor"><h2>{selected?.kind} · Sayfa {selected?.page}</h2><label htmlFor="gold-text">Doğru erişilebilir içerik</label><textarea id="gold-text" value={text} onChange={event => setText(event.target.value)} placeholder="Örneğin: sıfır virgül iki yüz on dokuz eksi sıfır virgül sıfır sıfır dokuz bölü iki virgül bir" /><button onClick={() => void save()}>Gold anotasyonunu kaydet</button></section></div></main>;
}

function ReviewerPublish() {
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [tables, setTables] = useState<TableReview[]>([]);
  const [message, setMessage] = useState("Yayınlanabilir içerikler yükleniyor.");
  const load = () => Promise.all([fetch(`${API}/v1/teacher/documents`, { headers: { "X-Role": "reviewer" } }).then(r => r.json()) as Promise<TeacherDocument[]>, fetch(`${API}/v1/reviewer/table-reviews`, { headers: { "X-Role": "reviewer" } }).then(r => r.json()) as Promise<TableReview[]>]).then(([nextDocuments, nextTables]) => { setDocuments(nextDocuments); setTables(nextTables); setMessage(nextDocuments.length || nextTables.length ? "Onaylı içeriği yayınlamak için seçin." : "Yayınlanabilir içerik yok."); }).catch(() => setMessage("Yayın listesi yüklenemedi."));
  useEffect(() => { load(); }, []);
  const publish = async (id: string) => { const result = await fetch(`${API}/v1/reviewer/documents/${id}/publish`, { method: "POST", headers: { "X-Role": "reviewer" } }); setMessage(result.ok ? "Belge yayımlandı." : "Yayın engellendi: denetim bekleyen içerikleri kontrol edin."); if (result.ok) load(); };
  const publishTable = async (id: string) => { const result = await fetch(`${API}/v1/reviewer/table-reviews/${id}/publish`, { method: "POST", headers: { "X-Role": "reviewer" } }); setMessage(result.ok ? "Tablo yayımlandı." : "Tablo yayımlanamadı; öğretmen onayı gerekli."); if (result.ok) load(); };
  return <main className="teacher"><h1>Onaylayıcı yayın paneli</h1><p role="status">{message}</p><h2>Belgeler</h2><ul>{documents.map(document => <li key={document.id}><h3>{document.title}</h3><p>Yayın sürümü: {document.published_revision}. Denetim bekleyen blok: {document.review_required_count}.</p><button type="button" disabled={document.review_required_count > 0} onClick={() => publish(document.id)}>Yayımla</button></li>)}</ul><h2>Öğretmen onaylı tablolar</h2><ul>{tables.map(table => <li key={table.id}><h3>Sayfa {table.source.page} · tablo</h3><p>{table.cells.length} hücre. Durum: {table.status === "published" ? "yayımlandı" : "öğretmen onaylı"}.</p><button type="button" disabled={table.status === "published"} onClick={() => publishTable(table.id)}>{table.status === "published" ? "Yayımlandı" : "Tabloyu yayımla"}</button></li>)}</ul></main>;
}

const mode = new URLSearchParams(window.location.search).get("mode");
createRoot(document.getElementById("root")!).render(mode === "learning-review" ? <LearningManagement api={API} panel="review" /> : mode === "pilot" ? <LearningManagement api={API} panel="pilot" /> : mode === "learning-release" ? <LearningManagement api={API} panel="release" /> : mode === "teacher" ? <TeacherReview /> : mode === "table-review" ? <TableReviewWorkspace /> : mode === "benchmark" ? <GoldAnnotationReview /> : mode === "reviewer" ? <ReviewerPublish /> : <StudentApp />);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
