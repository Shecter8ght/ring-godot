"""Проверка общего модуля развёртки (tools/asset_kit/uv.py) на копиях готовых игровых сеток: ВЕРАС-54 v13 (сталь,
полимер), Мосин ПУ (сталь, дерево, прицел со стеклом), ПМ «пошарпанный» (сталь, рукоять, магазин, глушитель).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/asset_kit/uv_check.py -- [ствол …] [атлас …] [вариант …]
(ствол: veras, mosin, pm; атлас: Steel, Polymer, Wood, Optic, Grip, Magazine, Suppressor; вариант — из VARIANTS;
без аргументов всё; dump — острова вариантов ещё и в .npz для опытов с tools/asset_kit/uv_pack.py вне Blender.)

Игровой .blend открывается только на чтение: рядом с GameUV у деталей появляются слои вариантов (активный — KitUV),
файл сохраняется копией в <рабочая папка ствола>/uv_kit/<имя>_UVKit.blend; исходник, игровой файл и карты не
меняются, ничего не запекается. Цифры — <рабочая папка>/uv_kit/uv_kit_check.json и строки UVKIT в выводе.

Классы видимости готовой сетки читаются по её развёртке (classes_from_uv: старые скрипты ужимали скрытое × 0,1
и просторное скрытое × 0,5; у Мосина делится его прибавка у глаза). Точки глаза — в осях модели: от бедра камера
в 35 см позади рукояти, на 12 см выше и на 9 см левее (Balance.FPS_HIP_POSE), в прицеле — на линии прицеливания.
"""
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit  # noqa: E402

SRC = ROOT / '_asset_src'


def mosin_prior(c) -> float:
    """Прибавка, которую tools/mosin_pu/game_lp.py (eye_texels) дал острову по x центра: × 1,35 у глаза, × 0,8 вдали."""
    out = max(-0.38 - c[0], c[0] - 0.17, 0.0)
    return 1.35 + (0.8 - 1.35) * min(1.0, out / 0.15)


WEAPONS = {
    'veras': dict(
        file=SRC / 'veras54_game_v13/lp/VERAS54_Game_LP.blend', out=SRC / 'veras54_game_v13/uv_kit', name='VERAS54',
        atlases={'Steel': (('GAME • Steel • 100',), 4096), 'Polymer': (('GAME • Polymer • 100',), 4096)},
        # оси: +X дуло, +Y влево, +Z вверх, начало — ось канала у заднего торца коробки; целик 29 мм, линия 57 мм
        eyes=[kit.Eye((-0.33, 0.09, 0.12), name='бедро'), kit.Eye((-0.22, 0.0, 0.057), kit.ADS_K, 'прицел')]),
    'mosin': dict(
        file=SRC / 'mosin_pu_game/fp/lp/Mosin_Game_LP.blend', out=SRC / 'mosin_pu_game/uv_kit', name='Mosin', prior=mosin_prior,
        atlases={'Steel': (('GAME • Steel • 20',), 4096), 'Wood': (('GAME • Wood • 20',), 4096),
                 'Optic': (('GAME • Optic • 20', 'GAME • Lens • 20'), 4096)},
        # оси как у ВЕРАС; окуляр ПУ на x −187 мм, ось прицела 51 мм над каналом, 8 мм влево; глаз — 7–8 см за окуляром
        eyes=[kit.Eye((-0.48, 0.09, 0.11), name='бедро'), kit.Eye((-0.27, 0.008, 0.0512), kit.ADS_K, 'прицел')]),
    'pm': dict(
        file=SRC / 'pm_worn_game/lp/PM_Worn_LP.blend', out=SRC / 'pm_worn_game/uv_kit', name='PM',
        atlases={'Steel': (('GAME • Steel • 100',), 4096), 'Grip': (('GAME • Grip • 100',), 2048),
                 'Magazine': (('GAME • Magazine • 100',), 2048), 'Suppressor': (('GAME • Suppressor • 100',), 4096)},
        # оси ПМ: дуло −X, +Y вправо, +Z вверх; целик x 60 мм, z 127 мм; пистолет в вытянутых руках — глаз в 55 см
        eyes=[kit.Eye((0.40, -0.09, 0.17), name='бедро', forward=(-1, 0, 0)),
              kit.Eye((0.61, 0.0, 0.127), kit.ADS_K, 'прицел', forward=(-1, 0, 0))]),
}

# варианты: (слой, параметры layout); главный — последним, его метки uv_stack / uv_group остаются в файле.
# RUN — что идёт без явного списка; остальные — по имени в аргументах.
VARIANTS = {
    'KitUV_plain': dict(groups=False, stack=False, eye=False, holes=False),   # своя укладка «тетрисом», отступ 12 везде
    'KitUV_flat': dict(eye=False),                                            # всё, кроме прибавки у глаза
    'KitUV_m8': dict(margin=8),                                               # отступ 8 (норма роликов), в группе 6
    'KitUV_stitch': dict(stitch=True),                                        # группы сшиты блоками вдоль общего ребра
    'KitUV_nogroups': dict(groups=False),                                     # без групп «разрыва»: отступ 12 везде
    'KitUV_pool': dict(hidden_pool=True),                                     # всё скрытое × 0,1 — одной группой
    'KitUV': dict(),                                                          # группы, внахлёст, глаз, пустоты; 12 / 6
}
RUN = ('KitUV_plain', 'KitUV_flat', 'KitUV_m8', 'KitUV_stitch', 'KitUV')
log = lambda *a: print('UVKIT', *a, flush=True)
DUMP = False


