import { currentSoundType, enabledTracks, audibleTracks, variantsOf, addLayer, assignVariant, createTrack, createClip, projectEnd, trackStart, trackEnd, uid, MAX_TRACKS, MAX_VARIANTS, MAX_LAYERS } from './model.mjs';
import { defaultShotDesign, spacePresets, shotRoles } from './shot-model.mjs';
import { analyzeShot, splitShot, planShot, timingScenarios } from './shot-analysis.mjs';
import { trackSpeed } from './speed-model.mjs';
import { prepareShotSpeed } from './shot-speed.mjs';
import { renderAudio, encodeWav } from './audio.mjs';
import { escapeHtml } from './timeline.mjs';
const $ = id => document.getElementById(id);
const metadata = asset => ({ id: asset.id, name: asset.name, duration: asset.duration, sampleRate: asset.sampleRate, channels: asset.channels });
const channels = buffer => Array.from({ length: buffer.numberOfChannels }, (_, c) => buffer.getChannelData(c));
const db = value => value > 1e-9 ? (20 * Math.log10(value)).toFixed(1) : '−∞';

export class ShotDesigner {
  constructor(state, engine, hooks) {
    this.state = state; this.engine = engine; this.hooks = hooks; this.cache = new Map(); this.working = false; this.mode = 'space'; this.result = null; this.plan = null;
    this.dialog = document.createElement('dialog'); this.dialog.id = 'shot-designer'; this.dialog.className = 'shot-designer'; document.body.append(this.dialog);
    this.dialog.addEventListener('click', event => this.click(event));
    this.dialog.addEventListener('input', event => this.input(event));
    this.dialog.addEventListener('change', event => this.change(event));
    this.dialog.addEventListener('close', () => { this.stopPreview(); this.hooks.endPendingEdit(); });
    this.dialog.addEventListener('cancel', event => { if (this.working) event.preventDefault(); });
  }
  get type() { return currentSoundType(this.state.project); }
  get design() { return this.type.shotDesign ??= defaultShotDesign(); }
  open() {
    this.hooks.endPendingEdit(); this.result = null; this.plan = null; this.mode = 'space'; this.sourceId = enabledTracks(this.state.project).find(track => track.id === this.state.selectedTrackId && track.clips.length)?.id || enabledTracks(this.state.project).find(track => track.clips.length)?.id || '';
    this.render(); this.dialog.showModal();
  }
  render() {
    const design = this.design, gun = this.type.id === 'gunshots', tracks = enabledTracks(this.state.project).filter(track => track.clips.length && this.type.layers.find(layer => layer.id === track.layerId)?.role !== 'reference');
    this.dialog.innerHTML = `<header class="shot-heading"><div><span class="eyebrow">SONORA · СБОРКА И ХАРАКТЕР</span><h2>${gun ? 'Конструктор выстрела' : 'Пространство звука'}</h2><p>Общая обработка после всех слоёв · ${escapeHtml(this.type.name)}</p></div><button id="shot-close" aria-label="Закрыть конструктор">×</button></header>
      <div class="shot-tabs"><button data-shot-tab="space" class="${this.mode === 'space' ? 'active' : ''}">Пространство и характер</button><button data-shot-tab="layers" class="${this.mode === 'layers' ? 'active' : ''}" ${gun ? '' : 'disabled'}>Умные слои</button><div class="shot-preview"><label><input id="shot-loop" type="checkbox" checked>Петля</label><button id="shot-preview-a" ${tracks.length ? '' : 'disabled'}>A · Без пресета</button><button id="shot-preview-b" ${tracks.length ? '' : 'disabled'}>B · С пресетом</button><button id="shot-stop">■ Стоп</button></div></div>
      <div class="shot-space" ${this.mode === 'space' ? '' : 'hidden'}><div class="shot-section-heading"><h3>Где звучит выстрел</h3><label><input id="shot-enabled" type="checkbox" ${design.enabled ? 'checked' : ''}>Обработка включена</label></div><div class="space-presets">${Object.entries(spacePresets).map(([id,preset]) => `<button data-space-preset="${id}" class="${design.environment === id ? 'active' : ''}" aria-pressed="${design.environment === id}"><span>${{dry:'○',small:'▣',large:'▤',outdoor:'⌁'}[id]}</span><strong>${preset.name}</strong><small>${preset.note}</small><i>${id === 'dry' ? 'Прямой звук' : `Хвост ${(preset.decay * design.size).toFixed(2)} с`}</i></button>`).join('')}</div>
      <div class="shot-controls"><section class="shot-control-card"><h3>Акустика</h3><p>Прямой удар сохраняется. Отражения добавляются параллельно.</p>${this.slider('amount','Количество отражений',design.amount,0,1.5,.01,'%')}${this.slider('size','Масштаб пространства',design.size,.5,1.6,.01,'×')}</section><section class="shot-control-card ${gun ? '' : 'unavailable'}"><h3><label><input id="shot-suppressed" type="checkbox" ${design.suppressed ? 'checked' : ''} ${gun ? '' : 'disabled'}>Выстрел с глушителем</label></h3><p>Мягче хлопок и верх, плотнее низ. Вариант из стандартного выстрела.</p>${this.slider('suppression','Степень приглушения',design.suppression,0,1,.01,'%')}<small>Стилизация исходной записи. Уже записанные эхо и сверхзвуковой треск могут остаться.</small></section><section class="shot-control-card"><h3>Выход</h3><p>Слой за слоем → общий характер → мастер и лимитер.</p>${this.slider('output','Уровень результата',design.output,-18,6,.1,'дБ')}<button id="shot-reset" class="shot-secondary">Сбросить общую обработку</button></section></div>
      <div class="shot-batch"><div><strong>Один выстрел → шесть вариаций</strong><p>Малое помещение, большой зал, улица — обычный и приглушённый варианты.</p></div><button id="shot-export-six" ${gun && tracks.length ? '' : 'disabled'}>6 WAV в папку</button><button id="shot-ring-six" ${gun && tracks.length ? '' : 'disabled'}>6 вариантов → Ring</button></div></div>
      <div class="shot-layers" ${this.mode === 'layers' ? '' : 'hidden'}><div class="smart-workflows"><section class="shot-control-card"><span class="shot-step">01 · ИЗ ОДНОЙ ЗАПИСИ</span><h3>Разложить выстрел на слои</h3><p>Низ, середина, хлопок, шумовая часть и исходный хвост. Сумма частей сохраняет исходный звук.</p><label class="shot-source-label">Исходная дорожка<select id="shot-source">${tracks.map(track => `<option value="${track.id}" ${track.id === this.sourceId ? 'selected' : ''}>${escapeHtml(track.name)}</option>`).join('')}</select></label><button id="shot-analyze" ${tracks.length ? '' : 'disabled'}>Анализировать запись</button><small>Лучше сухой одиночный выстрел. Механику можно добавить отдельными записями.</small></section><section class="shot-control-card"><span class="shot-step">02 · ИЗ ЗАГРУЖЕННЫХ СЛОЁВ</span><h3>Собрать сценарий исполнения</h3><p>Найдёт начало звуков, синхронизирует удар, спуск, боёк, затвор и гильзу. Закреплённые слои сохраняются.</p><select id="shot-scenario">${Object.entries(timingScenarios).map(([id,item]) => `<option value="${id}">${item.name}</option>`).join('')}</select><label class="shot-check"><input id="shot-auto-speed" type="checkbox" checked>Ускорять длинную механику, сохраняя высоту</label><label class="shot-check"><input id="shot-auto-balance" type="checkbox" checked>Подобрать уровни деталей относительно удара</label><button id="shot-plan" ${tracks.length ? '' : 'disabled'}>Рассчитать сценарий</button></section></div><div id="shot-analysis-result"></div><div class="shot-role-heading"><h3>Роли загруженных слоёв</h3><span>Пустые слои молчат. Роль определяет поведение в сценарии.</span></div><div class="shot-role-list">${tracks.map(track => {const layer = this.type.layers.find(layer => layer.id === track.layerId);return `<label><span>${escapeHtml(layer.name)}${layer.locked ? ' · закреплён' : ''}</span><select data-shot-role="${layer.id}">${Object.entries(shotRoles).map(([id,title]) => `<option value="${id}" ${layer.role === id ? 'selected' : ''}>${title}</option>`).join('')}</select></label>`;}).join('')}</div><div id="shot-plan-result"></div></div>
      <footer class="shot-footer"><span id="shot-status">Изменения сохраняются в проекте. Ctrl+Z отменяет применённую обработку.</span><button id="shot-done">Готово</button></footer>`;
    this.renderResult(); this.renderPlan();
  }
  slider(key, label, value, min, max, step, unit) {
    return `<label class="shot-slider"><span>${label}<output data-shot-output="${key}">${this.format(value, unit)}</output></span><input type="range" data-shot-param="${key}" min="${min}" max="${max}" step="${step}" value="${value}" aria-label="${label}"></label>`;
  }
  format(value, unit) { return unit === '%' ? `${Math.round(value * 100)}%` : `${Number(value.toFixed(2))} ${unit}`; }
  click(event) {
    const button = event.target.closest('button'); if (!button || button.disabled || this.working) return;
    this.hooks.run(async () => {
      if (button.id === 'shot-close' || button.id === 'shot-done') { this.dialog.close(); return; }
      if (button.dataset.shotTab) { this.stopPreview(); this.hooks.endPendingEdit(); this.mode = button.dataset.shotTab; this.render(); return; }
      if (button.dataset.spacePreset) { this.stopPreview(); this.hooks.commit(() => { this.design.environment = button.dataset.spacePreset; this.design.enabled = true; }); this.render(); }
      else if (button.id === 'shot-reset') { this.stopPreview(); this.hooks.commit(() => { this.type.shotDesign = defaultShotDesign(); }); this.render(); }
      else if (button.id === 'shot-preview-a' || button.id === 'shot-preview-b') await this.previewMix(button.id.endsWith('a'));
      else if (button.id === 'shot-stop') this.stopPreview();
      else if (button.id === 'shot-analyze') await this.analyze();
      else if (button.id === 'shot-create-layers') await this.createLayers();
      else if (button.id === 'shot-plan') await this.calculatePlan();
      else if (button.id === 'shot-apply-plan') await this.applyPlan();
      else if (button.id === 'shot-export-six' || button.id === 'shot-ring-six') await this.exportSix(button.id === 'shot-ring-six');
    });
  }
  input(event) {
    const key = event.target.dataset.shotParam; if (!key) return;
    this.stopPreview(); this.hooks.beginEdit(); this.design[key] = Number(event.target.value); this.design.enabled = true;
    const unit = key === 'size' ? '×' : key === 'output' ? 'дБ' : '%'; this.dialog.querySelector(`[data-shot-output="${key}"]`).textContent = this.format(this.design[key], unit);
    if (key === 'size') for (const button of this.dialog.querySelectorAll('[data-space-preset]')) {
      const preset = spacePresets[button.dataset.spacePreset];
      if (preset.decay) button.querySelector('i').textContent = `Хвост ${(preset.decay * this.design.size).toFixed(2)} с`;
    }
    $('shot-enabled').checked = true; this.engine.sync(); this.hooks.liveChange();
  }
  change(event) {
    const input = event.target;
    if (input.dataset.shotParam) { this.hooks.endEdit('sync'); return; }
    if (input.id === 'shot-enabled' || input.id === 'shot-suppressed') { this.stopPreview(); this.hooks.commit(() => { this.design[input.id === 'shot-enabled' ? 'enabled' : 'suppressed'] = input.checked; if (input.id === 'shot-suppressed') this.design.enabled = true; }); this.render(); }
    else if (input.id === 'shot-source') { this.sourceId = input.value; this.result = null; this.renderResult(); }
    else if (input.dataset.shotRole || ['shot-scenario','shot-auto-speed','shot-auto-balance'].includes(input.id)) { this.plan = null; this.renderPlan(); }
    else if (input.id === 'shot-loop' && this.previewNode) this.previewNode.loop = input.checked;
  }
  async task(title, action) {
    if (this.working) return; this.hooks.endPendingEdit(); this.stopPreview(); this.working = true; this.hooks.setBusy(title, 'Готовим аудио…');
    try { return await action(); } finally { this.working = false; this.hooks.clearBusy(); }
  }
  assertSnapshot(value) { if (this.state.project.id !== value.projectId || this.state.revision !== value.revision) throw new Error('Сборка изменилась. Рассчитайте результат заново.'); }
  async source(track) {
    const range = { start: trackStart(track), end: trackEnd(track) };
    if (range.end - range.start > 30) throw new Error('Для конструктора выберите дорожку с одиночным звуком длительностью до 30 секунд.');
    return { range, buffer: await renderAudio(this.state.project, this.engine.assets, [track.id], range, { includeDesign: false, includeMaster: false }) };
  }
  async analyze() {
    return this.task('Разбираем исходный выстрел', async () => {
      const track = this.state.project.tracks.find(track => track.id === this.sourceId); if (!track?.clips.length) throw new Error('Выберите дорожку с выстрелом.');
      const snapshot = { projectId: this.state.project.id, revision: this.state.revision };
      const { buffer, range } = await this.source(track), result = splitShot(channels(buffer), buffer.sampleRate);
      this.assertSnapshot(snapshot); this.result = { ...snapshot, trackId: track.id, range, ...result, rate: buffer.sampleRate };
      this.renderResult();
    });
  }
  renderResult() {
    const root = $('shot-analysis-result'); if (!root) return;
    root.innerHTML = this.result ? `<div class="shot-result"><div><h3>Пять частей готовы к сборке</h3><p>Начало: ${(this.result.analysis.onset * 1000).toFixed(1)} мс · пик ${this.result.analysis.peakDb.toFixed(1)} дБ · основа ${(this.result.analysis.bodyEnd * 1000).toFixed(0)} мс</p></div><div class="shot-part-tags">${Object.keys(this.result.layers).map(role => `<span>${role === 'gas' ? 'Шумовая часть / газы' : shotRoles[role]}</span>`).join('')}</div><p>Исходная дорожка сохранится в выключенном слое для сравнения. Новые части станут выбранными вариантами соответствующих слоёв; остальные записи сохранятся.</p><button id="shot-create-layers">Создать слои · можно отменить</button></div>` : '';
  }
  async createLayers() {
    if (!this.result) return;
    return this.task('Создаём слои выстрела', async () => {
      const result = this.result; this.assertSnapshot(result);
      const project = this.state.project, type = this.type, source = project.tracks.find(track => track.id === result.trackId), sourceLayer = type.layers.find(layer => layer.id === source.layerId), roles = Object.keys(result.layers);
      if (project.tracks.length + 5 > MAX_TRACKS || project.assets.length + 5 > 2000) throw new Error('Недостаточно места для пяти новых вариантов.');
      const targets = new Map(), sourceRole = roles.includes(sourceLayer.role) ? sourceLayer.role : 'low';
      targets.set(sourceRole, sourceLayer);
      for (const role of roles) if (!targets.has(role)) targets.set(role, type.layers.find(layer => layer.role === role) || null);
      if (type.layers.length + 1 + [...targets.values()].filter(layer => !layer).length > MAX_LAYERS) throw new Error('Не хватает места для новых слоёв. Удалите неиспользуемые пустые слои.');
      for (const layer of targets.values()) if (layer && variantsOf(project, layer.id).filter(track => track.id !== source.id).length >= MAX_VARIANTS) throw new Error(`В слое «${layer.name}» уже ${MAX_VARIANTS} вариантов.`);
      const assets = [], context = await this.engine.ensureContext();
      for (const role of roles) {
        const data = result.layers[role], buffer = context.createBuffer(data.length, data[0].length, result.rate);
        data.forEach((channel, index) => buffer.copyToChannel(channel, index));
        assets.push({ role, asset: await this.engine.addBuffer(`${source.name}_${role}_слой.wav`, buffer) });
      }
      this.assertSnapshot(result); const group = uid();
      this.hooks.commit(() => {
        const backup = addLayer(project, `Исходник · ${source.name}`); backup.role = 'reference'; backup.enabled = false; assignVariant(project, source, backup);
        sourceLayer.role = sourceRole; if (sourceRole === 'low') sourceLayer.name = shotRoles.low;
        for (const { role, asset } of assets) {
          const layer = targets.get(role) || addLayer(project, shotRoles[role]); layer.role = role; layer.enabled = true;
          const track = createTrack(project.tracks.length, `${role === 'gas' ? 'Шумовая часть' : shotRoles[role]} · из записи`);
          track.decompositionGroup = group; track.decompositionOnset = result.analysis.onset;
          track.clips = [{ ...createClip(asset, result.range.start), fadeIn: 0, fadeOut: 0 }];
          project.assets.push(metadata(asset)); assignVariant(project, track, layer);
          this.state.selectedTrackId = track.id;
        }
        this.state.activeLayerId = null; this.state.selectedClipIds.clear(); this.state.selection = null; this.state.loopMode = 'project'; this.state.playOnlyTrackId = null;
      }, 'restart');
      this.result = null; this.plan = null; this.render(); this.hooks.toast('Создано пять слоёв. Исходник сохранён в выключенном слое; Ctrl+Z вернёт прежнюю сборку.');
    });
  }
  async calculatePlan() {
    const options = { scenario: $('shot-scenario').value, speed: $('shot-auto-speed').checked, balance: $('shot-auto-balance').checked };
    const roles = new Map([...this.dialog.querySelectorAll('[data-shot-role]')].map(input => [input.dataset.shotRole, input.value]));
    return this.task('Рассчитываем исполнение слоёв', async () => {
      const snapshot = { projectId: this.state.project.id, revision: this.state.revision }, entries = [];
      for (const track of enabledTracks(this.state.project).filter(track => track.clips.length && !track.muted)) {
        const layer = this.type.layers.find(layer => layer.id === track.layerId), role = roles.get(layer.id) || layer.role;
        if (role === 'reference' || role === 'other') continue;
        const { buffer, range } = await this.source(track);
        if (!channels(buffer).some(data => data.some(sample => Math.abs(sample) >= 1e-7))) continue;
        const stats = analyzeShot(channels(buffer), buffer.sampleRate);
        const intact = track.decompositionGroup && track.clips.length === 1 && (track.clips[0].speed ?? 1) === 1 && track.clips[0].offset === 0;
        entries.push({ trackId: track.id, layerId: layer.id, name: layer.name, role, locked: layer.locked, stats, start: range.start, volume: track.volume, speed: trackSpeed(track), originOnset: intact ? track.decompositionOnset : undefined });
      }
      this.assertSnapshot(snapshot); this.plan = { ...snapshot, ...planShot(entries, options), roles: [...roles] }; this.renderPlan();
    });
  }
  renderPlan() {
    const root = $('shot-plan-result'); if (!root) return;
    root.innerHTML = this.plan ? `<div class="shot-result"><h3>Сценарий готов · выстрел на ${this.plan.shotAt.toFixed(3)} с</h3><table><thead><tr><th>Слой</th><th>Роль</th><th>Позиция</th><th>Скорость</th><th>Уровень</th></tr></thead><tbody>${this.plan.rows.map(row => `<tr><td>${escapeHtml(row.name)}</td><td>${shotRoles[row.role]}</td><td>${(row.start + row.delta).toFixed(3)} с</td><td>${row.speed === null ? 'разная' : row.rate + '×'}</td><td>${row.volume} дБ</td></tr>`).join('')}</tbody></table><p>Сдвигаются выбранные варианты целиком. Высота при ускорении сохраняется. Части одного разложения остаются синхронными.${this.plan.skipped ? ` Пропущено закреплённых слоёв: ${this.plan.skipped}.` : ''}</p><button id="shot-apply-plan" ${this.plan.rows.length ? '' : 'disabled'}>Применить сценарий · можно отменить</button></div>` : '';
  }
  async applyPlan() {
    if (!this.plan) return;
    return this.task('Применяем сценарий выстрела', async () => {
      const plan = this.plan; this.assertSnapshot(plan); const prepared = [];
      for (let i = 0; i < plan.rows.length; i++) {
        const row = plan.rows[i], track = this.state.project.tracks.find(track => track.id === row.trackId);
        this.hooks.setBusy('Исполнение слоёв', `${i + 1} / ${plan.rows.length} · ${row.name}`, i / plan.rows.length);
        prepared.push({ row, track, ...(row.speed === null ? { clips: structuredClone(track.clips), assets: [] } : await prepareShotSpeed(track, row.rate, this.engine, this.cache)) });
        if (row.speed !== null && row.rate !== row.speed) {
          const staged = structuredClone(this.state.project), stagedTrack = { ...structuredClone(track), clips: prepared.at(-1).clips };
          staged.tracks = [stagedTrack];
          const range = { start: trackStart(stagedTrack), end: trackEnd(stagedTrack) };
          const buffer = await renderAudio(staged, this.engine.assets, [track.id], range, { includeDesign: false, includeMaster: false });
          const onset = analyzeShot(channels(buffer), buffer.sampleRate).onset;
          // Rubber Band may shift a transient by a few milliseconds. Align the rendered onset.
          prepared.at(-1).delta = row.start + row.delta + row.stats.onset * row.speed / row.rate - range.start - onset;
        } else prepared.at(-1).delta = row.delta;
        if (prepared.at(-1).clips.some(clip => clip.start + prepared.at(-1).delta > 7200)) throw new Error('Сценарий выйдет за пределы двух часов проекта.');
      }
      this.assertSnapshot(plan);
      const padding = Math.max(0, ...prepared.flatMap(item => item.clips.map(clip => -(clip.start + item.delta))));
      if (padding > .00001 && this.type.layers.some(layer => layer.locked && layer.enabled)) throw new Error('После ускорения нужен запас в начале. Освободите закреплённые слои или отключите ускорение.');
      const unique = new Map(prepared.flatMap(item => item.assets.map(asset => [asset.id, asset])));
      if (this.state.project.assets.length + [...unique.keys()].filter(id => !this.state.project.assets.some(asset => asset.id === id)).length > 2000) throw new Error('Слишком много исходников для изменения скорости.');
      this.hooks.commit(() => {
        for (const asset of unique.values()) if (!this.state.project.assets.some(item => item.id === asset.id)) this.state.project.assets.push({ ...metadata(asset), derived: true });
        for (const { row, track, clips, delta } of prepared) { track.clips = clips.map(clip => ({ ...clip, start: Math.max(0, clip.start + delta + padding) })); track.volume = row.volume; }
        for (const [id, role] of plan.roles) { const layer = this.type.layers.find(layer => layer.id === id); if (layer) layer.role = role; }
        this.state.activeLayerId = null; this.state.selectedClipIds.clear(); this.state.selection = null; this.state.loopMode = 'project'; this.state.playOnlyTrackId = null;
      }, 'restart');
      this.plan = null; this.render(); this.hooks.toast('Слои синхронизированы. Все изменения можно отменить одним Ctrl+Z.');
    });
  }
  async previewMix(dry) {
    return this.task('Готовим прослушивание', async () => {
      const project = structuredClone(this.state.project), ids = audibleTracks(project).filter(track => track.clips.length).map(track => track.id);
      if (!ids.length) throw new Error('Добавьте звук для прослушивания.');
      if (dry) currentSoundType(project).shotDesign.enabled = false;
      const buffer = await renderAudio(project, this.engine.assets, ids, { start: 0, end: projectEnd(project) });
      await this.playBuffer(buffer); $('shot-status').textContent = dry ? 'A · исходная сборка без общего пресета' : 'B · сборка с пространством и характером';
    });
  }
  async playBuffer(buffer) {
    this.stopPreview(); if (this.engine.playing) { this.state.cursor = this.engine.pause(); this.hooks.updateTransport(); }
    const context = await this.engine.ensureContext(); this.previewNode = context.createBufferSource(); this.previewNode.buffer = buffer; this.previewNode.loop = $('shot-loop').checked; this.previewNode.connect(context.destination); this.previewNode.onended = () => this.stopPreview(); this.previewNode.start();
  }
  stopPreview() { if (this.previewNode) { this.previewNode.onended = null; try { this.previewNode.stop(); } catch {} this.previewNode.disconnect(); this.previewNode = null; } }
  async exportSix(toRing) {
    const environments = ['small','large','outdoor'], jobs = environments.flatMap(environment => [false,true].map(suppressed => ({ environment, suppressed, name: `${this.state.project.name}_${{small:'комната',large:'зал',outdoor:'улица'}[environment]}_${suppressed ? 'глушитель' : 'обычный'}` })));
    if (!toRing && !await window.sonora.chooseExport({ format: 'wav', separate: true, names: jobs.map(job => job.name), name: this.state.project.name })) return;
    return this.task('Шесть вариаций выстрела', async () => {
      const project = structuredClone(this.state.project), ids = enabledTracks(project).filter(track => track.export && track.clips.length).map(track => track.id), range = { start: 0, end: projectEnd(project) }, items = [];
      if (!ids.length) throw new Error('Отметьте слои для экспорта.');
      for (let i = 0; i < jobs.length; i++) {
        const job = jobs[i]; this.hooks.setBusy('Создаём вариации', `${i + 1} / 6 · ${job.name}`, i / 6);
        Object.assign(currentSoundType(project).shotDesign, { enabled: true, environment: job.environment, suppressed: job.suppressed });
        const buffer = await renderAudio(project, this.engine.assets, ids, range), bytes = encodeWav(buffer, true);
        if (toRing) items.push({ name: job.name, bytes }); else await window.sonora.writeExport(bytes, { index: i, format: 'wav', sampleRate: 48000, bitDepth: '24' });
      }
      if (toRing) await window.sonora.sendToRing(items);
      this.hooks.toast(toRing ? 'Шесть вариантов переданы на стенд Ring. Выберите событие и утвердите нужную запись.' : 'Сохранены шесть WAV: три пространства, обычный и приглушённый выстрел.');
    });
  }
}
