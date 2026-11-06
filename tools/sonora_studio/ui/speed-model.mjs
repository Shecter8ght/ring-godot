export function trackSpeed(track) {
  const speeds = new Set(track?.clips.map(clip => clip.speed ?? 1));
  return speeds.size > 1 ? null : ([...speeds][0] ?? 1);
}
export function retimeClip(clip, asset, speed) {
  const factor = (clip.speed ?? 1) / speed, offset = Math.min(clip.offset * factor, asset.duration);
  const duration = Math.min(clip.duration * factor, asset.duration - offset);
  if (duration < 1 / 48000) throw new Error('После изменения скорости фрагмент короче одного отсчёта.');
  return { ...clip, sourceAssetId: clip.sourceAssetId || clip.assetId, assetId: asset.id, speed, offset, duration,
    fadeIn: Math.min(clip.fadeIn * factor, duration), fadeOut: Math.min(clip.fadeOut * factor, duration) };
}
