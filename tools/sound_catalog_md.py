from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'data/audio_events.json').read_text(encoding='utf-8-sig'))
weapons=json.loads((root/'data/weapons.json').read_text(encoding='utf-8-sig'))['weapons']
lines=['# Каталог назначений Ring', '', 'Управление — через Sonora 1.3. Источник истины: `data/audio_events.json`.', '', '| Модель | Назначено действий |', '|---|---|']
for wid,item in weapons.items():
 count=sum(bool(e['files']) for e in data['events'] if e.get('weapon')==wid)
 lines.append('| '+item['name']+' | '+str(count)+' |')
lines+=['', '## Другие назначенные события', '']
for e in data['events']:
 if not e.get('weapon') and e['files']:lines.append('- '+e['name']+': '+str(len(e['files']))+' записей.')
(root/'docs/sound_catalog.md').write_text(chr(10).join(lines)+chr(10),encoding='utf-8')

