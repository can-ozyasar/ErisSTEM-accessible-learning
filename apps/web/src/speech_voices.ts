/** Browser TTS may silently pick a non-Turkish default unless a voice is set. */
export function turkishVoices<T extends { lang: string; voiceURI: string; localService: boolean }>(voices: readonly T[]): T[] {
  return voices.filter(voice => voice.localService === true && /^tr(?:-|_|$)/i.test(voice.lang)).sort((left, right) => {
    const rank = (voice: T) => voice.lang.toLowerCase().replace("_", "-") === "tr-tr" ? 1 : 0;
    return rank(right) - rank(left);
  });
}
