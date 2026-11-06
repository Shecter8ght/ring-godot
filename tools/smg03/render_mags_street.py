"""ИЗЛОМ-45: магазины v2 с износом на улице — как они отражают солнце (владелец 06.11: «покажи с косым светом на улице,
как они отражают его»; «при высоком солнце тоже надо, и пусть магазины целиком будут в центре кадра»).

Магазины — игровые сетки (SMG03_Game_LP_mags_v2.blend) с картами из Painter; лежат на правом борту друг за другом
вдоль кадра на дощатой крышке ящика во дворе (асфальт и доски — фото Poly Haven, CC0, assets/textures; небо — панорама
Poly Haven, CC0, assets/sky; солнце — лампой, как в render_street.py). Камера в каждом кадре сама подбирает расстояние:
оба магазина целиком, по центру кадра. Солнце низкое (косой свет) и высокое; «против солнца» — камера по ту сторону
от него, блик с верхних граней идёт в объектив.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/render_mags_street.py -- <карты> <папка> [кадр,кадр] [ширина высота выборки] [сцена.blend]
кадры: 1_низкое_против_солнца, 2_низкое_сбоку, 3_высокое_блик, 4_высокое_сбоку
"""
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/smg03'))
sys.path.insert(0, str(ROOT / 'tools/ar15'))
import render_street as RS  # noqa: E402
import tex_review  # noqa: E402

LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP_mags_v2.blend'
A = math.radians(21.2)
C = Vector((-0.0555, 0.0, -0.110))          # середина горловины — начало осей магазина (part_magazine)
TOP = 0.30                                  # высота крышки ящика, м
FILL = 0.46                                 # магазины занимают по ширине кадра до 2 × FILL (от середины)
# кадр: (азимут солнца °, высота солнца °, азимут камеры °, высота камеры над горизонтом °, фокусное, диафрагма)
# камера смотрит с −Y (перёд магазинов с рифлением — к ней); солнце с +Y — за магазинами
SHOTS = {
    '1_низкое_против_солнца': (100.0, 8.0, -80.0, 18.0, 70.0, 11.0),
    '2_низкое_сбоку': (185.0, 6.0, -60.0, 24.0, 70.0, 11.0),
    '3_высокое_блик': (110.0, 62.0, -70.0, 50.0, 70.0, 11.0),
    '4_высокое_сбоку': (215.0, 64.0, -100.0, 28.0, 70.0, 11.0),
}


def lowest(o, x_lo, x_hi):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return min((p for p in pts if x_lo <= p.x <= x_hi), key=lambda p: p.z)


def settle(o):
    """Положить на крышку: самая низкая точка каждого конца — на высоту TOP (наклон вдоль оси, чтобы конец не висел)."""
    xs = [(o.matrix_world @ v.co).x for v in o.data.vertices]
    x0, x1 = min(xs), max(xs)
    lo_a, lo_b = lowest(o, x0, x0 + 0.02), lowest(o, x1 - 0.02, x1)
    ang = math.atan2(lo_b.z - lo_a.z, lo_b.x - lo_a.x)
    o.matrix_world = (Matrix.Translation(lo_a) @ Matrix.Rotation(ang, 4, 'Y') @ Matrix.Translation(-lo_a)) @ o.matrix_world
    bpy.context.view_layer.update()
    zmin = min((o.matrix_world @ v.co).z for v in o.data.vertices)
    o.matrix_world = Matrix.Translation((0, 0, TOP - zmin)) @ o.matrix_world
    bpy.context.view_layer.update()


def place(objs):
    """Оба магазина — на правом борту (вверх правый борт, самый вытертый), ось вдоль X, губки к +X, перёд к камере;
    друг за другом вдоль кадра: на 13 слева, на 30 справа, между ними 3 см."""
    to_axis = Matrix.Rotation(-A, 4, 'Y') @ Matrix.Translation(-C)
    lay = Matrix.Rotation(math.radians(-90.0), 4, 'Z') @ Matrix.Rotation(math.radians(-90.0), 4, 'X')
    x = None
    for at in ('Mag13', 'Mag30'):
        o = objs[at]
        o.matrix_world = lay @ to_axis
        bpy.context.view_layer.update()
        settle(o)
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
        y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
        start = -0.215 if x is None else x + 0.03
        o.matrix_world = Matrix.Translation((start - x0, -(y0 + y1) / 2, 0.0)) @ o.matrix_world
        bpy.context.view_layer.update()
        x = start + (x1 - x0)


def bbox(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def fit(cam, lo, hi, az, el):
    """Камера на направлении (азимут, высота) от середины габарита; расстояние — чтобы габарит занял до FILL от середины
    кадра по любой оси, середина габарита — в середине кадра."""
    S = bpy.context.scene
    ctr = (lo + hi) / 2
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    d = Vector((math.cos(math.radians(el)) * math.cos(math.radians(az)),
                math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))))
    dist = 1.0
    for _ in range(8):
        cam.location = ctr + d * dist
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        m = max(max(abs(q.x - 0.5), abs(q.y - 0.5)) for q in (world_to_camera_view(S, cam, c) for c in corners))
        dist *= m / FILL
    cam.data.dof.focus_distance = dist
    return dist


def crate(coll):
    """Ящик с дощатой крышкой 0.8 × 0.5 м и асфальт вокруг."""
    me = bpy.data.meshes.new('ящик')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.8, 0.5, TOP), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0.0, 0.08, TOP / 2), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.004, segments=2, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(RS.mat_photo('доски крышки', 'wood_planks_grey', 0.9, box=True, value=0.9, bump=1.0))
    o = bpy.data.objects.new('ящик', me)
    coll.objects.link(o)
    RS.ground(coll)


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    maps, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    only = a[2].split(',') if len(a) > 2 and a[2] not in ('', 'all') else None
    w, h, samples = (int(a[3]), int(a[4]), int(a[5])) if len(a) > 5 else (2048, 1152, 160)
    save = a[6] if len(a) > 6 else None
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    S = bpy.context.scene
    objs = {}
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]:
        at = o['atlas']
        o.data.materials.clear()
        o.data.materials.append(tex_review.material(at, maps))
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
        objs[at] = o
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' not in o]:
        bpy.data.objects.remove(o)
    place(objs)
    lo, hi = bbox(objs.values())
    RS.log('габарит магазинов', [round(v, 3) for v in lo], [round(v, 3) for v in hi])
    env = bpy.data.collections.new('двор')
    S.collection.children.link(env)
    crate(env)
    RS.render_settings(w, h, samples)
    S.render.use_motion_blur = False
    sun = None
    for name, (saz, sel, caz, cel, lens, fstop) in SHOTS.items():
        if only and name not in only:
            continue
        RS.SUN_AZ, RS.SUN_EL = saz, sel
        if sun is not None:
            bpy.data.objects.remove(sun)
        sun = RS.world_and_sun()
        cam = RS.camera('кадр ' + name, (0.0, -1.0, TOP + 0.3), (0.0, 0.0, TOP), lens, fstop)
        cam.data.clip_start = 0.005
        dist = fit(cam, lo, hi, caz, cel)
        S.camera = cam
        S.render.filepath = os.path.join(out, f'магазины_{name}.png')
        bpy.ops.render.render(write_still=True)
        RS.log('кадр', name, 'расстояние', round(dist, 3), S.render.filepath)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save), compress=True)


if __name__ == '__main__':
    main()
