import * as THREE from 'three';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';

const stateSelect = document.querySelector('#state');
const groups = document.querySelector('#groups');
const cards = document.querySelector('#candidates');
const heading = document.querySelector('#heading');
const count = document.querySelector('#count');
const notice = document.querySelector('#notice');
const decisions = JSON.parse(localStorage.getItem('ring-animation-decisions') || '{}');
let data, current, visible = [], previews = [], generation = 0;
let playing = true, phase = 0, previousTime = performance.now();

function save() { localStorage.setItem('ring-animation-decisions', JSON.stringify(decisions)); }
function keyFor(family, state) { return `${family}/${state}`; }
function getState() { const [family, state] = current.split('/'); return data[family][state]; }
function setNotice(message) { notice.textContent = message; }

function disposeObject(object) {
  object.traverse(node => {
    if (node.geometry) node.geometry.dispose();
    if (node.material) {
      for (const material of [].concat(node.material)) {
        for (const value of Object.values(material)) if (value?.isTexture) value.dispose();
        material.dispose();
      }
    }
  });
}
function clearPreviews() {
  generation++;
  for (const preview of previews) {
    preview.observer?.disconnect();
    preview.mixer?.stopAllAction();
    disposeObject(preview.scene);
    preview.renderer.dispose();
    preview.renderer.forceContextLoss();
    preview.renderer.domElement.remove();
  }
  previews = [];
  cards.replaceChildren();
}

function renderNav() {
  stateSelect.replaceChildren(); groups.replaceChildren();
  for (const [family, states] of Object.entries(data)) {
    const optgroup = document.createElement('optgroup'); optgroup.label = family.toUpperCase();
    const headingEl = document.createElement('small'); headingEl.textContent = family.toUpperCase(); groups.append(headingEl);
    for (const [state, info] of Object.entries(states)) {
      const key = keyFor(family, state);
      const opt = new Option(`${info.label} (${info.candidates.length})`, key); optgroup.append(opt);
      const button = document.createElement('button'); button.className = 'group' + (key === current ? ' active' : '') + (info.candidates.length ? '' : ' empty');
      button.textContent = `${info.label.split(' / ').at(-1)} · ${info.candidates.length}`;
      button.onclick = () => openGroup(key); groups.append(button);
    }
    stateSelect.append(optgroup);
  }
  stateSelect.value = current;
}

function openGroup(key) {
  current = key; phase = 0; clearPreviews(); renderNav();
  const info = getState(); heading.textContent = info.label;
  count.textContent = `${info.candidates.length} кандидатов · показывается до 4`;
  visible = info.candidates.slice(0, 4).map(candidate => candidate.path);
  setNotice(info.candidates.length ? 'Оценка качества остаётся за визуальным просмотром.' : 'В библиотеке нет уверенного кандидата для этого состояния.');
  renderCards();
}

function renderCards() {
  clearPreviews();
  const info = getState();
  for (const path of visible) {
    const candidate = info.candidates.find(item => item.path === path);
    if (candidate) addCard(candidate, info.label);
  }
  const hidden = info.candidates.filter(item => !visible.includes(item.path));
  if (hidden.length) {
    const extra = document.createElement('div'); extra.className = 'extra';
    const label = document.createElement('span'); label.textContent = 'Ещё кандидаты:';
    const pick = document.createElement('select');
    for (const candidate of hidden) pick.add(new Option(`${candidate.sourcePack} / ${candidate.filename}`, candidate.path));
    const show = document.createElement('button'); show.textContent = 'Сравнить вместо последнего';
    show.onclick = () => { visible[visible.length - 1] = pick.value; phase = 0; renderCards(); };
    extra.append(label, pick, show); cards.append(extra);
  }
}

function addCard(candidate, label) {
  const card = document.createElement('article'); card.className = 'card';
  const top = document.createElement('div'); top.className = 'card-top';
  const name = document.createElement('strong'); name.textContent = candidate.filename;
  const pack = document.createElement('span'); pack.textContent = candidate.sourcePack; top.append(name, pack);
  const area = document.createElement('div'); area.className = 'preview';
  const overlay = document.createElement('div'); overlay.className = 'overlay'; overlay.textContent = 'Загрузка FBX…'; area.append(overlay);
  const details = document.createElement('div'); details.className = 'details';
  for (const [key, value] of [
    ['Состояние', label], ['Файл', candidate.filename], ['Набор', candidate.sourcePack],
    ['Путь', candidate.path], ['Размер', `${(candidate.bytes / 1048576).toFixed(2)} MiB`],
    ['Дубли', candidate.duplicateGroup ? `${candidate.duplicateGroup}: ${candidate.duplicatePaths.join(', ')}` : 'Точных дублей нет'],
    ['Причины', candidate.reason.join('; ')]]) {
    const p = document.createElement('p'); const b = document.createElement('b'); b.textContent = `${key}: `;
    p.append(b, document.createTextNode(value)); details.append(p);
  }
  const actions = document.createElement('div'); actions.className = 'actions';
  for (const status of ['SELECT', 'MAYBE', 'REJECT']) {
    const button = document.createElement('button'); button.textContent = status;
    button.className = `${status.toLowerCase()}${decisions[candidate.path] === status ? ' on' : ''}`;
    button.onclick = () => { if (decisions[candidate.path] === status) delete decisions[candidate.path]; else decisions[candidate.path] = status; save();
      card.className = `card ${decisions[candidate.path]?.toLowerCase() || ''}`;
      for (const child of actions.querySelectorAll('button[data-status]')) child.classList.toggle('on', decisions[candidate.path] === child.dataset.status);
    };
    button.dataset.status = status; actions.append(button);
  }
  const copy = document.createElement('button'); copy.textContent = 'COPY PATH';
  copy.onclick = async () => { await navigator.clipboard.writeText(candidate.path); setNotice(`Скопирован путь: ${candidate.path}`); }; actions.append(copy);
  details.append(actions); card.append(top, area, details); cards.append(card);
  if (decisions[candidate.path]) card.classList.add(decisions[candidate.path].toLowerCase());
  initPreview(area, overlay, candidate);
}