def copy_layer(objs, src: str, dst: str) -> None:
    for o in objs:
        me = o.data
        lay = me.uv_layers.get(dst) or me.uv_layers.new(name=dst, do_init=False)
        buf = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[src].uv.foreach_get('vector', buf)
        lay.uv.foreach_set('vector', buf)


def run(key: str, only_atlas: set, only_var: list) -> dict:
    W = WEAPONS[key]
    bpy.ops.wm.open_mainfile(filepath=str(W['file']))
    W['out'].mkdir(parents=True, exist_ok=True)
    res = {}
    for atlas, (mats, size) in W['atlases'].items():
        if only_atlas and atlas not in only_atlas:
            continue
        objs = sorted([o for o in bpy.data.objects if o.type == 'MESH' and o.data.materials and o.data.materials[0]
                       and o.data.materials[0].name in mats], key=lambda o: o.name)
        for o in objs:
            o.data.uv_layers.active = o.data.uv_layers['GameUV']
        t0 = time.time()
        cls = kit.classes_from_uv(objs, 'GameUV', W.get('prior'))
        ef = kit.eye_factors(objs, W['eyes'])
        zones = [np.where(s & (k >= 1.2), 1, np.where(k <= 0.9, -1, 0)).astype(np.int32) for k, s in zip(ef['k'], ef['seen'])]
        base = kit.report(objs, size, uv='GameUV', classes=cls, zones=zones)
        a_cls = np.zeros(4)
        for o, c in zip(objs, cls):
            a = np.empty(len(o.data.polygons), np.float32)
            o.data.polygons.foreach_get('area', a)
            a_cls += np.bincount(c, a, 4)
        row = dict(size=size, objects=[o.name for o in objs], faces=sum(len(o.data.polygons) for o in objs),
                   class_area_share=dict(zip(('visible', 'roomy', 'hidden', 'contact'), np.round(a_cls / a_cls.sum(), 4).tolist())),
                   eye=dict(g_ref=ef.get('g_ref'), d_ref_m=ef.get('d_ref')), GameUV=base, variants={})
        log(key, atlas, 'GameUV', base, f'{time.time() - t0:.1f}s')
        for tag, opt in VARIANTS.items():
            if tag not in (only_var or RUN):
                continue
            copy_layer(objs, 'GameUV', tag)
            opt = dict(opt)
            eyes = W['eyes'] if opt.pop('eye', True) else ()
            if DUMP:
                opt['dump'] = str(W['out'] / f'islands_{atlas}_{tag}.npz')
            lay = kit.layout(objs, size, uv=tag, classes=cls, eyes=eyes, log=lambda *a: log(key, atlas, tag, *a), **opt)
            rep = kit.report(objs, size, uv=tag, classes=cls, zones=zones)
            ver = kit.verify(objs, size, uv=tag, margin=lay['margin_px'], group_margin=lay['group_margin_px'], classes=cls)
            row['variants'][tag] = dict(layout=lay, report=rep, verify=ver)
            log(key, atlas, tag, 'report', rep)
            log(key, atlas, tag, 'verify', ver)
        for o in objs:
            if 'KitUV' in o.data.uv_layers:
                o.data.uv_layers.active = o.data.uv_layers['KitUV']
            o.data.uv_layers['GameUV'].active_render = True
        res[atlas] = row
    out = W['out'] / f"{W['name']}_UVKit.blend"
    bpy.context.preferences.filepaths.save_version = 0       # без .blend1 рядом
    bpy.ops.wm.save_as_mainfile(filepath=str(out), copy=True)
    log('SAVED', out)
    js = W['out'] / 'uv_kit_check.json'
    prev = json.loads(js.read_text(encoding='utf-8')) if js.exists() else {}
    for atlas, row in res.items():
        old = prev.get(atlas, {})
        if only_var and 'variants' in old:
            old['variants'].update(row['variants'])
            row['variants'] = old['variants']
        prev[atlas] = row
    js.write_text(json.dumps(prev, ensure_ascii=False, indent=1, default=lambda v: v.item() if hasattr(v, 'item') else str(v)), encoding='utf-8', newline='\n')
    return res


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = [a for a in args if a in WEAPONS] or list(WEAPONS)
    atl = {a for a in args if any(a in w['atlases'] for w in WEAPONS.values())}
    var = [a for a in args if a in VARIANTS]
    DUMP = 'dump' in args            # острова каждого варианта — в .npz рядом (опыты с укладчиком вне Blender)
    for k in keys:
        run(k, atl, var)
