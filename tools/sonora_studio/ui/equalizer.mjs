import { clamp, MAX_BANDS, createTrack } from './model.mjs';

const BAND_COLORS = ['#ae9bdc', '#9ba9e2', '#81b1e2', '#78bace', '#80bfac', '#9fc296', '#c2c08c', '#d7b286', '#d59f9e', '#bd9cbf', '#9fa7db', '#87bbbd'];
const typeOptions = [['peaking', 'Bell'], ['lowshelf', 'НЧ полка'], ['highshelf', 'ВЧ полка'], ['lowpass', 'Срез ВЧ'], ['highpass', 'Срез НЧ']];
export class Equalizer {
  constructor(state, engine, hooks) {
    this.state = state; this.engine = engine; this.hooks = hooks;
    this.container = document.getElementById('eq-bands'); this.canvas = document.getElementById('eq-graph');
    this.preview = createTrack(); this.selectedBandId = null; this.spectrum = new Uint8Array(1024);
    this.container.addEventListener('pointerdown', event => {
      const strip = event.target.closest('.eq-band');
      if (strip) { this.selectBand(strip.dataset.bandId); }
    });
    this.container.addEventListener('input', event => this.input(event));
    this.container.addEventListener('change', event => this.change(event));
    this.container.addEventListener('click', event => this.click(event));
    this.canvas.addEventListener('pointerdown', event => this.pointerDown(event));
    this.canvas.addEventListener('wheel', event => this.wheel(event), { passive: false });
    document.addEventListener('pointermove', event => this.pointerMove(event));
    document.addEventListener('pointerup', () => this.pointerUp());
    this.resizeObserver = new ResizeObserver(() => { this.curveKey = ''; this.draw(); });
    this.resizeObserver.observe(this.canvas);
  }
  track() { return this.state.project.tracks.find(track => track.id === this.state.selectedTrackId) || null; }
  band() { return this.track()?.bands.find(band => band.id === this.selectedBandId); }
  selectBand(id) {
    this.selectedBandId = id;
    for (const strip of this.container.querySelectorAll('.eq-band')) strip.classList.toggle('selected', strip.dataset.bandId === id);
    this.updateReadout(); this.draw();
  }
  render() {
    const actual = this.track(), track = actual || this.preview;
    if (!track.bands.some(band => band.id === this.selectedBandId)) this.selectedBandId = track.bands[0]?.id;
    document.getElementById('eq-track-name').textContent = actual ? track.name : 'Выберите дорожку';
    document.getElementById('eq-track-dot').style.background = track.color;
    document.querySelector('.eq-content').classList.toggle('inactive', !actual);
    document.getElementById('eq-power').classList.toggle('active', !!actual && track.eqEnabled);
    document.getElementById('eq-power').setAttribute('aria-pressed', String(!!actual && track.eqEnabled));
    for (const id of ['eq-power', 'load-preset', 'save-preset', 'eq-reset', 'add-band', 'eq-preset']) document.getElementById(id).disabled = !actual || (id === 'add-band' && track.bands.length >= MAX_BANDS);
    this.container.innerHTML = track.bands.map((band, index) => {
      const color = BAND_COLORS[index % BAND_COLORS.length];
      const noGain = ['lowpass', 'highpass'].includes(band.type), noQ = ['lowshelf', 'highshelf'].includes(band.type);
      return `<div class="eq-band ${band.id === this.selectedBandId ? 'selected' : ''} ${!band.enabled ? 'disabled' : ''}" data-band-id="${band.id}" style="--band-color:${color}"><div class="eq-band-top"><button class="band-enable" data-action="enable" title="Включить / отключить полосу ${index + 1}" aria-label="Полоса ${index + 1}: включить или отключить" aria-pressed="${band.enabled}"><i></i>${String(index + 1).padStart(2, '0')}</button><button class="band-remove" data-action="remove" title="Удалить полосу" aria-label="Удалить полосу ${index + 1}">×</button></div><input class="band-frequency" type="number" min="20" max="20000" step="1" value="${Math.round(band.frequency)}" data-param="frequency" title="Частота, Гц" aria-label="Частота полосы ${index + 1}, Гц"><select class="band-type" data-param="type" title="Тип фильтра" aria-label="Тип полосы ${index + 1}">${typeOptions.map(([value, text]) => `<option value="${value}" ${value === band.type ? 'selected' : ''}>${text}</option>`).join('')}</select><div class="eq-gain-wrap"><input class="eq-gain" type="range" min="-24" max="24" step="0.1" value="${band.gain}" data-param="gain" ${noGain ? 'disabled' : ''} aria-label="Усиление полосы ${index + 1}, дБ"></div><input class="band-gain-value" type="number" min="-24" max="24" step="0.1" value="${band.gain.toFixed(1)}" data-param="gain" ${noGain ? 'disabled' : ''} title="Усиление, дБ" aria-label="Усиление полосы ${index + 1}, число"><label class="band-q-wrap" title="Ширина полосы: меньше Q — шире диапазон">Q<input class="band-q" type="number" min="0.1" max="18" step="0.05" value="${Number(band.q.toFixed(3))}" data-param="q" ${noQ ? 'disabled' : ''} aria-label="Ширина Q полосы ${index + 1}"></label></div>`;
    }).join('');
    this.curveKey = ''; this.updateReadout(); this.draw();
  }
  updateReadout() {
    const band = this.band();
    document.getElementById('eq-band-readout').textContent = band ? `${Math.round(band.frequency)} Гц · ${band.gain > 0 ? '+' : ''}${band.gain.toFixed(1)} дБ · Q ${band.q.toFixed(2)}` : '20 Гц — 20 кГц';
  }
  input(event) {
    const input = event.target, parameter = input.dataset.param;
    if (!parameter || parameter === 'type') return;
    const band = this.track()?.bands.find(item => item.id === input.closest('.eq-band').dataset.bandId);
    if (!band) return;
    const value = input.valueAsNumber;
    const limits = { frequency: [20, 20000], gain: [-24, 24], q: [0.1, 18] }[parameter];
    if (!Number.isFinite(value) || value < limits[0] || value > limits[1]) return;
    if (!this.inputGesture) { this.hooks.beginEdit(); this.inputGesture = true; }
    band[parameter] = value;
    const strip = input.closest('.eq-band');
    for (const other of strip.querySelectorAll(`[data-param="${parameter}"]`)) if (other !== input) other.value = parameter === 'gain' ? value.toFixed(1) : value;
    this.engine.sync(); this.hooks.liveChange(); this.updateReadout(); this.draw();
  }
  change(event) {
    if (event.target.dataset.param === 'type') {
      const band = this.track()?.bands.find(item => item.id === event.target.closest('.eq-band').dataset.bandId);
      if (!band) return;
      this.hooks.beginEdit(); band.type = event.target.value; this.hooks.endEdit('sync'); this.render();
    } else if (event.target.dataset.param) {
      if (this.inputGesture) { this.inputGesture = false; this.hooks.endEdit('sync'); }
      this.render();
    }
  }
  click(event) {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const track = this.track(), bandId = button.closest('.eq-band').dataset.bandId;
    if (!track) return;
    if (button.dataset.action === 'remove' && track.bands.length <= 1) { this.hooks.toast('В эквалайзере должна остаться хотя бы одна полоса.'); return; }
    this.hooks.beginEdit();
    if (button.dataset.action === 'enable') { const band = track.bands.find(item => item.id === bandId); band.enabled = !band.enabled; }
    else track.bands = track.bands.filter(item => item.id !== bandId);
    this.hooks.endEdit('sync'); this.render();
  }
  coordinates() {
    const rect = this.canvas.getBoundingClientRect();
    return { width: rect.width, height: rect.height, left: 30, right: rect.width - 9, top: 9, bottom: rect.height - 20 };
  }
  point(band, geometry) {
    return { x: geometry.left + Math.log(band.frequency / 20) / Math.log(1000) * (geometry.right - geometry.left), y: geometry.top + (24 - (['lowpass', 'highpass'].includes(band.type) ? 0 : band.gain)) / 48 * (geometry.bottom - geometry.top) };
  }
  draw() {
    const canvas = this.canvas, geometry = this.coordinates();
    if (geometry.width < 40 || geometry.height < 40) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(geometry.width * ratio) || canvas.height !== Math.round(geometry.height * ratio)) { canvas.width = Math.round(geometry.width * ratio); canvas.height = Math.round(geometry.height * ratio); this.curveKey = ''; }
    const context = canvas.getContext('2d'); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, geometry.width, geometry.height);
    const g = geometry, track = this.track() || this.preview;
    context.font = '8px Consolas, monospace'; context.lineWidth = 1;
    for (const frequency of [20, 50, 100, 500, 1000, 5000, 10000, 20000]) {
      const x = g.left + Math.log(frequency / 20) / Math.log(1000) * (g.right - g.left);
      context.strokeStyle = '#34405870'; context.beginPath(); context.moveTo(x, g.top); context.lineTo(x, g.bottom); context.stroke();
      if (![50, 500, 5000].includes(frequency)) { context.fillStyle = '#667d9e'; context.textAlign = frequency === 20 ? 'left' : frequency === 20000 ? 'right' : 'center'; context.fillText(frequency >= 1000 ? `${frequency / 1000}k` : `${frequency}`, x, g.height - 6); }
    }
    for (const db of [-24, -12, 0, 12, 24]) {
      const y = g.top + (24 - db) / 48 * (g.bottom - g.top);
      context.strokeStyle = db === 0 ? '#576b8b80' : '#34405860'; context.beginPath(); context.moveTo(g.left, y); context.lineTo(g.right, y); context.stroke();
      context.textAlign = 'right'; context.fillStyle = '#637999'; context.fillText(db > 0 ? `+${db}` : `${db}`, g.left - 7, y + 3);
    }
    if (this.engine.spectrum(track.id, this.spectrum)) {
      context.fillStyle = '#7899bd1e'; context.beginPath(); context.moveTo(g.left, g.bottom);
      for (let pixel = 0; pixel <= g.right - g.left; pixel += 2) {
        const frequency = 20 * 1000 ** (pixel / (g.right - g.left));
        const bin = Math.min(1023, Math.round(frequency / (this.engine.context.sampleRate / 2) * 1024));
        const y = g.bottom - this.spectrum[bin] / 255 * (g.bottom - g.top) * .9;
        context.lineTo(g.left + pixel, y);
      }
      context.lineTo(g.right, g.bottom); context.closePath(); context.fill();
    }
    const key = `${g.width},${g.height},${track.eqEnabled},${JSON.stringify(track.fx?.tone)},${track.bands.map(band => `${band.frequency},${band.gain},${band.q},${band.type},${band.enabled}`).join(';')}`;
    if (this.curveKey !== key) {
      const count = Math.ceil(g.right - g.left) + 1;
      const frequencies = Float32Array.from({ length: count }, (_, index) => 20 * 1000 ** (index / (count - 1)));
      this.curve = this.engine.response(track, frequencies); this.curveKey = key;
    }
    if (this.curve?.length) {
      context.save(); context.beginPath(); context.rect(g.left, g.top - 1, g.right - g.left, g.bottom - g.top + 2); context.clip();
      context.beginPath();
      for (let i = 0; i < this.curve.length; i++) { const x = g.left + i / (this.curve.length - 1) * (g.right - g.left), y = g.top + (24 - this.curve[i]) / 48 * (g.bottom - g.top); if (!i) context.moveTo(x, y); else context.lineTo(x, y); }
      context.strokeStyle = track.eqEnabled ? '#edb27f' : '#677e9d'; context.lineWidth = 1.65; context.stroke();
      const lastX = g.right, zeroY = (g.top + g.bottom) / 2;
      context.lineTo(lastX, zeroY); context.lineTo(g.left, zeroY); context.closePath();
      context.fillStyle = track.eqEnabled ? '#edb27f0c' : '#617a9910'; context.fill(); context.restore();
    }
    track.bands.forEach((band, index) => {
      const point = this.point(band, g), selected = band.id === this.selectedBandId;
      if (selected) { context.fillStyle = `${BAND_COLORS[index % BAND_COLORS.length]}20`; context.beginPath(); context.arc(point.x, point.y, 8, 0, Math.PI * 2); context.fill(); }
      context.fillStyle = band.enabled && track.eqEnabled ? BAND_COLORS[index % BAND_COLORS.length] : '#39485f'; context.strokeStyle = selected ? '#dbe8f8' : '#101a2c'; context.lineWidth = selected ? 1.5 : 1;
      context.beginPath(); context.arc(point.x, point.y, selected ? 4 : 3, 0, Math.PI * 2); context.fill(); context.stroke();
    });
  }
  pointerDown(event) {
    if (event.button !== 0 || !this.track()) return;
    const rect = this.canvas.getBoundingClientRect(), g = this.coordinates();
    const x = event.clientX - rect.left, y = event.clientY - rect.top;
    let nearest = null, distance = 18;
    for (const band of this.track().bands) { const point = this.point(band, g), next = Math.hypot(point.x - x, point.y - y); if (next < distance) { nearest = band; distance = next; } }
    if (!nearest) return;
    this.selectBand(nearest.id); this.drag = { band: nearest, x: event.clientX, y: event.clientY, started: false };
    event.preventDefault();
  }
  pointerMove(event) {
    if (!this.drag) return;
    const drag = this.drag;
    if (!drag.started && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 2) return;
    if (!drag.started) { drag.started = true; this.hooks.beginEdit(); }
    const rect = this.canvas.getBoundingClientRect(), g = this.coordinates();
    const x = clamp(event.clientX - rect.left, g.left, g.right), y = clamp(event.clientY - rect.top, g.top, g.bottom);
    drag.band.frequency = Math.round(20 * 1000 ** ((x - g.left) / (g.right - g.left)));
    if (!['lowpass', 'highpass'].includes(drag.band.type)) drag.band.gain = Math.round((24 - (y - g.top) / (g.bottom - g.top) * 48) * 10) / 10;
    const strip = this.container.querySelector(`[data-band-id="${drag.band.id}"]`);
    if (strip) { strip.querySelector('[data-param="frequency"]').value = drag.band.frequency; for (const input of strip.querySelectorAll('[data-param="gain"]')) input.value = drag.band.gain.toFixed(1); }
    this.engine.sync(); this.hooks.liveChange(); this.updateReadout(); this.draw();
  }
  pointerUp() { if (this.drag?.started) this.hooks.endEdit('sync'); this.drag = null; }
  wheel(event) {
    const band = this.band(); if (!band || ['lowshelf', 'highshelf'].includes(band.type)) return;
    event.preventDefault();
    if (!this.wheelGesture) { this.wheelGesture = true; this.hooks.beginEdit(); }
    band.q = Math.round(clamp(band.q * Math.exp(-event.deltaY * 0.003), 0.1, 18) * 1000) / 1000;
    this.engine.sync(); this.hooks.liveChange(); this.updateReadout(); this.draw();
    const strip = this.container.querySelector(`[data-band-id="${band.id}"]`); if (strip) strip.querySelector('[data-param="q"]').value = band.q;
    clearTimeout(this.wheelTimer); this.wheelTimer = setTimeout(() => { this.wheelGesture = false; this.hooks.endEdit('sync'); }, 250);
  }
}
