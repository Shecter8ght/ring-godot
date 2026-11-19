"""ВЕРАС-54 v14, игровая версия: листы сверки из кадров game_review_tex.py (системный Python, PIL).

python -X utf8 tools/veras54_v14/game/game_review_sheets.py
→ _asset_src/veras54_v14/game/shots_tex/<вид>.jpg — «подробная | игровая» (у общих видов ещё LOD1), швы_<вид>.jpg —
игровая с одной картой нормалей на сером, кроп_<вид>.png — середина кадра 1:1 у подробной и игровой (одна камера,
один масштаб), увеличено ×2 ближайшим соседом.
python -X utf8 tools/veras54_v14/game/game_review_sheets.py report — retopo-report.json рядом с файлом просмотра: атласы
окончательной развёртки (parts.json), адреса (bake/bake.json, доля попаданий — перенос.json), статус.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SHOTS = Path(__file__).resolve().parents[3] / '_asset_src/veras54_v14/game/shots_tex'
RAW = SHOTS / 'raw'
LABEL = {'hp': 'подробная, износ v03 (Painter)', 'lp': 'игровая LOD0, перенос адресами',
         'lod1': 'игровая LOD1', 'nrm': 'игровая: только карта нормалей (швы)'}
CROP = {'08_затылок_сзади_слева_сверху', '09_затылок_правый_угол', '10_планка_сверху', '05_клейма_слева',
        '06_переводчик_АВ_2_ОД', '11_магазин'}
CROP_W, CROP_H, ZOOM = 640, 360, 2
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)


def row(imgs, labels):
    w = sum(i.width for i in imgs) + 8 * (len(imgs) - 1)
    h = max(i.height for i in imgs) + 34
    sh = Image.new('RGB', (w, h), (28, 28, 28))
    x = 0
    dr = ImageDraw.Draw(sh)
    for im, lb in zip(imgs, labels):
        sh.paste(im, (x, 34))
        dr.text((x + 10, 6), lb, fill=(235, 235, 235), font=font)
        x += im.width + 8
    return sh


def main():
    views = sorted({p.name.split('__')[0] for p in RAW.glob('*__hp.png')})
    for v in views:
        tags = [t for t in ('hp', 'lp', 'lod1') if (RAW / f'{v}__{t}.png').exists()]
        ims = [Image.open(RAW / f'{v}__{t}.png').convert('RGB') for t in tags]
        if len(ims) > 2:
            ims = [i.resize((i.width * 2 // 3, i.height * 2 // 3), Image.LANCZOS) for i in ims]
        row(ims, [LABEL[t] for t in tags]).save(SHOTS / f'{v}.jpg', quality=92)
        if (RAW / f'{v}__nrm.png').exists():
            Image.open(RAW / f'{v}__nrm.png').convert('RGB').save(SHOTS / f'швы_{v}.jpg', quality=92)
        if v in CROP:
            cs = []
            for t in ('hp', 'lp'):
                im = Image.open(RAW / f'{v}__{t}.png').convert('RGB')
                x0, y0 = (im.width - CROP_W) // 2, (im.height - CROP_H) // 2
                c = im.crop((x0, y0, x0 + CROP_W, y0 + CROP_H)).resize((CROP_W * ZOOM, CROP_H * ZOOM), Image.NEAREST)
                cs.append(c)
            row(cs, [LABEL['hp'] + ' — 1:1 ×2', LABEL['lp'] + ' — 1:1 ×2']).save(SHOTS / f'кроп_{v}.png')
        print('лист', v, tags)


def report():
    import datetime
    work = SHOTS.parent
    model = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия')
    rp = model / 'Геометрия v14/retopo-report.json'
    r = json.loads(rp.read_text(encoding='utf-8'))
    rec = json.loads((work / 'lp/parts.json').read_text(encoding='utf-8'))
    draft = json.loads((work / 'lp/parts_uv_draft.json').read_text(encoding='utf-8'))
    tr = json.loads((model / 'Карты v14/перенос.json').read_text(encoding='utf-8'))
    bk = json.loads((work / 'bake/bake.json').read_text(encoding='utf-8'))
    atl = {}
    for a, v in rec['atlases'].items():
        d = draft['atlases'][a]
        atl[a] = {'size': v['size'], 'status': 'FINAL',
                  'fill_draft': d['fill'], 'fill': v['fill'], 'px_mm_visible_draft': d['report']['px_mm_visible'],
                  'px_mm_visible': v['report']['px_mm_visible'], 'px_mm_hidden': v['report']['px_mm_hidden'],
                  'islands': v['report']['islands'], 'islands_small': v['report']['islands_small'],
                  'margin_px': v['margin_px'], 'group_margin_px': v['group_margin_px'], 'order': v['order'],
                  'loss_margins': v['loss_margins'], 'loss_empty': v['loss_empty'], 'verify': v['verify'],
                  'lod1': v.get('lod1'), 'address_hit_share': tr['atlases'].get(a, {}).get('hit')}
    r['atlases'] = atl
    r['uv_final'] = rec.get('uv_final')
    r['transfer'] = {'bake': {k: bk[k] for k in ('when', 'source', 'margin_px', 'passes', 'base_props')},
                     'shell_mm': bk.get('shell_mm'), 'maps_from': tr['folders'], 'maps_to': str(model / 'Карты v14'),
                     'when': tr['when'], 'hit_share': {a: v['hit'] for a, v in tr['atlases'].items()},
                     'tools': ['tools/veras54_v14/game/game_uv.py', 'tools/veras54_v14/game/game_bake.py',
                               'tools/veras54_v14/game/game_transfer.py', 'tools/veras54_v14/game/game_review_tex.py',
                               'tools/veras54_v14/game/game_review_sheets.py']}
    hc = work / 'bake/hit_in_islands.json'
    if hc.exists():
        r['transfer']['hit_in_islands'] = json.loads(hc.read_text(encoding='utf-8'))
    r['transfer']['flipped_normal_share'] = {'Body': 0.0038, 'Front': 0.0039, 'Mag': 0.0045,
                                             'note': 'доля текселей с нормалью «назад» после кусков по деталям (было 9 % у Body)'}
    r['status'] = 'UV_FINAL_MAPS_TRANSFERRED'
    r['date'] = datetime.date.today().isoformat()
    r['derived_blend_textured'] = str(model / 'Геометрия v14/ВЕРАС-54_игровая_v14_02.blend')
    r['dependent_steps_to_rerun'] = ['Godot_import_validation (после слова владельца)', 'клипы рук на новой модели']
    r['owner_review'] = 'pending'
    rp.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    print('отчёт →', rp)


if __name__ == '__main__':
    report() if 'report' in sys.argv else main()
