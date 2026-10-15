import { useRef } from "react";
import { useLearningSpeech } from "./useLearningSpeech";
import { VoiceCommandPanel } from "./VoiceCommandPanel";

export function WritingSpace({ writing, onWriting, status, onStatus, onBack }: {
  writing: string; onWriting: (text: string) => void; status: string; onStatus: (status: string) => void; onBack: () => void;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const { speak, stop, status: speechStatus } = useLearningSpeech(1);
  const read = () => {
    if (!writing.trim()) { onStatus("Okunacak yazı yok."); return; }
    if (writing.length > 1200) { onStatus("Yazı uzun. Okunmasını istediğiniz bölümü seçip ekran okuyucunuzla dinleyin."); return; }
    speak(writing);
  };
  return <><a className="skip" href="#writing-main">Ana içeriğe geç</a><header><p className="brand">ErişSTEM</p></header><main id="writing-main" className="student-shell"><button type="button" onClick={() => { stop(); onBack(); }}>← Kütüphaneye dön</button><p className="eyebrow">KİŞİSEL ALAN</p><h1 tabIndex={-1}>Braille ile yaz</h1><p>Telefonunda TalkBack veya VoiceOver açıksa metin alanına odaklanıp çift dokun; cihazının Braille giriş yöntemini kullanabilirsin.</p>
    <VoiceCommandPanel title="Yazı alanında sesli yönlendirme" examples={["yazı alanına geç", "yazdığımı oku", "kütüphaneye dön"]}
      available={["focus_writing", "read_written", "stop_audio", "back"]} onCommand={command => {
        if (command.kind === "focus_writing") input.current?.focus();
        else if (command.kind === "read_written") read();
        else if (command.kind === "stop_audio") stop();
        else if (command.kind === "back") { stop(); onBack(); }
      }} />
    <label htmlFor="student-writing">Yazın</label><textarea id="student-writing" ref={input} lang="tr" inputMode="text" autoComplete="off" spellCheck={false} value={writing} onChange={event => onWriting(event.target.value)} maxLength={5000} />
    <p role="status">{speechStatus || status}</p><div className="student-actions"><button type="button" onClick={() => input.current?.focus()}>Yazı alanına odaklan</button><button type="button" disabled={!writing} onClick={() => { void navigator.clipboard.writeText(writing).then(() => onStatus("Yazı panoya kopyalandı.")).catch(() => onStatus("Panoya kopyalanamadı; metni seçerek kopyalayın.")); }}>Yazıyı kopyala</button><button type="button" disabled={!writing} onClick={() => { if (window.confirm("Bu oturumdaki yazı silinsin mi?")) { onWriting(""); onStatus("Yazı temizlendi."); input.current?.focus(); } }}>Yazıyı temizle</button></div>
    <p className="notice">Bu alan henüz ödev veya mesaj göndermez. Yazı sunucuya kaydedilmez ve sayfa yenilenirse kaybolur.</p>
  </main></>;
}
