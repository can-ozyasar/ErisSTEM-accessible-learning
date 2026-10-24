import { useLayoutEffect, useState } from "react";

const KEY = "eristem-accessibility-preferences";
type TextSize = "standard" | "large" | "larger" | "largest";
type Preferences = { textSize: TextSize; highContrast: boolean; reduceMotion: boolean };
const defaults: Preferences = { textSize: "standard", highContrast: false, reduceMotion: false };
const sizes: TextSize[] = ["standard", "large", "larger", "largest"];

function savedPreferences(): Preferences {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<Preferences> | null;
    return {
      textSize: sizes.includes(value?.textSize as TextSize) ? value!.textSize as TextSize : defaults.textSize,
      highContrast: value?.highContrast === true,
      reduceMotion: value?.reduceMotion === true,
    };
  } catch { return defaults; }
}

export function AccessibilitySettings() {
  const [preferences, setPreferences] = useState(savedPreferences);
  const [notice, setNotice] = useState("");

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.dataset.textSize = preferences.textSize;
    root.dataset.contrast = preferences.highContrast ? "high" : "standard";
    root.dataset.motion = preferences.reduceMotion ? "reduced" : "standard";
    try { localStorage.setItem(KEY, JSON.stringify(preferences)); } catch { /* storage may be unavailable */ }
  }, [preferences]);

  const change = (next: Preferences, message: string) => { setPreferences(next); setNotice(message); };
  return <aside className="accessibility-settings" aria-label="Erişilebilirlik tercihleri">
    <details><summary aria-label="Erişilebilirlik ayarları">Ayarlar</summary>
      <div className="accessibility-settings-panel">
        <p>Görünümü kendine göre ayarla. Ayarların bu tarayıcıda saklanır.</p>
        <label htmlFor="accessibility-text-size">Yazı boyutu</label>
        <select id="accessibility-text-size" value={preferences.textSize} onChange={event => {
          const textSize = event.target.value as TextSize;
          change({ ...preferences, textSize }, "Yazı boyutu değiştirildi.");
        }}><option value="standard">Standart</option><option value="large">Büyük</option><option value="larger">Daha büyük</option><option value="largest">Çok büyük</option></select>
        <label className="accessibility-check"><input type="checkbox" checked={preferences.highContrast} onChange={event => change({ ...preferences, highContrast: event.target.checked }, event.target.checked ? "Yüksek kontrast açıldı." : "Yüksek kontrast kapatıldı.")} /> Yüksek kontrast</label>
        <label className="accessibility-check"><input type="checkbox" checked={preferences.reduceMotion} onChange={event => change({ ...preferences, reduceMotion: event.target.checked }, event.target.checked ? "Hareket azaltıldı." : "Hareket ayarı normale döndü.")} /> Hareketi azalt</label>
        <details className="accessibility-help"><summary>Kullanım yardımı</summary><ul>
          <li>Tab ve Shift + Tab ile denetimler arasında ilerle.</li>
          <li>Enter veya Boşluk ile seçili düğmeyi aç.</li>
          <li>Kaydırmalı menüde sağ ve sol ok tuşlarını kullan.</li>
          <li>Ekran okuyucudaki dokunma hareketleri her zamanki gibi çalışır.</li>
        </ul></details>
        <p role="status" className="accessibility-settings-status">{notice}</p>
      </div>
    </details>
  </aside>;
}
