/** Deterministic, deliberately narrow Turkish command grammar. No answer is submitted. */
export type VoiceIntent =
  | { kind: "open_history" | "open_bank" | "open_writing" | "start_study" | "back" | "next_page" | "previous_page" | "next_question" | "previous_question" | "next_unit" | "previous_unit" | "read_selected" | "show_choices" | "stop_audio" | "focus_writing" | "read_written" | "help" }
  | { kind: "go_page" | "select_region"; number: number }
  | { kind: "read_choice"; label: "A" | "B" | "C" | "D" | "E" };

export type VoiceKind = VoiceIntent["kind"];

const ones: Record<string, number> = { bir: 1, iki: 2, üç: 3, dort: 4, dört: 4, beş: 5, bes: 5, altı: 6, alti: 6, yedi: 7, sekiz: 8, dokuz: 9 };
const tens: Record<string, number> = { on: 10, yirmi: 20, otuz: 30, kırk: 40, kirk: 40, elli: 50, altmış: 60, altmis: 60, yetmiş: 70, yetmis: 70, seksen: 80, doksan: 90 };

export function normalizeVoiceText(text: string): string {
  return text.toLocaleLowerCase("tr-TR").replace(/[’']/g, " ").replace(/[^a-zçğıöşü0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

export function parseTurkishNumber(text: string): number | null {
  const value = normalizeVoiceText(text);
  if (/^\d{1,3}$/.test(value)) return Number(value);
  const words = value.split(" ");
  if (!words.length || words.length > 4) return null;
  let total = 0;
  let index = 0;
  if (words[index] === "yüz") { total += 100; index++; }
  else if (ones[words[index]] && words[index + 1] === "yüz") { total += ones[words[index]] * 100; index += 2; }
  if (tens[words[index]]) { total += tens[words[index]]; index++; }
  if (ones[words[index]]) { total += ones[words[index]]; index++; }
  return index === words.length && total > 0 ? total : null;
}

export function parseVoiceCommand(transcript: string): VoiceIntent | null {
  const text = normalizeVoiceText(transcript);
  if (!text || text.length > 90) return null;
  if (/^(yardım|komutlar|ne diyebilirim)$/.test(text)) return { kind: "help" };
  if (/^(dur|sesi durdur|okumayı durdur|seslendirmeyi durdur)$/.test(text)) return { kind: "stop_audio" };
  if (/^(ana sayfa|ana sayfaya dön|kütüphane|kütüphaneye dön|geri dön)$/.test(text)) return { kind: "back" };
  // This intentionally opens a choice, not a lesson. "Çalışmak istiyorum" is a
  // learning goal, not enough information to assume reading or assessment.
  if (/^(tarih(?: dersi)? çalış(?:mak istiyorum|alım)|(?:ders|konu)? ?çalışmak istiyorum|çalışalım)$/.test(text)) return { kind: "start_study" };
  if (/^(tarih kitabı|tarih kitabını aç|kitabı aç|konu anlatımını aç)$/.test(text)) return { kind: "open_history" };
  if (/^(soru bankası|soru bankasını aç|sorulara geç|soru çöz)$/.test(text)) return { kind: "open_bank" };
  if (/^(braille ile yaz|yazma alanı|yazma alanını aç)$/.test(text)) return { kind: "open_writing" };
  if (/^(yazı alanına geç|yazıya odaklan|yazmaya başla)$/.test(text)) return { kind: "focus_writing" };
  if (/^(yazdığımı oku|yazımı oku|metnimi oku)$/.test(text)) return { kind: "read_written" };
  if (/^(şıkları aç|şıkları göster|seçenekleri aç|seçenekleri göster)$/.test(text)) return { kind: "show_choices" };
  const choice = text.match(/^şık ([a-e])(?: yı| yi| yu| yü)?(?: oku| seslendir)?$/);
  if (choice) return { kind: "read_choice", label: choice[1].toUpperCase() as "A" | "B" | "C" | "D" | "E" };
  if (/^(sonraki sayfa|bir sonraki sayfa|sonraki sayfaya geç)$/.test(text)) return { kind: "next_page" };
  if (/^(önceki sayfa|bir önceki sayfa|önceki sayfaya geç)$/.test(text)) return { kind: "previous_page" };
  if (/^(sonraki soru|bir sonraki soru|sonraki soruya geç)$/.test(text)) return { kind: "next_question" };
  if (/^(önceki soru|bir önceki soru|önceki soruya geç)$/.test(text)) return { kind: "previous_question" };
  if (/^(sonraki bölüm|bir sonraki bölüm|sonraki metin)$/.test(text)) return { kind: "next_unit" };
  if (/^(önceki bölüm|bir önceki bölüm|önceki metin)$/.test(text)) return { kind: "previous_unit" };
  if (/^(oku|seçili bölümü oku|bölümü oku|soruyu oku|metni oku|seslendir)$/.test(text)) return { kind: "read_selected" };
  const page = text.match(/^(?:sayfa|sayfaya git|sayfayı aç) (.+)$/);
  if (page) { const number = parseTurkishNumber(page[1]); return number && number <= 300 ? { kind: "go_page", number } : null; }
  const region = text.match(/^(?:bölüm|bölüme git) (.+)$/);
  if (region) { const number = parseTurkishNumber(region[1]); return number && number <= 100 ? { kind: "select_region", number } : null; }
  return null;
}
