/** Ephemeral bounded audio cache shared by question reading and interface speech. */
const MAX_BYTES = 24 * 1024 * 1024;
const cache = new Map<string, ArrayBuffer>();
const pending = new Map<string, Promise<ArrayBuffer>>();
let bytes = 0;

export async function audioBytes(key: string, load: () => Promise<ArrayBuffer>): Promise<ArrayBuffer> {
  const hit = cache.get(key);
  if (hit) {
    cache.delete(key); cache.set(key, hit);
    return hit;
  }
  const running = pending.get(key);
  if (running) return running;
  const task = load().then(data => {
    if (data.byteLength <= MAX_BYTES) {
      while (bytes + data.byteLength > MAX_BYTES) {
        const oldest = cache.keys().next().value;
        if (!oldest) break;
        bytes -= cache.get(oldest)!.byteLength;
        cache.delete(oldest);
      }
      cache.set(key, data); bytes += data.byteLength;
    }
    return data;
  }).finally(() => pending.delete(key));
  pending.set(key, task);
  return task;
}

export async function fetchAudio(key: string, url: string, init?: RequestInit): Promise<ArrayBuffer> {
  return audioBytes(key, async () => {
    const response = await fetch(url, init);
    if (!response.ok) throw new Error("audio_unavailable");
    return response.arrayBuffer();
  });
}

export function cachedAudioCount(): number { return cache.size; }
