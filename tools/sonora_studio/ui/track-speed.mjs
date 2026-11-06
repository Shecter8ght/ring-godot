import { encodeWav } from './audio.mjs';
import { escapeHtml } from './timeline.mjs';
import { trackSpeed, retimeClip } from './speed-model.mjs';
export class TrackSpeed {
  constructor(state, engine, hooks) {
    this.state = state; this.engine = engine; this.hooks = hooks; this.cache = new Map(); this.working = false;
    this.element = document.createElement('section'); this.element.className = 'track-speed-panel'; this.element.id = 'track-speed-panel';
    document.getElementById('clip-inspector').before(this.element);
    this.element.addEventListener('click', event => {
      const button = event.target.closest('button'); if (!button) return;
      const value = button.dataset.rate ?? this.element.querySelector('#track-speed-value')?.value;
      this.hooks.run(() => this.apply(Number(value)));
    });
    this.element.addEventListener('keydown', event => { if (event.key === 'Enter' && event.target.id === 'track-speed-value') { event.preventDefault(); event.stopPropagation(); this.hooks.run(() => this.apply(Number(event.target.value))); } });
  }
  get track() { return this.state.project.tracks.find(track => track.id === this.state.selectedTrackId); }
  render() {
    const track = this.track, speed = trackSpeed(track);
    this.element.innerHTML = `<div class="inspector-title">СКОРОСТЬ ДОРОЖКИ <span>×</span></div><div class="speed-track-name">${track ? escapeHtml(track.name) : 'Выберите дорожку'}</div><div class="speed-input-row"><label><input id="track-speed-value" aria-label="Скорость дорожки" type="number" min="0.25" max="8" step="0.05" value="${speed ?? ''}" placeholder="Разная" ${track?.clips.length && !this.working ? '' : 'disabled'}><span>×</span></label><button id="apply-track-speed" ${track?.clips.length && !this.working ? '' : 'disabled'}>Применить</button></div><div class="speed-presets">${[.5, 1, 2, 4, 8].map(rate => `<button data-rate="${rate}" class="${speed === rate ? 'active' : ''}" ${track?.clips.length && !this.working ? '' : 'disabled'}>${rate}×</button>`).join('')}</div><p>Высота звука сохраняется.<br>1× возвращает исходную скорость.</p>`;
  }
  focus() { this.element.scrollIntoView({ block: 'nearest' }); const input = this.element.querySelector('input'); input?.focus(); input?.select(); }
  async apply(speed) {
    const track = this.track;
    if (!track?.clips.length || this.working) return;
    if (!Number.isFinite(speed) || speed < .25 || speed > 8) throw new Error('Укажите скорость от 0,25× до 8×.');
    if (track.clips.every(clip => (clip.speed ?? 1) === speed)) return;
    this.hooks.endPendingEdit(); this.working = true;
    const project = this.state.project, revision = this.state.revision, wasPlaying = this.engine.playing, position = wasPlaying ? this.engine.pause() : this.state.cursor;
    this.hooks.setBusy('Меняем скорость дорожки', 'Сохраняем высоту звука…', 0);
    try {
      const sources = [...new Set(track.clips.map(clip => clip.sourceAssetId || clip.assetId))], prepared = new Map();
      if (project.assets.length + sources.filter(id => !this.cache.has(`${id}:${speed}`) && speed !== 1).length > 2000) throw new Error('В проекте слишком много исходников.');
      for (let i = 0; i < sources.length; i++) {
        const id = sources[i], source = this.engine.assets.get(id);
        if (!source) throw new Error('Исходный звук не найден.');
        this.hooks.setBusy('Меняем скорость дорожки', `${i + 1} / ${sources.length} · ${source.name}`, i / sources.length);
        let asset = speed === 1 ? source : this.engine.assets.get(this.cache.get(`${id}:${speed}`));
        if (!asset) {
          const bytes = await window.sonora.processAudio(encodeWav(source.buffer), { pitch: 0, speed, mode: 'independent', formant: true });
          asset = await this.engine.decode(`${source.name.replace(/\.(wav|mp3|ogg)$/i, '')}_${speed}x.wav`, bytes);
          this.cache.set(`${id}:${speed}`, asset.id);
        }
        prepared.set(id, asset);
      }
      if (this.state.project !== project || this.state.revision !== revision) throw new Error('Проект изменился во время обработки. Повторите действие.');
      const previousSpeed = trackSpeed(track), anchor = Math.min(...track.clips.map(clip => clip.start));
      const clips = track.clips.map(clip => ({ ...retimeClip(clip, prepared.get(clip.sourceAssetId || clip.assetId), speed),
        start: previousSpeed === null ? clip.start : anchor + (clip.start - anchor) * previousSpeed / speed }));
      this.hooks.commit(() => {
        for (const asset of prepared.values()) if (!project.assets.some(item => item.id === asset.id)) project.assets.push({ id: asset.id, name: asset.name, duration: asset.duration, sampleRate: asset.sampleRate, channels: asset.channels, derived: true });
        track.clips = clips;
      }, 'none');
      this.hooks.toast(`Скорость ${speed}×. Высота звука сохранена.`);
    } finally {
      this.working = false; this.hooks.clearBusy(); this.render();
      if (wasPlaying) { this.state.cursor = position; await this.hooks.resume(position); }
      else this.hooks.updateTransport();
    }
  }
}
