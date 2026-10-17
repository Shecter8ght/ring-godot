"""Купе Ильи: сцена чернового объёма — кузов из body_field.py и колёса.

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/blockout_scene.py -- \
        <кузов.ply> <выход.blend>

Колёса одного размера на всех осях (решение для игры: найденное колесо подходит на любое место):
шина 265/35 R20, диск 20", колея CLE 53 — 1661 / 1645 мм. Шина — профиль, провёрнутый вокруг оси.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
BODY = Path(argv[0])
OUT = Path(argv[1])

WHEEL_Y = 1.4355          # половина базы 2,871 (чертёж)
TIRE_R = 0.3467           # 265/35 R20: 0,254 + 0,35·0,265
TIRE_W = 0.265
RIM_R = 0.254 + 0.012     # закраина диска над посадочным
TRACK_F, TRACK_R = 1.661, 1.645
SEGMENTS = 128


def tire_profile() -> list[tuple[float, float]]:
    """(осевая координата, радиус) — от внутренней закраины по боковине, протектору, к наружной."""
    hw = TIRE_W / 2
    pts = []
    # боковина: от посадки до плеча, слегка выпуклая
    side = [(0.254, 0.86), (0.270, 0.96), (0.290, 1.00), (0.310, 0.99), (0.326, 0.95), (0.338, 0.88)]
    for r, k in side:
        pts.append((-hw * k, r))
    # плечо и протектор
    for a in range(0, 91, 15):
        t = math.radians(a)
        pts.append((-hw * 0.80 - 0.018 * math.cos(t), TIRE_R - 0.018 + 0.018 * math.sin(t)))
    pts.append((0.0, TIRE_R))
    mirror = [(-u, r) for u, r in reversed(pts)]
    return pts + mirror


def spin_mesh(name: str, profile: list[tuple[float, float]], closed: bool = False) -> bpy.types.Object:
    bm = bmesh.new()
    verts = [bm.verts.new((u, 0.0, r)) for u, r in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    if closed:
        edges.append(bm.edges.new((verts[-1], verts[0])))
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(1, 0, 0), angle=math.tau,
                   steps=SEGMENTS, use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material(name: str, rgb: tuple[float, float, float], rough: float) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.ply_import(filepath=str(BODY))
body = bpy.context.selected_objects[0]
body.name = "Body_blockout"
for p in body.data.polygons:
    p.use_smooth = True
body.data.materials.append(material("blockout_grey", (0.55, 0.55, 0.55), 0.45))

rubber = material("blockout_rubber", (0.05, 0.05, 0.05), 0.85)
rim_mat = material("blockout_rim", (0.12, 0.12, 0.13), 0.35)

tire = spin_mesh("Tire_proto", tire_profile())
tire.data.materials.append(rubber)
# Диск в черновике — утопленная тарелка с закраиной (спицы — на этапе деталей)
rim_prof = [(-0.105, RIM_R), (-0.105, 0.245), (0.060, 0.245), (0.095, 0.20), (0.100, 0.07),
            (0.105, 0.035), (0.105, 0.0)]
rim = spin_mesh("Rim_proto", rim_prof)
rim.data.materials.append(rim_mat)

col = bpy.data.collections.new("Wheels")
bpy.context.scene.collection.children.link(col)
for name, y, track in (("FL", -WHEEL_Y, TRACK_F), ("FR", -WHEEL_Y, TRACK_F),
                       ("RL", WHEEL_Y, TRACK_R), ("RR", WHEEL_Y, TRACK_R)):
    side = 1.0 if name.endswith("L") else -1.0      # левый борт +X
    root = bpy.data.objects.new(f"Wheel_{name}", None)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = TIRE_R
    root.location = (side * track / 2, y, TIRE_R)
    # Наружная сторона диска смотрит от машины: правым колёсам ось разворачиваем
    root.rotation_euler = (0, 0, 0 if side > 0 else math.pi)
    col.objects.link(root)
    for proto in (tire, rim):
        ob = bpy.data.objects.new(f"{proto.name.split('_')[0]}_{name}", proto.data)
        ob.parent = root
        col.objects.link(ob)

for proto in (tire, rim):
    bpy.data.objects.remove(proto)

OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("сохранено:", OUT)
