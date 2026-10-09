export type PublishedCell = { row: number; column: number; role: "header" | "data" | "unknown"; text: string; spoken_text?: string | null };

const symbols: Record<string, string> = {
  "∪": "birleşim", "∩": "kesişim", "\\": "küme farkı", "∖": "küme farkı",
  "∅": "boş küme", "∈": "elemanıdır", "∉": "elemanı değildir",
  "⊆": "alt kümesidir", "⊂": "öz alt kümesidir", "⊇": "kapsar",
  "=": "eşittir", "≠": "eşit değildir", "+": "artı", "−": "eksi", "-": "eksi",
  "×": "çarpı", "÷": "bölü", "/": "bölü", "<": "küçüktür", ">": "büyüktür",
  "≤": "küçük veya eşittir", "≥": "büyük veya eşittir",
  "≈": "yaklaşık eşittir", "≡": "özdeştir", "∝": "orantılıdır",
  "∀": "her", "∃": "vardır", "¬": "değil", "∧": "ve", "∨": "veya",
  "⇒": "ise", "⇔": "ancak ve ancak", "⊥": "diktir", "∥": "paraleldir",
  "∠": "açı", "°": "derece", "△": "üçgen", "→": "ok", "∞": "sonsuz",
  "√": "karekök", "±": "artı eksi", "%": "yüzde", "²": "karesi", "³": "küpü",
  "₁": "alt indis bir", "₂": "alt indis iki", "₃": "alt indis üç",
  "α": "alfa", "β": "beta", "γ": "gama", "δ": "delta", "θ": "teta",
  "λ": "lambda", "μ": "mü", "π": "pi", "σ": "sigma", "φ": "fi", "ω": "omega",
  "′": "asal işareti", "'": "asal işareti", "’": "asal işareti",
  "{": "aç küme parantezi", "}": "kapa küme parantezi",
  "(": "aç parantez", ")": "kapa parantez", "[": "aç köşeli parantez", "]": "kapa köşeli parantez",
  ",": "virgül", ".": "nokta", "…": "üç nokta", ":": "iki nokta", ";": "noktalı virgül",
};

/** Read only known notation; an unknown sign is never assigned a guessed meaning. */
export function turkishCellReading(value: string): string | null {
  if (!value.trim() || value.length > 4000) return null;
  const tokens = value.match(/[A-Za-zÇĞİÖŞÜçğıöşü0-9]+(?:['’][A-Za-zÇĞİÖŞÜçğıöşü]+)?|[^\s]/gu) ?? [];
  const parts: string[] = [];
  for (const token of tokens) {
    if (/^[A-Za-zÇĞİÖŞÜçğıöşü0-9]+(?:['’][A-Za-zÇĞİÖŞÜçğıöşü]+)?$/.test(token)) parts.push(token);
    else if (symbols[token]) parts.push(symbols[token]);
    else return null;
  }
  return parts.join(" ");
}

export function cellSpeechLabel(cell: PublishedCell, cells: PublishedCell[]): string | null {
  const headerRow = Math.min(...cells.filter(item => item.role === "header").map(item => item.row));
  const header = cells.find(item => item.row === headerRow && item.column === cell.column && item.role === "header");
  const prefix = `Satır ${cell.row}, sütun ${cell.column}`;
  const heading = header && header !== cell ? header.spoken_text || turkishCellReading(header.text) : "";
  const spoken = cell.spoken_text || (cell.text ? turkishCellReading(cell.text) : "boş hücre");
  if (heading === null || spoken === null) return null;
  return `${prefix}. ${heading ? `${heading}: ` : ""}${spoken}`;
}

export function cellNavigationLabel(cell: PublishedCell, cells: PublishedCell[]): string {
  return cellSpeechLabel(cell, cells) ?? `Satır ${cell.row}, sütun ${cell.column}. ${cell.text || "boş hücre"}`;
}
