import { defaultShotDesign, validateShotDesign, inferShotRole, shotRoles } from './shot-model.mjs';
export const MAX_LAYERS = 50;
export const MAX_VARIANTS = 32;
export const MAX_STORED_TRACKS = 500;
const uid = () => globalThis.crypto.randomUUID();

const templates = [
  ['gunshots', 'Стрельба', ['Низкочастотный удар', 'Высокочастотный хлопок', 'Середина', 'Шипение газов', 'Спусковой крючок', 'Удар бойка', 'Откат затвора', 'Возврат затвора', 'Вылет гильзы', 'Хвост / пространство']],
  ['footsteps', 'Шаги', ['Удар стопы', 'Поверхность', 'Трение подошвы', 'Вода / грязь', 'Снаряжение', 'Одежда']],
  ['ambience', 'Окружение', ['Основной фон', 'Ближние детали', 'Дальние детали', 'Механизмы', 'Природа']],
  ['voices', 'Голоса', ['Основной голос', 'Дыхание', 'Усилия', 'Шорохи', 'Пространство', 'Рация']]
];
export function createLayer(name) {
  return { id: uid(), name, role: inferShotRole(name), enabled: true, locked: false, activeVariantId: null };
}
export function createSoundTypes() {
  return templates.map(([id, name, layers]) => ({ id, name, layers: layers.map(createLayer), shotDesign: defaultShotDesign() }));
}
export function currentSoundType(project) {
  return project.soundTypes?.find(type => type.id === project.activeSoundTypeId) || project.soundTypes?.[0] || null;
}
export function variantsOf(project, layerId) {
  return project.tracks.filter(track => track.layerId === layerId);
}
export function layerOf(project, track) {
  return project.soundTypes?.find(type => type.id === track.soundTypeId)?.layers.find(layer => layer.id === track.layerId) || null;
}
// Unassigned tracks remain audible for old callers; normalizeWorkbench adopts them on edits/load.
export function activeTracks(project) {
  const type = currentSoundType(project);
  if (!type) return project.tracks;
  const chosen = new Set(type.layers.map(layer => layer.activeVariantId).filter(Boolean));
  return project.tracks.filter(track => (!track.layerId && !track.soundTypeId) || (track.soundTypeId === type.id && chosen.has(track.id)));
}
export function enabledTracks(project) {
  return activeTracks(project).filter(track => layerOf(project, track)?.enabled !== false);
}
export function visibleTracks(project, layerId = null) {
  return activeTracks(project).filter(track => !layerId || track.layerId === layerId);
}
export function addLayer(project, name, type = currentSoundType(project)) {
  if (!type || type.layers.length >= MAX_LAYERS) throw new Error(`В одном типе звука может быть до ${MAX_LAYERS} слоёв.`);
  const layer = createLayer(String(name || 'Новый слой').slice(0, 200));
  type.layers.push(layer);
  return layer;
}
export function assignVariant(project, track, layer, type = currentSoundType(project)) {
  if (variantsOf(project, layer.id).filter(item => item.id !== track.id).length >= MAX_VARIANTS) throw new Error(`В слое может быть до ${MAX_VARIANTS} вариантов.`);
  if (!project.tracks.includes(track)) {
    if (project.tracks.length >= MAX_STORED_TRACKS) throw new Error(`В проекте может быть до ${MAX_STORED_TRACKS} вариантов.`);
    project.tracks.push(track);
  }
  track.soundTypeId = type.id;
  track.layerId = layer.id;
  layer.activeVariantId = track.id;
  return track;
}
export function normalizeWorkbench(project) {
  const legacy = !Array.isArray(project.soundTypes);
  if (legacy) project.soundTypes = createSoundTypes();
  if (!project.soundTypes.some(type => type.id === project.activeSoundTypeId)) project.activeSoundTypeId = project.soundTypes[0].id;
  const type = currentSoundType(project);
  // A legacy project is a parallel mix. Keep every old track in its own layer.
  if (legacy && project.tracks.length) type.layers = [];
  for (const track of project.tracks) {
    if (!layerOf(project, track)) {
      const layer = addLayer(project, track.name, type);
      assignVariant(project, track, layer, type);
    }
  }
  for (const soundType of project.soundTypes) {
    soundType.shotDesign ??= defaultShotDesign();
    for (const layer of soundType.layers) {
      layer.role ??= inferShotRole(layer.name);
      const variants = variantsOf(project, layer.id);
      if (!variants.some(track => track.id === layer.activeVariantId)) layer.activeVariantId = variants[0]?.id || null;
    }
  }
  project.schemaVersion = 3;
  return project;
}
export function newCombination(project, random = Math.random) {
  let changed = 0;
  for (const layer of currentSoundType(project).layers) {
    if (!layer.enabled || layer.locked) continue;
    const alternatives = variantsOf(project, layer.id).filter(track => track.id !== layer.activeVariantId);
    if (!alternatives.length) continue;
    layer.activeVariantId = alternatives[Math.min(alternatives.length - 1, Math.floor(random() * alternatives.length))].id;
    changed++;
  }
  return changed;
}
export function validateWorkbench(project, checkId) {
  if (!Array.isArray(project.soundTypes) || project.soundTypes.length !== templates.length) throw new Error('В проекте должны быть четыре типа игровых звуков.');
  for (const [typeId] of templates) {
    if (project.soundTypes.filter(type => type.id === typeId).length !== 1) throw new Error('Некорректный тип игрового звука.');
  }
  const assignments = new Map();
  for (const type of project.soundTypes) {
    type.shotDesign = validateShotDesign(type.shotDesign);
    type.name = templates.find(([id]) => id === type.id)[1];
    if (!Array.isArray(type.layers) || type.layers.length > MAX_LAYERS) throw new Error('Слишком много слоёв в типе звука.');
    for (const layer of type.layers) {
      checkId(layer.id);
      layer.name = String(layer.name || 'Слой').slice(0, 200);
      layer.role ??= inferShotRole(layer.name);
      if (!Object.hasOwn(shotRoles, layer.role)) throw new Error('Неизвестная роль слоя.');
      layer.enabled = layer.enabled !== false; layer.locked = !!layer.locked;
      const variants = project.tracks.filter(track => track.layerId === layer.id && track.soundTypeId === type.id);
      if (variants.length > MAX_VARIANTS || (layer.activeVariantId !== null && !variants.some(track => track.id === layer.activeVariantId)) || (variants.length && !layer.activeVariantId)) throw new Error('Некорректные варианты слоя.');
      for (const track of variants) assignments.set(track.id, layer.id);
    }
  }
  if (!project.soundTypes.some(type => type.id === project.activeSoundTypeId) || assignments.size !== project.tracks.length) throw new Error('Дорожка ссылается на отсутствующий слой.');
}
