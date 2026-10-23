"""Сверка запечённого с high-poly в одной студии: игровая сетка на картах игры рядом с принятой сборкой.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/compare.py [-- размер]
Студия, камера и мир — из принятого файла 01_ПМ (как смотрит владелец); сборка — как есть (глушитель надет), игровая сетка —
lp/PM_Worn_LP.blend с материалами на картах assets/models/weapons/pm/pm_<Атлас>_100_* (плёнка — Coat по маске _coat).
→ _asset_src/pm_worn_game/images/compare_{highpoly,game}.png и docs/screens/pm_worn_compare.png (рядом: слева high-poly,
справа игра), то же без глушителя (хвостовик ствола): compare_bare_*.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SIZE = int(args[0]) if args else 1000
IMAGES = C.WORK / 'images'
IMAGES.mkdir(parents=True, exist_ok=True)
DOCS = C.ROOT / 'docs/screens'
log = lambda *a: C.log('PM_COMPARE', *a)  # noqa: E731


def game_material(name: str, atlas: str):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind: str, cs: str):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(C.ASSET / f'pm_{atlas}_100_{kind}.png'), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    nt.links.new(tex('albedo', 'sRGB').outputs['Color'], p.inputs['Base Color'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tex('orm', 'Non-Color').outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.uv_map = 'GameUV'
    nt.links.new(tex('normal', 'Non-Color').outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    # плёнка — как в игре: шейдер следов опускает шероховатость по маске; здесь — лак по маске
    coat = tex('coat', 'Non-Color')
    nt.links.new(coat.outputs['Color'], p.inputs['Coat Weight'])
    p.inputs['Coat Roughness'].default_value = 0.1
    p.inputs['Coat IOR'].default_value = 1.47
    return m


def render(path: Path) -> None:
    S = bpy.context.scene
    S.render.resolution_x = S.render.resolution_y = SIZE
    S.render.resolution_percentage = 100
    S.render.image_settings.file_format = 'PNG'
    S.render.image_settings.color_mode = 'RGB'
    S.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log('rendered', path.name)


def side_by_side(left: Path, right: Path, out: Path) -> None:
    a = bpy.data.images.load(str(left))
    b = bpy.data.images.load(str(right))
    w, h = a.size
    pa = np.empty(w * h * 4, np.float32)
    pb = np.empty(w * h * 4, np.float32)
    a.pixels.foreach_get(pa)
    b.pixels.foreach_get(pb)
    pa = pa.reshape(h, w, 4)
    pb = pb.reshape(h, w, 4)
    im = bpy.data.images.new(out.stem, w * 2, h, alpha=False)
    im.pixels.foreach_set(np.concatenate([pa, pb], axis=1).ravel())
    im.filepath_raw = str(out)
    im.file_format = 'PNG'
    im.save()
    log('saved', out)


bpy.context.preferences.use_preferences_save = False
C.enable_ucupaint()
bpy.ops.wm.open_mainfile(filepath=str(C.SRC_PM))
S = bpy.context.scene
S.frame_set(1)
C.rest_pose()
C.gpu_cycles(S, 96)
S.cycles.use_denoising = True
for o in bpy.data.objects:
    if o.name.startswith(('Mount |', 'Reflex |', 'Animation |', 'Engraving |', 'Check |')):
        o.hide_render = True
render(IMAGES / 'compare_highpoly.png')
rig = bpy.data.objects.get(C.CONTROLS)
if rig is not None and 'Suppressor' in rig.keys():
    rig['Suppressor'] = 1.0
    rig.update_tag()
    bpy.context.view_layer.update()
    render(IMAGES / 'compare_bare_highpoly.png')
    rig['Suppressor'] = 0.0
    rig.update_tag()
# Игровая сетка в той же студии: вся сборка прячется, остаются студия и камера.
for o in bpy.data.objects:
    if o.type == 'MESH' and not o.name.startswith('Studio |') and not any(c.name.startswith('11 |') or c.name.startswith('05 •') for c in o.users_collection):
        o.hide_render = True
with bpy.data.libraries.load(str(C.LP_FILE), link=False) as (src, dst):
    dst.objects = list(src.objects)
coll = bpy.data.collections.new('GAME')
S.collection.children.link(coll)
lp_objs = [o for o in dst.objects if o is not None]
for o in lp_objs:
    coll.objects.link(o)
    if o.get('bake_only') or o.name in ('RoundChamber', 'JamCase'):
        o.hide_render = True
bpy.context.view_layer.update()
for atlas, name in C.MATNAME.items():
    mat = game_material(name, atlas)
    for o in lp_objs:
        if o.type == 'MESH' and o.data.materials and o.data.materials[0] and o.data.materials[0].name == name:
            o.data.materials[0] = mat
render(IMAGES / 'compare_game.png')
supp = bpy.data.objects.get('Suppressor_Mesh')
if supp is not None:
    supp.hide_render = True
    render(IMAGES / 'compare_bare_game.png')
    supp.hide_render = False
side_by_side(IMAGES / 'compare_highpoly.png', IMAGES / 'compare_game.png', DOCS / 'pm_worn_compare.png')
if (IMAGES / 'compare_bare_highpoly.png').exists():
    side_by_side(IMAGES / 'compare_bare_highpoly.png', IMAGES / 'compare_bare_game.png', DOCS / 'pm_worn_compare_bare.png')
print('PM_COMPARE_DONE', flush=True)
