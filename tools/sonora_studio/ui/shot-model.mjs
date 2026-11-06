export const spacePresets = {
  dry: { name: 'Сухой звук', note: 'Без отражений и добавленного хвоста', decay: 0, preDelay: 0, wet: 0, damping: 18000, dense: false, early: [] },
  small: { name: 'Небольшое помещение', note: 'Близкие стены, короткий плотный отклик', decay: .48, preDelay: .007, wet: .24, damping: 6200, dense: true, early: [[.011,.20],[.019,.13],[.031,.085]] },
  large: { name: 'Большое помещение', note: 'Отдалённые отражения и мягкое затухание', decay: 1.85, preDelay: .026, wet: .30, damping: 4900, dense: true, early: [[.033,.18],[.061,.12],[.098,.08]] },
  outdoor: { name: 'Улица', note: 'Открытое пространство, редкие слабые отражения', decay: .24, preDelay: 0, wet: .32, damping: 7800, dense: false, early: [[.043,.17],[.079,.085],[.121,.04]] }
};
export const shotRoles = {
  other: 'Не задана', low: 'Низкочастотный удар', high: 'Высокочастотный хлопок', mid: 'Середина', gas: 'Шипение газов', trigger: 'Спусковой крючок', pin: 'Удар бойка', boltBack: 'Откат затвора', boltForward: 'Возврат затвора', casing: 'Вылет гильзы', tail: 'Хвост / пространство', reference: 'Исходник для сравнения'
};
export const defaultShotDesign = () => ({ enabled: false, environment: 'dry', suppressed: false, suppression: .8, amount: 1, size: 1, output: 0 });
export function validateShotDesign(input) {
  if (input !== undefined && (!input || typeof input !== 'object' || Array.isArray(input))) throw new Error('Некорректные настройки характера выстрела.');
  const value = { ...defaultShotDesign(), ...input };
  if (!Object.hasOwn(spacePresets, value.environment)) throw new Error('Неизвестный пресет пространства.');
  for (const [key, min, max] of [['suppression',0,1],['amount',0,1.5],['size',.5,1.6],['output',-18,6]]) {
    if (!Number.isFinite(value[key]) || typeof value[key] !== 'number' || value[key] < min || value[key] > max) throw new Error('Некорректный параметр характера выстрела: ' + key);
  }
  return { enabled: value.enabled === true, environment: value.environment, suppressed: value.suppressed === true, suppression: value.suppression, amount: value.amount, size: value.size, output: value.output };
}
export function currentShotDesign(project) {
  return project.soundTypes?.find(type => type.id === project.activeSoundTypeId)?.shotDesign || defaultShotDesign();
}
export function shotTail(project) {
  const design = currentShotDesign(project), preset = spacePresets[design.environment];
  return design.enabled && design.amount > 0 && preset.wet > 0 ? preset.preDelay * design.size + preset.decay * design.size : 0;
}
export function designDescription(project) {
  const design = currentShotDesign(project);
  return !design.enabled ? 'Пространство и выстрел' : `${spacePresets[design.environment].name}${design.suppressed ? ' · глушитель' : ''}`;
}
export function inferShotRole(name) {
  return Object.entries(shotRoles).find(([role, title]) => role !== 'other' && title.toLowerCase() === String(name).toLowerCase())?.[0] || 'other';
}