function initPreview(area, overlay, candidate) {
  const stamp = generation;
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setSize(area.clientWidth, area.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  area.prepend(renderer.domElement);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x17202a);
  scene.add(new THREE.HemisphereLight(0xd8e7ff, 0x526070, 2));
  const light = new THREE.DirectionalLight(0xffffff, 2); light.position.set(3, 5, 4); scene.add(light);
  const grid = new THREE.GridHelper(5, 10, 0x647080, 0x33404d); scene.add(grid);
  const camera = new THREE.PerspectiveCamera(42, area.clientWidth / area.clientHeight, .01, 1000);
  camera.position.set(3, 2.7, 4.3); camera.lookAt(0, 1.15, 0);
  const preview = { scene, camera, renderer, area, overlay, mixer: null, action: null, duration: 1, time: 0 };
  const observer = new ResizeObserver(() => { const w = area.clientWidth, h = area.clientHeight;
    if (w && h) { renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }
  }); observer.observe(area); preview.observer = observer; previews.push(preview);
  new FBXLoader().load('/asset/' + encodeURIComponent(candidate.path), fbx => {
    if (stamp !== generation) { disposeObject(fbx); return; }
    const clips = fbx.animations || [];
    let meshCount = 0, boneCount = 0;
    fbx.traverse(node => { if (node.isMesh) meshCount++; if (node.isBone) boneCount++; });
    if (!meshCount && !boneCount) { overlay.textContent = 'ANIMATION-ONLY FBX · External skeleton required'; disposeObject(fbx); return; }
    fbx.updateMatrixWorld(true);
    const box = new THREE.Box3();
    if (meshCount) box.setFromObject(fbx);
    else fbx.traverse(node => { if (node.isBone) box.expandByPoint(node.getWorldPosition(new THREE.Vector3())); });
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 1);
    fbx.scale.multiplyScalar(2.4 / maxDim);
    fbx.updateMatrixWorld(true);
    const fitted = new THREE.Box3();
    if (meshCount) fitted.setFromObject(fbx);
    else fbx.traverse(node => { if (node.isBone) fitted.expandByPoint(node.getWorldPosition(new THREE.Vector3())); });
    const center = fitted.getCenter(new THREE.Vector3());
    fbx.position.x -= center.x; fbx.position.z -= center.z; fbx.position.y -= fitted.min.y;
    scene.add(fbx);
    if (!meshCount && boneCount) { const helper = new THREE.SkeletonHelper(fbx); helper.material.color.set(0xe0ae6c); scene.add(helper); }
    if (clips.length) {
      preview.mixer = new THREE.AnimationMixer(fbx); preview.action = preview.mixer.clipAction(clips[0]);
      preview.action.setLoop(document.querySelector('#loop').checked ? THREE.LoopRepeat : THREE.LoopOnce);
      preview.action.clampWhenFinished = true; preview.action.play(); preview.duration = Math.max(clips[0].duration, .01);
    }
    overlay.textContent = `${meshCount ? 'Модель' : 'Скелет'} · ${boneCount} костей · ${clips.length} клип · ${clips.length ? clips[0].duration.toFixed(2) + ' c' : 'нет клипа'}`;
    if (!clips.length) overlay.textContent += ' · External animation required';
  }, undefined, error => { if (stamp === generation) { overlay.textContent = `Ошибка FBX: ${error.message}`; console.error(candidate.path, error); } });
}

function frame(now) {
  const delta = Math.min((now - previousTime) / 1000, .1); previousTime = now;
  const speed = Number(document.querySelector('#speed').value);
  if (playing) phase += delta * speed;
  const sync = document.querySelector('#sync').checked, loop = document.querySelector('#loop').checked;
  for (const preview of previews) {
    if (preview.mixer && preview.action) {
      preview.action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce);
      if (sync) preview.mixer.setTime(loop ? phase % preview.duration : Math.min(phase, preview.duration));
      else if (playing) preview.mixer.update(delta * speed);
    }
    preview.renderer.render(preview.scene, preview.camera);
  }
  requestAnimationFrame(frame);
}

document.querySelector('#play').onclick = () => { playing = true; };
document.querySelector('#pause').onclick = () => { playing = false; };
document.querySelector('#restart').onclick = () => { phase = 0; for (const preview of previews) preview.mixer?.setTime(0); playing = true; };
document.querySelector('#export').onclick = async () => {
  const response = await fetch('/api/selection', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decisions }) });
  setNotice(response.ok ? 'Сохранено: tools/animation_audit/selection.json и SELECTION.md' : `Ошибка экспорта: ${response.status}`);
};
stateSelect.onchange = () => openGroup(stateSelect.value);
try {
  const response = await fetch('/shortlist.json'); if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
  const initial = Object.entries(data).flatMap(([family, states]) => Object.keys(states).map(state => keyFor(family, state)));
  openGroup(initial.find(key => data[key.split('/')[0]][key.split('/')[1]].candidates.length) || initial[0]);
  requestAnimationFrame(frame);
} catch (error) { setNotice(`Не удалось открыть shortlist: ${error.message}`); console.error(error); }
