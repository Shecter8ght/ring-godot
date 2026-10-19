"""ВЕРАС-54 v13: матовая отделка корпуса в игровых картах ORM (после game_pack.py, перед export_veras54.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_v13/game_finish.py

Владелец 2026-10-19 (тир убежища, лампы): «для корпуса автомата надо убирать глянец… под светом ламп вообще капец» — как и
10.10 для v11: корпус матовый, блестят затворная группа (рама, затвор, рукоятка — заполированы рукой), трубка приклада
и следы рук. Стек
v13 даёт чёрному фосфату металличность ~0,6 и шероховатость ~0,38 — в тёмной студии Blender не видно, под лампами хром.
Пересчёт всегда из сырых карт (maps/raw: mrh, ao, ecm) — повторный запуск даёт то же самое:
  Steel: покрытие — шероховатость не ниже COAT_ROUGH, металличность × COAT_METAL; вытертая до стали кромка (светлый цвет)
         — мягче (BARE_*); затворная группа (Bolt_Steel) и трубка приклада (грани StockFold_Steel на её цилиндре) — как в стеке;
  Polymer, Magazine: шероховатость не ниже POLY_ROUGH.
Жировые следы (маска _coat) шейдер оружия по-прежнему сглаживает до 0,3 — на матовом корпусе они и дают отблеск под углом.

Текстуры v04 (владелец 2026-10-20: «теперь текстура хорошая»): сталь матовая и почти чёрная уже в самом стеке (шероховатость
~0,86, металличность ~0,70 — у почти чёрного металла отражение темнее, чем у «пластика»), блестят только потёртости. Поэтому
STEEL_FROM_STACK: сталь — как запечено (умножение металличности на COAT_METAL сделало бы её серой); пол шероховатости — только
полимеру и магазину.
→ _asset_src/veras54_game_v13/maps/game/veras54_<Атлас>_100_orm.png (те же имена, что у game_pack.py).
"""
from __future__ import annotations

from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/veras54_game_v13'
RAW = WORK / 'maps/raw'
GAME = WORK / 'maps/game'
COAT_ROUGH = 0.74          # фосфатное покрытие: матовое
COAT_METAL = 0.3           # тёмный конверсионный слой, не полированный металл
BARE_ROUGH = 0.5           # вытертая до стали кромка — чуть глаже
BARE_METAL = 0.85
POLY_ROUGH = 0.66          # полимер цевья, рукоятки, приклада и магазина
GLOSS_PARTS = ('Bolt_Steel', 'StockFold_Steel')
STEEL_FROM_STACK = True    # v04: отделка стали — из стека, без пересчёта
# трубка приклада (выдвижная, Ø25, ось y 0, z −10 мм, x −85…−10 мм) — грани StockFold_Steel на её цилиндре
TUBE = dict(x=(-0.086, -0.009), axis_z=-0.010, r=(0.008, 0.0135))
log = lambda *a: print('VERAS_FINISH', *a, flush=True)


def load(path: Path):
    im = bpy.data.images.load(str(path))
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save(arr: np.ndarray, path: Path) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr
    im = bpy.data.images.new(path.stem, w, h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    log('saved', path.name)


def pushpull(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    c = img * mask[..., None]
    wgt = mask.astype(np.float32)
    levels = []
    while c.shape[0] > 1:
        levels.append((c, wgt))
        h, w = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :w * 2].reshape(h, 2, w, 2, -1).sum(axis=(1, 3))
        wgt = wgt[:h * 2, :w * 2].reshape(h, 2, w, 2).sum(axis=(1, 3))
    fill = c / np.maximum(wgt, 1e-6)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c_l.shape[0], :c_l.shape[1]]
        have = w_l > 1e-6
        fill = np.where(have[..., None], c_l / np.maximum(w_l, 1e-6)[..., None], up)
    return np.where(mask[..., None], img, fill)


