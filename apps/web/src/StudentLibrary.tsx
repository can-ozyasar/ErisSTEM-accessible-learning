import { VoiceCommandPanel } from "./VoiceCommandPanel";

type DocumentSummary = { id: string; title: string; block_count: number };

export function StudentLibrary({ documents, search, onSearch, status, onNavigate, onDocument }: {
  documents: DocumentSummary[];
  search: string;
  onSearch: (value: string) => void;
  status: string;
  onNavigate: (view: "history" | "question-bank" | "writing") => void;
  onDocument: (id: string) => void;
}) {
  const matches = documents.filter(item => item.title.toLocaleLowerCase("tr").includes(search.toLocaleLowerCase("tr")));
  return <>
    <a className="skip" href="#student-main">Ana içeriğe geç</a>
    <header className="site-header"><div className="site-header-inner"><p className="brand">Eriş<span>STEM</span></p><p className="site-header-context">Erişilebilir öğrenme alanı</p></div></header>
    <main id="student-main" className="student-shell library-shell">
      <section className="library-hero" aria-labelledby="library-title">
        <p className="eyebrow">ÖĞRENME KÜTÜPHANESİ</p>
        <h1 id="library-title" tabIndex={-1}>Kendi hızında, güvenle öğren.</h1>
        <p>Kaynakları dinle, sayfadaki bir bölüme odaklan veya soruları adım adım çalış. Her içerik açıkça kaynağına bağlıdır.</p>
        <a className="hero-voice-link" href="#home-voice">Sesli komutlarla ilerle ↓</a>
      </section>
      <div id="home-voice"><VoiceCommandPanel title="Sesli yol seç" examples={["tarih kitabını aç", "soru bankasını aç", "yazma alanını aç"]}
        available={["open_history", "open_bank", "open_writing"]} onCommand={command => {
          if (command.kind === "open_history") onNavigate("history");
          if (command.kind === "open_bank") onNavigate("question-bank");
          if (command.kind === "open_writing") onNavigate("writing");
        }} /></div>
      <section aria-labelledby="learning-paths-title" className="library-section">
        <div className="section-heading"><div><p className="eyebrow">BAŞLANGIÇ NOKTAN</p><h2 id="learning-paths-title">Bugün ne yapmak istersin?</h2></div><p>Bir yol seç; diğerlerine istediğin zaman dönebilirsin.</p></div>
        <nav className="path-grid" aria-label="Öğrenme yolları">
          <button type="button" className="path-card path-card-primary" aria-label="9. sınıf tarih kitabını aç" onClick={() => onNavigate("history")}><span className="path-icon" aria-hidden="true">01</span><span className="path-text"><span className="path-tag">KONU ANLATIMI</span><strong>9. sınıf tarih kitabı</strong><span>MEB kaynağındaki sayfaları ve bölümleri tek tek keşfet, seçtiğini dinle.</span></span><span className="path-action" aria-hidden="true">Kitabı aç →</span></button>
          <button type="button" className="path-card" aria-label="Tarih soru bankasını aç" onClick={() => onNavigate("question-bank")}><span className="path-icon" aria-hidden="true">02</span><span className="path-text"><span className="path-tag">SORU ÇALIŞMASI</span><strong>Tarih soru bankası</strong><span>Onaylı soruları soru kökü, görsel ve şıklar olarak ayrı ayrı incele.</span></span><span className="path-action" aria-hidden="true">Sorulara geç →</span></button>
          <button type="button" className="path-card" aria-label="Braille ile yazma alanını aç" onClick={() => onNavigate("writing")}><span className="path-icon" aria-hidden="true">03</span><span className="path-text"><span className="path-tag">KİŞİSEL ALAN</span><strong>Braille ile yaz</strong><span>Cihazındaki Braille girişini kullanarak düşüncelerini taslakla.</span></span><span className="path-action" aria-hidden="true">Yazmaya başla →</span></button>
        </nav>
      </section>
      <section className="library-section library-documents" aria-labelledby="documents-title"><div className="section-heading"><div><p className="eyebrow">DİĞER KAYNAKLAR</p><h2 id="documents-title">Yayımlanmış belgeler</h2></div></div>
        <label htmlFor="student-search">Belge ara</label><input id="student-search" type="search" lang="tr" value={search} onChange={event => onSearch(event.target.value)} placeholder="Belge adı yazın" />
        <p role="status" className="library-status">{status || `${matches.length} yayımlanmış belge bulundu.`}</p>
        {matches.length ? <ul className="student-document-list">{matches.map(item => <li key={item.id}><button type="button" onClick={() => onDocument(item.id)}><strong>{item.title}</strong><span>{item.block_count} bölüm · Okumayı aç →</span></button></li>)}</ul> : <p className="empty-state">{search ? "Aramanızla eşleşen belge yok." : "Bu bölümde henüz yayımlanmış belge yok. Yukarıdaki tarih kitabı ve soru bankası ayrı alanlardan açılır."}</p>}
      </section>
      <details className="student-help"><summary>Ekran okuyucu ve dokunmatik kullanım yardımı</summary><p>Uygulamanın sesli keşfinde fareyle üzerine gelinen veya klavyeyle odaklanan öğe tanıtılır. Dokunmatik ekranda ilk dokunuş düğmeyi tanıtır; aynı düğmeye ikinci dokunuş onu açar. TalkBack ve VoiceOver kendi gezinme hareketlerini kullanır; ikisini birlikte dinlemek istemezseniz keşif sesini kapatabilirsiniz. Her sayfada “Ana içeriğe geç” bağlantısı bulunur. Yazı girişinde cihazınızın Braille klavyesini kullanabilirsiniz; destek cihaza bağlıdır.</p></details>
    </main>
  </>;
}
