const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require('electron');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { zip, unzipSync, strToU8, strFromU8 } = require('fflate');
const { RingService } = require('./ring-service.cjs');
const { createAudioProcessor } = require('./audio-process.cjs');

if (process.env.SONORA_USER_DATA) app.setPath('userData', process.env.SONORA_USER_DATA);
app.setName('Sonora Studio');
app.setAppUserModelId('local.sonora.studio');
let mainWindow;
let ringWindow, ringService;
let currentProjectPath = null;
const MAX_BYTES = 1024 * 1024 * 1024;
const ffmpegPath = app.isPackaged
  ? path.join(process.resourcesPath, 'bin', 'ffmpeg.exe')
  : path.join(__dirname, '..', 'vendor', 'ffmpeg.exe');

function fileName(value, fallback = 'Звук') {
  return String(value || fallback).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/g, '').slice(0, 120) || fallback;
}
function bytesOf(value) {
  if (!(value instanceof Uint8Array) && !(value instanceof ArrayBuffer)) throw new Error('Некорректные аудиоданные.');
  const result = value instanceof ArrayBuffer ? Buffer.from(value) : Buffer.from(value.buffer, value.byteOffset, value.byteLength);
  if (result.byteLength > MAX_BYTES) throw new Error('Размер файла превышает 1 ГБ.');
  return result;
}
function archiveAsync(entries) {
  return new Promise((resolve, reject) => zip(entries, { level: 0 }, (error, data) => error ? reject(error) : resolve(data)));
}
async function atomicWrite(destination, data) {
  const temporary = `${destination}.${randomUUID()}.tmp`;
  try {
    await fs.writeFile(temporary, data);
    await fs.rename(temporary, destination);
  } finally { await fs.rm(temporary, { force: true }).catch(() => {}); }
}
async function runFfmpeg(args) {
  await fs.access(ffmpegPath).catch(() => { throw new Error('Не найден встроенный аудиокодек FFmpeg. Переустановите программу из полного архива.'); });
  return new Promise((resolve, reject) => {
    const child = spawn(ffmpegPath, ['-hide_banner', '-loglevel', 'error', '-nostdin', ...args], { windowsHide: true });
    let errorText = '';
    child.stderr.on('data', data => { errorText = (errorText + data.toString()).slice(-5000); });
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolve() : reject(new Error(`Не удалось обработать звук: ${errorText.trim().slice(-800) || `код ${code}`}`)));
  });
}
function handle(channel, handler, scope = 'editor') {
  ipcMain.handle(channel, async (event, ...args) => {
    const allowed = scope === 'ring' ? [ringWindow] : scope === 'both' ? [mainWindow,ringWindow] : [mainWindow];
    if (!allowed.some(window => window && !window.isDestroyed() && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame)) throw new Error('Неизвестный источник запроса.');
    return handler(...args);
  });
}
function registerHandlers() {
  const processAudio=createAudioProcessor(runFfmpeg);
  handle('audio:process',(data,options)=>processAudio(bytesOf(data),options));
  handle('audio:open', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Добавить звуки', properties: ['openFile', 'multiSelections'],
      filters: [{ name: 'Аудио', extensions: ['wav', 'mp3', 'ogg'] }]
    });
    if (result.canceled) return [];
    return Promise.all(result.filePaths.map(async source => {
      const stat = await fs.stat(source);
      if (stat.size > MAX_BYTES) throw new Error(`Файл ${path.basename(source)} превышает 1 ГБ.`);
      return { name: path.basename(source), bytes: new Uint8Array(await fs.readFile(source)) };
    }));
  });
  handle('audio:decode', async (data, extension) => {
    const folder = await fs.mkdtemp(path.join(os.tmpdir(), 'sonora-decode-'));
    try {
      const ext = ['wav', 'mp3', 'ogg'].includes(extension) ? extension : 'audio';
      const input = path.join(folder, `input.${ext}`);
      const output = path.join(folder, 'decoded.wav');
      await fs.writeFile(input, bytesOf(data));
      await runFfmpeg(['-y', '-i', input, '-vn', '-ac', '2', '-ar', '48000', '-c:a', 'pcm_f32le', output]);
      return new Uint8Array(await fs.readFile(output));
    } finally { await fs.rm(folder, { recursive: true, force: true }); }
  }, 'both');
  handle('project:save', async (document, saveAs) => {
    if (!document?.project || ![1, 2, 3].includes(document.project.schemaVersion) || !Array.isArray(document.assets)) throw new Error('Некорректный проект.');
    let destination = currentProjectPath;
    if (!destination || saveAs) {
      const result = await dialog.showSaveDialog(mainWindow, {
        title: 'Сохранить проект', defaultPath: destination || `${fileName(document.project.name, 'Мой проект')}.sonora`,
        filters: [{ name: 'Проект Sonora', extensions: ['sonora'] }]
      });
      if (result.canceled || !result.filePath) return null;
      destination = result.filePath.toLowerCase().endsWith('.sonora') ? result.filePath : `${result.filePath}.sonora`;
    }
    const entries = { 'project.json': strToU8(JSON.stringify(document.project)) };
    for (const asset of document.assets) {
      if (!/^[a-zA-Z0-9_-]{1,80}$/.test(asset.id)) throw new Error('Некорректный идентификатор звука.');
      entries[`audio/${asset.id}`] = new Uint8Array(bytesOf(asset.bytes));
    }
    const archive = await archiveAsync(entries);
    await atomicWrite(destination, archive);
    currentProjectPath = destination;
    return { path: destination, name: path.basename(destination, '.sonora') };
  });
  handle('project:open', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Открыть проект', properties: ['openFile'], filters: [{ name: 'Проект Sonora', extensions: ['sonora'] }]
    });
    if (result.canceled) return null;
    const source = result.filePaths[0];
    if ((await fs.stat(source)).size > MAX_BYTES) throw new Error('Проект превышает 1 ГБ.');
    let entries;
    try { entries = unzipSync(new Uint8Array(await fs.readFile(source))); }
    catch { throw new Error('Не удалось прочитать проект. Возможно, файл повреждён.'); }
    if (!entries['project.json']) throw new Error('В архиве отсутствует описание проекта.');
    const project = JSON.parse(strFromU8(entries['project.json']));
    if (![1, 2, 3].includes(project.schemaVersion) || !Array.isArray(project.assets) || !Array.isArray(project.tracks)) throw new Error('Неподдерживаемая версия проекта.');
    const assets = project.assets.map(asset => {
      const bytes = entries[`audio/${asset.id}`];
      if (!bytes) throw new Error(`В проекте отсутствует звук «${asset.name}».`);
      return { id: asset.id, name: asset.name, bytes };
    });
    // The renderer confirms successful validation/decoding before adopting this path.
    return { path: source, project, assets };
  });
  handle('project:adopt', async source => { currentProjectPath = source || null; return true; });
  handle('preset:open', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Загрузить настройки эквалайзера', properties: ['openFile'],
      filters: [{ name: 'Настройки EQ', extensions: ['json', 'csv', 'txt'] }]
    });
    if (result.canceled) return null;
    if ((await fs.stat(result.filePaths[0])).size > 1024 * 1024) throw new Error('Файл настроек превышает 1 МБ.');
    return { name: path.basename(result.filePaths[0]), text: await fs.readFile(result.filePaths[0], 'utf8') };
  });
  handle('preset:save', async (name, text) => {
    const result = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить настройки эквалайзера', defaultPath: `${fileName(name, 'Эквалайзер')}.json`,
      filters: [{ name: 'Настройки EQ', extensions: ['json'] }]
    });
    if (result.canceled) return false;
    await atomicWrite(result.filePath, String(text));
    return true;
  });
  handle('export:choose', async options => {
    const format = ['wav', 'mp3', 'ogg'].includes(options.format) ? options.format : 'wav';
    if (options.separate) {
      const result = await dialog.showOpenDialog(mainWindow, { title: 'Папка для дорожек', properties: ['openDirectory', 'createDirectory'] });
      if (result.canceled) return null;
      const folder = result.filePaths[0];
      const used=new Set();
      const names = options.names.map((name, index) => {const base=options.exactNames?fileName(name):`${String(index+1).padStart(2,'0')}_${fileName(name)}`;let unique=`${base}.${format}`,counter=2;while(used.has(unique.toLowerCase()))unique=`${base}_${counter++}.${format}`;used.add(unique.toLowerCase());return unique;});
      const existing = (await Promise.all(names.map(async name => fs.access(path.join(folder, name)).then(() => name).catch(() => null)))).filter(Boolean);
      if (existing.length) {
        const answer = await dialog.showMessageBox(mainWindow, {
          type: 'question', buttons: ['Отмена', 'Заменить'], defaultId: 0, cancelId: 0,
          message: `В папке уже есть ${existing.length} файлов с такими именами.`, detail: 'Заменить их результатом экспорта?'
        });
        if (answer.response !== 1) return null;
      }
      exportTargets = names.map(name => path.join(folder, name));
      return { count: names.length };
    }
    const result = await dialog.showSaveDialog(mainWindow, {
      title: 'Экспорт микса', defaultPath: `${fileName(options.name, 'Микс')}.${format}`,
      filters: [{ name: format.toUpperCase(), extensions: [format] }]
    });
    if (result.canceled) return null;
    exportTargets = [result.filePath.toLowerCase().endsWith(`.${format}`) ? result.filePath : `${result.filePath}.${format}`];
    return { count: 1 };
  });
  handle('export:write', async (data, options) => {
    const destination = exportTargets[options.index];
    if (!destination) throw new Error('Сначала выберите место экспорта.');
    const folder = await fs.mkdtemp(path.join(os.tmpdir(), 'sonora-export-'));
    const format = ['wav', 'mp3', 'ogg'].includes(options.format) ? options.format : 'wav';
    const temporaryOutput = path.join(path.dirname(destination), `.${randomUUID()}.${format}`);
    try {
      const input = path.join(folder, 'render.wav');
      await fs.writeFile(input, bytesOf(data));
      const codecs = format === 'mp3' ? ['-c:a', 'libmp3lame', '-b:a', '320k']
        : format === 'ogg' ? ['-c:a', 'libvorbis', '-q:a', '8']
        : ['-c:a', options.bitDepth === '16' ? 'pcm_s16le' : options.bitDepth === '32f' ? 'pcm_f32le' : 'pcm_s24le'];
      await runFfmpeg(['-y', '-i', input, '-vn', '-ar', String([44100, 48000, 96000].includes(options.sampleRate) ? options.sampleRate : 48000), ...codecs, '-metadata', 'encoder=Sonora Studio', temporaryOutput]);
      await fs.rename(temporaryOutput, destination);
      return { path: destination, name: path.basename(destination) };
    } finally {
      await fs.rm(folder, { recursive: true, force: true });
      await fs.rm(temporaryOutput, { force: true }).catch(() => {});
    }
  });
  handle('export:reveal', async () => { if (exportTargets[0]) shell.showItemInFolder(exportTargets[0]); });
  handle('app:title', async title => { mainWindow.setTitle(`${String(title).slice(0, 200)} — Sonora Studio`); });
  handle('ring:open', async () => { await createRingWindow(); return true; });
  handle('ring:send', async items => {
    if (!Array.isArray(items) || !items.length || items.length > 32) throw new Error('Можно передать до 32 вариантов за раз.');
    if(ringService.shelf.length+items.length>100)throw new Error('На полке Ring не хватает места для всего набора. Удалите ненужные варианты.');
    const staged=[];
    for(const item of items) staged.push(await ringService.stage(new Uint8Array(bytesOf(item.bytes)),fileName(String(item.name).replace(/\.(wav|mp3|ogg)$/i,''))+'.wav','editor'));
    await createRingWindow();
    ringWindow.webContents.send('ring:incoming',staged.map(item=>item.id));
    return staged.map(item=>item.id);
  });
  handle('ring:state', refresh => ringService.state(refresh !== false), 'ring');
  handle('ring:locations', () => ringService.locations(), 'ring');
  handle('ring:edit', options => ringService.edit(options), 'ring');
  handle('ring:project', async () => {
    const result=await dialog.showOpenDialog(ringWindow,{title:'Папка проекта Ring с project.godot',defaultPath:ringService.settings.projectPath,properties:['openDirectory']});
    return result.canceled ? null : ringService.setProject(result.filePaths[0]);
  },'ring');
  handle('ring:godot', async () => {
    const result=await dialog.showOpenDialog(ringWindow,{title:'Исполняемый файл Godot для Ring',defaultPath:ringService.settings.godotPath,properties:['openFile'],filters:[{name:'Godot',extensions:['exe']}]});
    return result.canceled ? null : ringService.setGodot(result.filePaths[0]);
  },'ring');
  handle('ring:files', async () => {
    const result=await dialog.showOpenDialog(ringWindow,{title:'Новые варианты звука для Ring',properties:['openFile','multiSelections'],filters:[{name:'Аудио',extensions:['wav','mp3','ogg']}]});
    if(result.canceled)return[];
    if(result.filePaths.length>32)throw new Error('Выберите не больше 32 вариантов.');
    const staged=[];
    for(const source of result.filePaths){if((await fs.stat(source)).size>256*1024*1024)throw new Error('Файл превышает 256 МБ.');staged.push(await ringService.stage(new Uint8Array(await fs.readFile(source)),path.basename(source)));}
    return staged;
  },'ring');
  handle('ring:stage', (bytes,name) => ringService.stage(new Uint8Array(bytesOf(bytes)),name),'ring');
  handle('ring:remove', id => ringService.remove(id),'ring');
  handle('ring:audio', (id,game) => game ? ringService.gameAudio(id) : ringService.candidateAudio(id),'ring');
  handle('ring:approve', options => ringService.approve(options),'ring');
  handle('ring:invalidate', () => ringService.invalidate(),'ring');
  handle('ring:import', id => ringService.importApproved(id),'ring');
  handle('ring:undo', id => ringService.undo(id),'ring');
  handle('ring:reveal', async () => { await shell.openPath(ringService.catalog?.root || ringService.settings.projectPath); },'ring');
  handle('ring:backups', async () => { const folder=path.join(ringService.folder,'backups');await fs.mkdir(folder,{recursive:true});await shell.openPath(folder); },'ring');
}
let exportTargets = [];

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500, height: 960, minWidth: 1060, minHeight: 740, backgroundColor: '#11141b',
    title: 'Sonora Studio', icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    titleBarStyle: 'hidden', titleBarOverlay: { color: '#141820', symbolColor: '#a5adbb', height: 46 },
    show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false }
  });
  Menu.setApplicationMenu(null);
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('will-navigate', event => event.preventDefault());
  mainWindow.webContents.on('will-prevent-unload', event => {
    const choice = dialog.showMessageBoxSync(mainWindow, {
      type: 'question', buttons: ['Вернуться', 'Закрыть без сохранения'], defaultId: 0, cancelId: 0,
      message: 'В проекте есть несохранённые изменения.', detail: 'Вернитесь в программу и сохраните проект, чтобы продолжить работу позже.'
    });
    if (choice === 1) event.preventDefault();
  });
  mainWindow.loadFile(path.join(__dirname, '..', 'ui', 'index.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());
}
async function createRingWindow() {
  if(ringWindow && !ringWindow.isDestroyed()) { ringWindow.show(); ringWindow.focus(); return; }
  ringWindow=new BrowserWindow({width:1480,height:940,minWidth:1100,minHeight:740,backgroundColor:'#11141b',title:'Ring — звуковой стенд',icon:path.join(__dirname,'..','assets','icon.png'),show:false,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,spellcheck:false}});
  ringWindow.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  ringWindow.webContents.on('will-navigate',event=>event.preventDefault());
  ringWindow.on('close',event=>{if(ringService.busy)event.preventDefault();});
  ringWindow.on('closed',()=>{ringWindow=null;});
  await ringWindow.loadFile(path.join(__dirname,'..','ui','ring.html'));ringWindow.show();
}
app.whenReady().then(async () => { ringService=await new RingService(path.join(app.getPath('userData'),'ring'),runFfmpeg).init();registerHandlers(); createWindow(); });
app.on('window-all-closed', () => app.quit());
