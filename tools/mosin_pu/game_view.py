"""Мосин ПУ: файл просмотра игровой модели (вариант fp, ~20 000 треугольников) для владельца — в библиотеке модели.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_view.py
→ E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models/06_Игровая/fp/Mosin_PU_Game_Retopo_v05.blend
(v05 — ретопология той же сборкой формы и новая развёртка, game_retopo.py / game_uv.py, 2026-11-04;
v04 — упрощение high-poly, форма v08; v03 — прежняя, форма v07)
Берёт сохранённый экспорт (_asset_src/mosin_pu_game/fp/lp/Mosin_Game_export.blend, после game_export.py -- fp) и
возвращает его в оси винтовки (дуло +X, верх +Z), как у остальных файлов библиотеки. Коллекции: игровая модель,
LOD1 (выключена), коллизия (выключена), патрон и гильза; студия и мир — из сборки исходника (как там, для режима
Rendered). Карты встроены. Файл только для просмотра: правки — в скриптах tools/mosin_pu/game_*.py.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '_asset_src/mosin_pu_game/fp/lp/Mosin_Game_export.blend'
INFO = ROOT / 'assets/models/weapons/mosin_pu/mosin_pu.json'
LIB = Path('E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models')
STUDIO = LIB / '00_Сборка/Mosin_9130PU_Assembly_tex20_v03.blend'
OUT = LIB / '06_Игровая/fp/Mosin_PU_Game_Retopo_v05.blend'
log = lambda *a: print('MOSIN_VIEW', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SRC))
S = bpy.context.scene
O = bpy.data.objects
grip = Vector(json.loads(INFO.read_text(encoding='utf-8'))['grip_origin_rifle_mm']) * 0.001
# оси игры (до перевода glTF) → оси винтовки: обратное к MAP экспорта
BACK = Matrix.Translation(grip) @ Matrix.Rotation(math.radians(90), 4, 'Z')
O['Mosin_PU'].matrix_world = BACK @ O['Mosin_PU'].matrix_world
for o in O:
    if o.name.startswith('Col_'):
        o.matrix_world = BACK @ o.matrix_world
# патрон и гильза — под винтовкой, вдоль её оси
O['Round'].matrix_world = Matrix.Translation((0.02, -0.10, -0.20)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
O['SpentCase'].matrix_world = Matrix.Translation((0.02, -0.10, -0.23)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
bpy.context.view_layer.update()


def collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    S.collection.children.link(c)
    return c


def move(o, c) -> None:
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c.objects.link(o)


game = collection('Игровая модель — 20 000 треугольников')
lod = collection('LOD1 — мировая модель, 5 000 треугольников')
col = collection('Коллизия — выпуклые оболочки')
ammo = collection('Патрон и стреляная гильза')
for o in list(O):
    if o.name.startswith('Col_'):
        move(o, col)
    elif o.name.endswith('_LOD1') or o.name == 'Mosin_PU_LOD1':
        move(o, lod)
    elif o.name.startswith(('Round', 'SpentCase')):
        move(o, ammo)
    else:
        move(o, game)
for c in list(S.collection.children):
    if c not in (game, lod, col, ammo) and not c.all_objects:
        bpy.data.collections.remove(c)
vl = bpy.context.view_layer
for c in (lod, col):
    vl.layer_collection.children[c.name].hide_viewport = True
    c.hide_render = True

# студия исходника: свет, мир (HDRI, серый фон), камера «как у образца»
with bpy.data.libraries.load(str(STUDIO), link=False) as (src, dst):
    dst.collections = [n for n in src.collections if n.startswith('Студия')]
    dst.worlds = list(src.worlds)
for c in dst.collections:
    S.collection.children.link(c)
if dst.worlds:
    S.world = dst.worlds[0]
cam = next((o for c in dst.collections for o in c.all_objects if o.type == 'CAMERA'), None)
if cam:
    S.camera = cam
S.render.engine = 'CYCLES'
S.cycles.samples = 128
S.cycles.preview_samples = 64
S.cycles.use_preview_denoising = True
S.view_settings.exposure = -0.2
S.unit_settings.system = 'METRIC'
S.unit_settings.length_unit = 'MILLIMETERS'
tris = sum(len(o.data.polygons) for o in game.all_objects if o.type == 'MESH')
info = json.loads(INFO.read_text(encoding='utf-8'))['triangles']
S['Мосин'] = (f"Игровая модель Мосина ПУ: {info['first_person']} треугольников (винтовка, крепление, прицел), "
              f"LOD1 {info['lod1']}, карты 20 % 4K запечены с high-poly. Источник — tools/mosin_pu/game_*.py (RING).")
bpy.ops.file.pack_all()
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
log('SAVED', OUT, 'game faces', tris)
