import { useEffect, useRef, useState } from "react";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

const API = import.meta.env.VITE_API_URL ?? "/api";
type Region = { id: string; kind: string; bbox: number[]; text: string; spoken_text: string; description: string | null; description_status: string; caption_id: string | null; reading_order: number };
type Page = { page: number; width: number; height: number; regions: Region[] };
type Book = { title: string; page_count: number; source_url: string; notice: string };

const labels: Record<string, string> = {
  heading: "Başlık", source_label: "Kaynak", paragraph: "Metin", visual: "Görsel", qr_code: "Karekod",
  question_or_instruction: "Soru veya yönerge", worksheet_label: "Çalışma alanı",
  citation: "Kaynakça", external_link: "Dış bağlantı",
};

export function HistoryReader({ onBack }: { onBack: () => void }) {
  const [book, setBook] = useState<Book | null>(null);
  const [pageNumber, setPageNumber] = useState(40);
  const [page, setPage] = useState<Page | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [status, setStatus] = useState("MEB kitabı yükleniyor.");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [showEvidence, setShowEvidence] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const currentUrl = useRef<string | null>(null);
  const selection = useRef(0);
  useEffect(() => {
    void fetch(`${API}/v1/history/book`).then(r => { if (!r.ok) throw Error(); return r.json() as Promise<Book>; })
      .then(setBook).catch(() => setStatus("Tarih kitabı sunucuda bulunamadı."));
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API}/v1/history/pages/${pageNumber}`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw Error(); return r.json() as Promise<Page>; })
      .then(value => { if (!controller.signal.aborted) { setPage(value); setSelectedId(""); setShowEvidence(false); setAnswer(""); setStatus(`${value.regions.length} kaynak bölümü bulundu.`); } })
      .catch(() => { if (!controller.signal.aborted) setStatus("Sayfa yüklenemedi."); });
    return () => controller.abort();
  }, [pageNumber]);
  useEffect(() => () => { audio.current?.pause(); if (currentUrl.current) URL.revokeObjectURL(currentUrl.current); }, []);
  const selected = page?.regions.find(region => region.id === selectedId) ?? null;
  const choose = (region: Region) => { setSelectedId(region.id); setShowEvidence(false); setAnswer(""); selection.current++; audio.current?.pause(); };
  const speak = async (region: Region | null = selected) => {
    if (!region?.spoken_text) return;
    const serial = ++selection.current;
    audio.current?.pause();
    if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
    currentUrl.current = null; setAudioUrl(null);
    setStatus("Yerel Türkçe ses hazırlanıyor.");
    try {
      const response = await fetch(`${API}/v1/history/pages/${pageNumber}/regions/${region.id}/audio`);
      if (!response.ok) throw Error();
      const url = URL.createObjectURL(await response.blob());
      if (serial !== selection.current) { URL.revokeObjectURL(url); return; }
      currentUrl.current = url; setAudioUrl(url);
      const player = new Audio(url); audio.current = player;
      player.onended = () => setStatus("Bölüm okundu.");
      await player.play(); setStatus("Seçili bölüm okunuyor.");
    } catch { if (serial === selection.current) setStatus("Yerel ses kullanılamadı. Metin ekran okuyucuyla erişilebilir."); }
  };
  const prompts = page?.regions.filter(region => region.kind === "question_or_instruction") ?? [];
  const evidence = page?.regions.filter(region => region.reading_order < (selected?.reading_order ?? 0) && ["paragraph", "visual"].includes(region.kind)).slice(-5) ?? [];
  const go = (value: number) => { if (!book || value < 1 || value > book.page_count) return; selection.current++; audio.current?.pause(); setPage(null); setSelectedId(""); setStatus(`Sayfa ${value} yükleniyor.`); setPageNumber(value); };
  const moveRegion = (offset: number) => {
    if (!page?.regions.length) return;
    const current = page.regions.findIndex(region => region.id === selectedId);
    const next = page.regions[Math.max(0, Math.min(page.regions.length - 1, current + offset))];
    if (next) { choose(next); void speak(next); }
  };
  const selectedIndex = page?.regions.findIndex(region => region.id === selectedId) ?? -1;
  return <><a className="skip" href="#history-main">İçeriğe geç</a><header><p className="brand">Tarih çalışma alanı</p></header><main id="history-main" className="history-shell"><button type="button" onClick={onBack}>Kütüphaneye dön</button><h1>{book?.title ?? "Tarih kitabı"}</h1><p className="notice">{book?.notice ?? status} Resmî kaynak: <a href={book?.source_url} target="_blank" rel="noreferrer">MEB kitap sayfası</a>.</p><p role="status">{status}</p>
    <nav className="history-navigation" aria-label="Kitap sayfaları"><button type="button" onClick={() => go(pageNumber - 1)} disabled={pageNumber <= 1}>Önceki sayfa</button><label>PDF sayfası <input type="number" min={1} max={book?.page_count ?? 263} value={pageNumber} onChange={event => go(Number(event.target.value))} /></label><span>/ {book?.page_count ?? "…"}</span><button type="button" onClick={() => go(pageNumber + 1)} disabled={!book || pageNumber >= book.page_count}>Sonraki sayfa</button></nav>
    <VoiceCommandPanel title="Kitapta sesli ilerle" examples={["sonraki sayfa", "sayfa kırk iki", "sonraki bölüm", "bölüm üç", "seçili bölümü oku", "kütüphaneye dön"]}
      available={["back", "stop_audio", ...(book ? ["go_page" as const] : []), ...(book && pageNumber < book.page_count ? ["next_page" as const] : []), ...(pageNumber > 1 ? ["previous_page" as const] : []), ...(page?.regions.length ? ["select_region" as const, "read_selected" as const] : []), ...(page?.regions.length && selectedIndex < page.regions.length - 1 ? ["next_unit" as const] : []), ...(selectedIndex > 0 ? ["previous_unit" as const] : [])]}
      onCommand={command => {
        if (command.kind === "next_page") go(pageNumber + 1);
        else if (command.kind === "previous_page") go(pageNumber - 1);
        else if (command.kind === "go_page") { if (book && command.number <= book.page_count) go(command.number); else setStatus("Kitapta o numarada sayfa yok."); }
        else if (command.kind === "next_unit") moveRegion(1);
        else if (command.kind === "previous_unit") moveRegion(-1);
        else if (command.kind === "select_region") { const region = page?.regions[command.number - 1]; if (region) { choose(region); void speak(region); } else setStatus("Bu sayfada o numarada bölüm yok."); }
        else if (command.kind === "read_selected") { const region = selected ?? page?.regions[0]; if (region) { if (!selected) choose(region); void speak(region); } else setStatus("Önce bir bölüm seçin."); }
        else if (command.kind === "stop_audio") { selection.current++; audio.current?.pause(); setStatus("Ses durduruldu."); }
        else if (command.kind === "back") onBack();
      }} />
    {page && <div className="history-layout"><section aria-label={`Sayfa ${pageNumber} görseli`}><div className="history-page" style={{ aspectRatio: `${page.width}/${page.height}` }}><img src={`${API}/v1/history/pages/${pageNumber}/image`} alt={`Tarih kitabının PDF sayfası ${pageNumber}; seçilebilir alanlar aşağıda metin olarak da sunulur.`} />{page.regions.map(region => <button key={region.id} type="button" className={`history-hotspot ${selectedId === region.id ? "history-hotspot-selected" : ""}`} style={{ left: `${region.bbox[0] / page.width * 100}%`, top: `${region.bbox[1] / page.height * 100}%`, width: `${(region.bbox[2] - region.bbox[0]) / page.width * 100}%`, height: `${(region.bbox[3] - region.bbox[1]) / page.height * 100}%` }} onClick={() => choose(region)} aria-label={`${labels[region.kind] ?? region.kind}: ${region.text.slice(0, 90) || region.spoken_text.slice(0, 90)}`} title={labels[region.kind] ?? region.kind} />)}</div></section><aside className="history-panel"><h2>Sayfadaki bölümler</h2><p>Sayfa üzerindeki alana dokunun veya aşağıdaki listeden seçin.</p><ol>{page.regions.map(region => <li key={region.id}><button type="button" className={selectedId === region.id ? "history-selected" : ""} onClick={() => choose(region)}>{labels[region.kind] ?? region.kind}: {(region.text || region.spoken_text).slice(0, 110)}</button></li>)}</ol>{selected && <section className="history-detail" aria-live="polite"><h3>Seçili bölüm: {labels[selected.kind] ?? selected.kind}</h3><p>{selected.text || selected.spoken_text}</p>{selected.kind === "visual" && <p className="source-note">{selected.description ? selected.description : "Görselin ayrıntılı betimlemesi henüz doğrulanmadı. Alt yazı varsa yalnız o okunur."}</p>}{selected.kind === "external_link" && <a href={selected.text} target="_blank" rel="noreferrer">Bağlantıyı aç</a>}<button type="button" onClick={() => void speak()} disabled={!selected.spoken_text}>Seçili bölümü seslendir</button>{audioUrl && <audio controls src={audioUrl}>Ses oynatıcı desteklenmiyor.</audio>}</section>}</aside></div>}
    {page && <section className="history-study"><h2>Sesli soru-cevap çalışması</h2><p>Kitaptaki gerçek sorulardan birini seçin, yanıtınızı düşünün veya yazın; ardından aynı sayfadaki kaynak kanıtlarına dönün. Otomatik puanlama yapılmaz.</p><label>Soru seç <select value={selected?.kind === "question_or_instruction" ? selected.id : ""} onChange={event => { const region = prompts.find(item => item.id === event.target.value); if (region) choose(region); }}><option value="">Bir soru seçin</option>{prompts.map(region => <option key={region.id} value={region.id}>{region.text.slice(0, 125)}</option>)}</select></label>{selected?.kind === "question_or_instruction" && <><button type="button" onClick={() => void speak()}>Soruyu sesli oku</button><label>Yanıtım <textarea value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Yanıtınızı burada taslaklayın; sunucuya gönderilmez." /></label><button type="button" onClick={() => setShowEvidence(!showEvidence)}>{showEvidence ? "Kaynak ipuçlarını gizle" : "Kaynak ipuçlarını göster"}</button>{showEvidence && <ul>{evidence.map(region => <li key={region.id}><button type="button" onClick={() => choose(region)}>{labels[region.kind]}: {region.text.slice(0, 160) || region.spoken_text.slice(0, 160)}</button></li>)}</ul>}</>}</section>}
  </main></>;
}