def on_tube(ob, t) -> bool:
    c = ob.matrix_world @ t.center
    r = (c.y ** 2 + (c.z - TUBE['axis_z']) ** 2) ** 0.5
    return TUBE['x'][0] <= c.x <= TUBE['x'][1] and TUBE['r'][0] <= r <= TUBE['r'][1]


def uv_mask(objs, n: int) -> np.ndarray:
    """Треугольники GameUV деталей → маска n×n (строка 0 — низ картинки, как пиксели Blender); с полями в 4 пикселя.
    У приклада — только трубка."""
    m = np.zeros((n, n), dtype=bool)
    for ob in objs:
        me = ob.data
        uv = me.uv_layers['GameUV'].data
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            if ob.name.startswith('StockFold') and not on_tube(ob, t):
                continue
            p = np.array([uv[l].uv[:] for l in t.loops]) * n
            x0, y0 = np.maximum(np.floor(p.min(0)).astype(int) - 1, 0)
            x1, y1 = np.minimum(np.ceil(p.max(0)).astype(int) + 1, n - 1)
            d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
            if x1 < x0 or y1 < y0 or abs(d) < 1e-9:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0]) + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / d
            b = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0]) + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / d
            e = -0.6 / max(1.0, abs(d) ** 0.5)
            m[y0:y1 + 1, x0:x1 + 1] |= (a >= e) & (b >= e) & (1 - a - b >= e)
    for _ in range(4):
        m[1:, :] |= m[:-1, :]
        m[:-1, :] |= m[1:, :]
        m[:, 1:] |= m[:, :-1]
        m[:, :-1] |= m[:, 1:]
    return m


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


bpy.context.preferences.use_preferences_save = False
with bpy.data.libraries.load(str(WORK / 'lp/VERAS54_Game_LP.blend'), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in GLOSS_PARTS]
gloss_objs = [o for o in dst.objects if o is not None]

for atlas in ('Steel', 'Polymer', 'Magazine'):
    ecm = load(RAW / f'{atlas}_ecm.png')
    mask = ecm[..., 2] > 0.5
    mrh = load(RAW / f'{atlas}_mrh.png')
    rough = pushpull(mrh[..., 1:2], mask)[..., 0]
    metal = pushpull(mrh[..., 0:1], mask)[..., 0]
    ao_path = RAW / f'{atlas}_ao.png'
    ao = pushpull(load(ao_path)[..., :1], mask)[..., 0] if ao_path.exists() else np.ones_like(rough)
    before = (float(rough[mask].mean()), float(metal[mask].mean()))
    if atlas == 'Steel' and STEEL_FROM_STACK:
        log(atlas, 'отделка из стека (v04), без пересчёта')
    elif atlas == 'Steel':
        albedo = load(GAME / f'veras54_{atlas}_100_albedo.png')[..., :3]     # sRGB-значения файла
        lum = albedo.mean(axis=2)
        bare = smoothstep(0.30, 0.50, lum)                                   # вытертая до стали кромка
        keep = uv_mask(gloss_objs, rough.shape[0])
        rough_m = np.maximum(rough, COAT_ROUGH + (BARE_ROUGH - COAT_ROUGH) * bare)
        metal_m = metal * (COAT_METAL + (BARE_METAL - COAT_METAL) * bare)
        rough = np.where(keep, rough, rough_m)
        metal = np.where(keep, metal, metal_m)
        log(atlas, 'gloss parts share', round(float(keep[mask].mean()), 3))
    else:
        rough = np.maximum(rough, POLY_ROUGH)
    log(atlas, 'rough/metal before', [round(v, 3) for v in before], 'after',
        [round(float(rough[mask].mean()), 3), round(float(metal[mask].mean()), 3)])
    save(np.dstack([ao, rough, metal]), GAME / f'veras54_{atlas}_100_orm.png')
print('VERAS_FINISH_DONE', flush=True)
