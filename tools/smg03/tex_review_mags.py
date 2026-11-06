"""ИЗЛОМ-45: магазины v2 с износом → файл просмотра владельцу в Blender: игровые сетки Mag13 и Mag30
(_asset_src/smg03/game/lp/SMG03_Game_LP_mags_v2.blend) с картами из Painter, рядом (на 30 — левее), студия прямо в
файле (tools/ar15/tex_apply.studio: HDRI только в отражениях, тёмный фон, мягкие источники, Cycles, вьюпорт в Rendered).
Камеры видов — отдельные объекты «Вид • …» (переключать Numpad 0 / Ctrl+Numpad 0). Карты — внешние PNG по относительным
путям. С «shots <папка>» — ещё и снимки видов (самопроверка).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/tex_review_mags.py -- <папка карт> <выход.blend> [shots <папка> [выборки]]
"""
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ar15'))
sys.path.insert(0, str(ROOT / 'tools/smg03'))
import tex_apply  # noqa: E402
import tex_review  # noqa: E402

LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP_mags_v2.blend'
OFFSET30 = Vector((-0.085, 0.0, 0.0))       # магазин на 30 — левее (сзади по оружию), чтобы оба были в кадре
CENTER = Vector((-0.115, 0.0, -0.11))
# имя: (направление от точки взгляда к камере, расстояние, фокусное, точка взгляда)
VIEWS = {
    '01_справа_3-4': ((0.35, -0.90, 0.25), 0.62, 50, CENTER),
    '02_слева_3-4': ((0.35, 0.90, 0.25), 0.62, 50, CENTER),
    '03_сзади_справа': ((-0.75, -0.60, 0.25), 0.62, 50, CENTER),
    '04_на13_верх_крупно': ((0.25, -0.85, 0.55), 0.22, 50, Vector((-0.045, 0.0, -0.035))),
    '05_на13_защёлка': ((0.55, -0.80, 0.05), 0.20, 50, Vector((-0.035, -0.012, -0.065))),
    '06_донышки_снизу': ((0.30, -0.70, -0.65), 0.55, 50, Vector((-0.12, 0.0, -0.17))),
    '07_губки_сверху': ((0.10, -0.35, 1.0), 0.26, 50, Vector((-0.08, 0.0, -0.015))),
    '08_на30_рукав': ((0.65, -0.70, 0.10), 0.36, 50, Vector((-0.115, 0.0, -0.175))),
}


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    folder, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    S = bpy.context.scene
    S.unit_settings.system = 'METRIC'
    S.unit_settings.length_unit = 'MILLIMETERS'
    game = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
    coll = bpy.data.collections.new('ИЗЛОМ-45 — магазины v2 (игровая сетка)')
    S.collection.children.link(coll)
    for o in game:
        at = o['atlas']
        o.data.materials.clear()
        o.data.materials.append(tex_review.material(at, folder))
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o.name = {'Mag13': 'Магазин на 13', 'Mag30': 'Магазин на 30'}.get(at, o.name)
        if at == 'Mag30':
            o.location = o.location + OFFSET30
    tex_apply.CENTER = CENTER
    tex_apply.studio()
    vc = bpy.data.collections.new('Виды (камеры)')
    S.collection.children.link(vc)
    for name, (d, dist, lens, at) in VIEWS.items():
        cd = bpy.data.cameras.new('Вид • ' + name)
        cd.lens = lens
        cd.clip_start = 0.003
        cam = bpy.data.objects.new('Вид • ' + name, cd)
        vc.objects.link(cam)
        cam.location = at + Vector(d).normalized() * dist
        cam.rotation_euler = (at - cam.location).to_track_quat('-Z', 'Y').to_euler()
    S.camera = bpy.data.objects['Вид • 01_справа_3-4']
    S.render.resolution_x, S.render.resolution_y = 1600, 1000
    try:
        bpy.ops.file.make_paths_relative()
    except RuntimeError:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print('TEX_REVIEW_MAGS_SAVED', out)
    if len(a) > 3 and a[2] == 'shots':
        shots_dir = os.path.abspath(a[3])
        S.cycles.samples = int(a[4]) if len(a) > 4 else 48
        os.makedirs(shots_dir, exist_ok=True)
        for name in VIEWS:
            S.camera = bpy.data.objects['Вид • ' + name]
            S.render.filepath = os.path.join(shots_dir, f'mags_{name}.png')
            bpy.ops.render.render(write_still=True)
            print('SHOT', S.render.filepath, flush=True)


if __name__ == '__main__':
    main()
