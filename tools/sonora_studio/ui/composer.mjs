import { currentSoundType, activeTracks, visibleTracks, variantsOf, addLayer, newCombination, MAX_LAYERS, MAX_VARIANTS, trackEnd } from './model.mjs';
import { escapeHtml } from './timeline.mjs';
import { designDescription } from './shot-model.mjs';

export class Composer {
  constructor(state, hooks) {
    this.state = state; this.hooks = hooks;
    this.element = document.createElement('div'); this.element.className = 'composer';
    document.querySelector('.arrangement').prepend(this.element);
    this.element.addEventListener('click', event => this.click(event));
    this.element.addEventListener('change', event => this.change(event));
    this.element.addEventListener('dblclick', event => {
      if (event.target.closest('[data-layer]')?.dataset.layer) this.renameLayer();
      else if (event.target.closest('[data-variant]')) this.renameVariant();
    });
    this.dialog = document.createElement('dialog'); this.dialog.className = 'composer-name-dialog';
    this.dialog.innerHTML = '<form method="dialog"><h2 id="composer-name-title"></h2><label>Название<input id="composer-name" required maxlength="120" autocomplete="off"></label><div class="modal-footer"><button type="button" class="secondary-button" id="composer-name-cancel">Отмена</button><button class="primary-button" type="submit">Сохранить</button></div></form>';
    document.body.append(this.dialog);
  }
  get type() { return currentSoundType(this.state.project); }
  get layer() { return this.type.layers.find(layer => layer.id === this.state.activeLayerId) || null; }
  askName(title, value, action) {
    const input = this.dialog.querySelector('input');
    this.dialog.querySelector('h2').textContent = title; input.value = value;
    this.dialog.querySelector('form').onsubmit = event => { event.preventDefault(); const name = input.value.trim(); if (!name) return; this.dialog.close(); this.hooks.run(() => action(name)); };
    this.dialog.querySelector('#composer-name-cancel').onclick = () => this.dialog.close();
    this.dialog.showModal(); input.focus(); input.select();
  }
  render() {
    const project = this.state.project, type = this.type;
    if (!type.layers.some(layer => layer.id === this.state.activeLayerId)) this.state.activeLayerId = null;
    const layer = this.layer, variants = layer ? variantsOf(project, layer.id) : [];
    const populated = type.layers.filter(item => variantsOf(project, item.id).some(track => track.clips.length));
    const canShuffle = type.layers.some(item => item.enabled && !item.locked && variantsOf(project, item.id).length > 1);
    this.element.innerHTML = `<div class="composer-top"><div class="sound-type-tabs" role="tablist" aria-label="Тип игрового звука">${project.soundTypes.map(item => `<button role="tab" aria-selected="${type.id === item.id}" data-sound-type="${item.id}" class="${type.id === item.id ? 'active' : ''}">${item.name}<small>${item.layers.filter(l => variantsOf(project, l.id).length).length}</small></button>`).join('')}</div><div class="composer-actions"><button id="open-shot-designer" class="shot-open-button ${type.shotDesign?.enabled ? 'shot-design-on' : ''}" title="${escapeHtml(designDescription(project))}">${type.id === 'gunshots' ? 'Конструктор выстрела' : 'Пространство'}</button><button id="new-combination" class="combination-button" ${canShuffle ? '' : 'disabled'} title="Выбрать другой вариант в каждом незакреплённом слое">↻ Новая комбинация</button></div></div>
      <div class="layer-navigation"><div class="layer-tabs" role="tablist" aria-label="Слои звука"><button role="tab" aria-selected="${!layer}" data-layer="" class="${!layer ? 'active' : ''}">Весь звук <small>${populated.length}</small></button>${type.layers.map(item => { const count = variantsOf(project, item.id).length; return `<button role="tab" aria-selected="${layer?.id === item.id}" data-layer="${item.id}" class="${layer?.id === item.id ? 'active' : ''} ${count ? 'has-variants' : ''} ${item.enabled ? '' : 'layer-disabled'}" title="${escapeHtml(item.name)} · ${count} вариантов${item.locked ? ' · закреплён' : ''}">${escapeHtml(item.name)}<small>${item.locked ? '◆ ' : ''}${count || '＋'}</small></button>`; }).join('')}</div><button id="add-layer" class="add-layer-button" ${type.layers.length >= MAX_LAYERS ? 'disabled' : ''} title="Добавить свой слой">＋ Слой</button></div>
      ${layer ? `<div class="variant-shelf"><div class="variant-heading"><strong>${escapeHtml(layer.name)}</strong><span>${variants.length} / ${MAX_VARIANTS} вариантов · звучит один</span><div class="layer-options"><label title="Включить слой в финальный звук"><input id="layer-enabled" type="checkbox" ${layer.enabled ? 'checked' : ''}>В миксе</label><label title="Сохранять вариант при новой комбинации"><input id="layer-locked" type="checkbox" ${layer.locked ? 'checked' : ''}>Закрепить</label><button id="rename-layer" title="Переименовать слой">Имя слоя</button><button id="remove-layer" title="Удалить слой и его варианты. Можно отменить через Ctrl+Z">Удалить слой</button></div></div>
      <div class="variant-list" role="radiogroup" aria-label="Варианты слоя">${variants.map((track, index) => `<button role="radio" aria-checked="${layer.activeVariantId === track.id}" data-variant="${track.id}" class="variant-card ${layer.activeVariantId === track.id ? 'active' : ''}" title="Выбрать этот вариант. Двойной клик — изменить имя"><span class="variant-number">${String(index + 1).padStart(2, '0')}</span><span><strong>${escapeHtml(track.name)}</strong><small>${track.clips.length ? `${trackEnd(track).toFixed(3)} с · ${track.clips.length} фрагм.` : 'Пустой вариант'}</small></span><span class="variant-check">${layer.activeVariantId === track.id ? '●' : '○'}</span></button>`).join('')}<button id="add-variants" class="add-variants" ${variants.length >= MAX_VARIANTS ? 'disabled' : ''}>＋ Загрузить варианты<small>WAV · MP3 · OGG</small></button></div><div class="variant-caption"><label class="layer-type-label">Тип: <select id="layer-sound-type" aria-label="Перенести слой в тип звука">${project.soundTypes.map(item => `<option value="${item.id}" ${item.id === type.id ? 'selected' : ''}>${item.name}</option>`).join('')}</select></label><span>${layer.enabled ? 'Все включённые слои участвуют в прослушивании и экспорте.' : 'Этот слой выключен из микса.'}</span>${variants.length ? '<button id="rename-variant">Имя варианта</button><button id="remove-variant">Удалить вариант</button>' : ''}</div></div>` : `<div class="composition-caption"><span><i></i>${type.name}: ${activeTracks(project).filter(track => track.clips.length).length} слоёв в сборке</span><span>Один выбранный вариант из каждого слоя → готовый семпл</span></div>`}`;
  }
  selectLayer(id) {
    this.hooks.endPendingEdit(); this.state.activeLayerId = id || null;
    this.state.selectedClipIds.clear();
    this.state.selectedTrackId = visibleTracks(this.state.project, this.state.activeLayerId)[0]?.id || null;
    this.hooks.render();
  }
  renameLayer() { const layer = this.layer; if (layer) this.askName('Название слоя', layer.name, name => this.hooks.commit(() => { layer.name = name; }, 'none')); }
  renameVariant() { const track = this.state.project.tracks.find(item => item.id === this.layer?.activeVariantId); if (track) this.askName('Название варианта', track.name, name => this.hooks.commit(() => { track.name = name; }, 'none')); }
  click(event) {
    const button = event.target.closest('button'); if (!button || button.disabled) return;
    this.hooks.run(async () => {
      const project = this.state.project;
      if (button.dataset.soundType) {
        if (button.dataset.soundType === project.activeSoundTypeId) return;
        this.hooks.stop();
        this.hooks.commit(() => { project.activeSoundTypeId = button.dataset.soundType; this.state.activeLayerId = null; this.state.selectedTrackId = activeTracks(project)[0]?.id || null; this.state.selectedClipIds.clear(); this.state.selection = null; this.state.loopEnabled = false; }, 'restart');
      } else if ('layer' in button.dataset) this.selectLayer(button.dataset.layer);
      else if (button.dataset.variant) {
        this.hooks.commit(() => { this.layer.activeVariantId = button.dataset.variant; this.state.selectedTrackId = button.dataset.variant; this.state.selectedClipIds.clear(); this.state.playOnlyTrackId = null; }, 'restart');
      } else if (button.id === 'open-shot-designer') this.hooks.openDesigner();
      else if (button.id === 'new-combination') {
        this.hooks.commit(() => { newCombination(project); this.state.selectedClipIds.clear(); this.state.playOnlyTrackId = null; }, 'restart');
      } else if (button.id === 'add-layer') {
        this.askName('Новый слой', 'Новый слой', name => this.hooks.commit(() => { const layer = addLayer(project, name); this.state.activeLayerId = layer.id; this.state.selectedTrackId = null; this.state.selectedClipIds.clear(); }, 'none'));
      } else if (button.id === 'add-variants') await this.hooks.importVariants(this.layer.id);
      else if (button.id === 'rename-layer') this.renameLayer();
      else if (button.id === 'rename-variant') this.renameVariant();
      else if (button.id === 'remove-layer') {
        const layer = this.layer;
        this.hooks.commit(() => { project.tracks = project.tracks.filter(track => track.layerId !== layer.id); this.type.layers = this.type.layers.filter(item => item.id !== layer.id); this.state.activeLayerId = null; this.state.selectedClipIds.clear(); }, 'restart');
      } else if (button.id === 'remove-variant') this.hooks.commit(() => { project.tracks = project.tracks.filter(track => track.id !== this.layer.activeVariantId); this.state.selectedClipIds.clear(); }, 'restart');
    });
  }
  change(event) {
    const input = event.target, layer = this.layer; if (!layer) return;
    if (input.id === 'layer-sound-type') this.hooks.run(() => {
      const source = this.type, target = this.state.project.soundTypes.find(type => type.id === input.value);
      if (!target || source === target) return;
      if (target.layers.length >= MAX_LAYERS) throw new Error(`В типе «${target.name}» уже ${MAX_LAYERS} слоёв.`);
      this.hooks.stop();
      this.hooks.commit(() => {
        source.layers = source.layers.filter(item => item.id !== layer.id); target.layers.push(layer);
        for (const track of variantsOf(this.state.project, layer.id)) track.soundTypeId = target.id;
        this.state.project.activeSoundTypeId = target.id; this.state.selection = null; this.state.loopEnabled = false;
      }, 'restart');
    });
    if (input.id === 'layer-enabled' || input.id === 'layer-locked') this.hooks.commit(() => { layer[input.id === 'layer-enabled' ? 'enabled' : 'locked'] = input.checked; }, input.id === 'layer-enabled' ? 'restart' : 'none');
  }
}
