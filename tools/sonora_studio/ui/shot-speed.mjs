import { encodeWav } from './audio.mjs';
import { trackSpeed, retimeClip } from './speed-model.mjs';
export async function prepareShotSpeed(track, speed, engine, cache) {
  if (track.clips.every(clip => (clip.speed ?? 1) === speed)) return { clips: structuredClone(track.clips), assets: [] };
  const assets = new Map();
  for (const id of new Set(track.clips.map(clip => clip.sourceAssetId || clip.assetId))) {
    const source = engine.assets.get(id); if (!source) throw new Error('Не найден исходник для изменения скорости.');
    let asset = speed === 1 ? source : engine.assets.get(cache.get(`${id}:${speed}`));
    if (!asset) {
      const bytes = await window.sonora.processAudio(encodeWav(source.buffer), { pitch: 0, speed, mode: 'independent', formant: true });
      asset = await engine.decode(`${source.name.replace(/\.(wav|mp3|ogg)$/i, '')}_${speed}x.wav`, bytes); cache.set(`${id}:${speed}`, asset.id);
    }
    assets.set(id, asset);
  }
  const old = trackSpeed(track), anchor = Math.min(...track.clips.map(clip => clip.start));
  return { clips: track.clips.map(clip => ({ ...retimeClip(clip, assets.get(clip.sourceAssetId || clip.assetId), speed), start: old === null ? clip.start : anchor + (clip.start - anchor) * old / speed })), assets: [...assets.values()] };
}
