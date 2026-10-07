"""Хрущёвки двора (зона 1, объект 5): панельная 1-464 и кирпичная 1-447, bpy → GLB.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_khrushchevka.py

Референсы — референсы/zone05/ (Wikimedia Commons: Томск, Казань, подъезд с козырьком-плитой):
панели с каменной крошкой и светлыми швами-мастикой, окна в откосах с отливами и форточкой,
разномастные балконы (решётка, профлист, деревянное остекление), подъезды со стороны двора:
козырёк-плита на кронштейнах, крыльцо со ступенями и перилами, газовая труба по фасаду.
Кирпичная — силикатный кирпич, красный цоколь, бетонные перемычки, скатная крыша из шифера,
наружные водостоки. Состояние: район брошен два года назад — часть стёкол выбита, окна первого
этажа заколочены, двери подъездов открыты.

Оси — как в Godot (X вдоль дома, Y вверх, Z поперёк; +Z — сторона двора с подъездами),
UV — в метрах (материалы Godot масштабируют сами). Материал = имя слота; в Godot слоты
подменяет tools/author_zone01_yard.gd (assets/zone01/materials/<слот>.tres).
Пишет assets/zone01/models/khrushchevka_<вариант>.glb и assets/zone01/models/khrushchevka.json
(размеры, точки подъездов, коллизии).
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/zone01/models"
OUT.mkdir(parents=True, exist_ok=True)

# цвета слотов — только для превью в Blender; в игре — PBR-материалы Godot
SLOT_COLORS = {
    "PanelConcrete": (.62, .6, .56), "Mastic": (.7, .68, .62), "Plinth": (.5, .49, .46),
    "Brick": (.72, .7, .66), "BrickRed": (.45, .22, .16), "Lintel": (.68, .67, .63),
    "Roofing": (.15, .15, .15), "Slate": (.55, .56, .54), "Galv": (.55, .57, .57), "RustMetal": (.4, .25, .16),
    "Glass": (.1, .12, .13), "Interior": (.06, .055, .05), "Curtain1": (.7, .66, .55), "Curtain2": (.45, .2, .18),
    "Curtain3": (.6, .62, .68), "FrameWhite": (.78, .76, .7), "FrameTeal": (.1, .45, .45), "FrameBrown": (.35, .22, .14),
    "FramePVC": (.9, .9, .88), "Plywood": (.6, .5, .35), "WoodPlanks": (.45, .4, .33), "CorrGreen": (.35, .5, .3),
    "CorrYellow": (.75, .62, .3), "CorrBlue": (.3, .45, .6), "CorrGrey": (.6, .6, .6), "DoorMetal": (.35, .38, .4),
    "Railing": (.15, .45, .45), "GasPipe": (.8, .65, .15), "Concrete": (.55, .55, .52), "Void": (.02, .02, .02),
    "Paint": (.55, .55, .5), "Bars": (.15, .15, .15),
}


# ------------------------------------------------------------------ накопитель геометрии

class Builder:
    """Геометрия одного здания по слотам материалов: вершины, грани, UV в метрах."""

    def __init__(self) -> None:
        self.data: dict[str, tuple[list, list, list]] = {}
        self.collisions: list[dict] = []

    def _slot(self, mat: str):
        if mat not in self.data:
            self.data[mat] = ([], [], [])
        return self.data[mat]

    def add_bmesh(self, mat: str, bm: bmesh.types.BMesh, matrix: Matrix) -> None:
        verts, faces, uvs = self._slot(mat)
        base = len(verts)
        bm.verts.ensure_lookup_table()
        world = [matrix @ v.co for v in bm.verts]
        verts.extend(world)
        rot = matrix.to_3x3()
        for f in bm.faces:
            faces.append([base + v.index for v in f.verts])
            n = (rot @ f.normal).normalized()
            ax = max(range(3), key=lambda i: abs(n[i]))
            loop_uv = []
            for v in f.verts:
                p = world[v.index]
                if ax == 0:
                    u, w = (-p.z if n.x > 0 else p.z), p.y
                elif ax == 2:
                    u, w = (p.x if n.z > 0 else -p.x), p.y
                else:
                    u, w = p.x, p.z
                loop_uv.append((u, w))
            uvs.append(loop_uv)

    def box(self, mat: str, center, size, yaw: float = 0.0, bevel: float = 0.0, pitch: float = 0.0) -> None:
        sx, sy, sz = size
        if sx <= 0.001 or sy <= 0.001 or sz <= 0.001:
            return
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((sx, sy, sz)), verts=bm.verts)
        b = min(bevel, sx * 0.3, sy * 0.3, sz * 0.3)
        if b > 0.002:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=1, affect="EDGES", profile=0.5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        m = Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(yaw), 4, "Y") @ Matrix.Rotation(math.radians(pitch), 4, "X")
        self.add_bmesh(mat, bm, m)
        bm.free()

    def cyl(self, mat: str, a, b, r: float, verts: int = 8, caps: bool = True) -> None:
        a, b = Vector(a), Vector(b)
        d = b - a
        length = d.length
        if length < 0.001:
            return
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, segments=verts, radius1=r, radius2=r, depth=length)
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        m = Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4()
        self.add_bmesh(mat, bm, m)
        bm.free()

    def quad(self, mat: str, corners) -> None:
        bm = bmesh.new()
        vs = [bm.verts.new(Vector(c)) for c in corners]
        bm.faces.new(vs)
        bm.normal_update()
        self.add_bmesh(mat, bm, Matrix.Identity(4))
        bm.free()

    def collide(self, center, size, yaw: float = 0.0) -> None:
        self.collisions.append(dict(pos=[round(v, 3) for v in center], size=[round(v, 3) for v in size], yaw=yaw))

    def to_object(self, name: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name)
        all_v, all_f, all_uv, all_m = [], [], [], []
        mats = sorted(self.data)
        for mi, mat in enumerate(mats):
            verts, faces, uvs = self.data[mat]
            base = len(all_v)
            # Godot (x, y, z) → Blender (x, -z, y); экспорт с +Y вверх вернёт оси обратно
            all_v.extend([(v.x, -v.z, v.y) for v in verts])
            all_f.extend([[base + i for i in f] for f in faces])
            all_uv.extend(uvs)
            all_m.extend([mi] * len(faces))
        mesh.from_pydata(all_v, [], all_f)
        uv_layer = mesh.uv_layers.new(name="UVMap")
        li = 0
        for poly, puv in zip(mesh.polygons, all_uv):
            for k in range(poly.loop_total):
                uv_layer.data[poly.loop_start + k].uv = puv[k]
            li += poly.loop_total
        for mat in mats:
            m = bpy.data.materials.get(mat) or bpy.data.materials.new(mat)
            m.use_nodes = True
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                c = SLOT_COLORS.get(mat, (.5, .5, .5))
                bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
            mesh.materials.append(m)
        for poly, mi in zip(mesh.polygons, all_m):
            poly.material_index = mi
            poly.use_smooth = False
        mesh.validate()
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ------------------------------------------------------------------ окна, двери, балконы

FRAMES = ["FrameWhite", "FrameWhite", "FrameWhite", "FrameTeal", "FrameBrown", "FramePVC"]
CURTAINS = ["Curtain1", "Curtain2", "Curtain3"]


def window(b: Builder, rng: random.Random, x: float, y: float, w: float, h: float, face_z: float, out: float,
           depth: float, ground_floor: bool, kind: str = "room", frame: str | None = None) -> None:
    """Окно в проёме: x — центр, y — низ проёма, face_z — плоскость фасада, out — +1/−1 наружу.
    depth — глубина откоса до рамы. Состояние: целое, выбитое, заколоченное, со шторами."""
    frame = frame or rng.choice(FRAMES)
    fz = face_z - out * depth          # плоскость рамы
    t = 0.06                           # сечение рамы
    # подоконный отлив — оцинковка с уклоном наружу
    b.box("Galv", (x, y - 0.02, face_z - out * (depth * 0.5 - 0.04)), (w + 0.08, 0.025, depth + 0.08), pitch=out * 8)
    # тёмная «комната» за стеклом и шторы — объём и жизнь окна без интерьера
    room_z = fz - out * 0.7
    b.box("Interior", (x, y + h * 0.5, room_z), (w + 0.6, h + 0.6, 0.05))
    state = rng.random()
    boarded = ground_floor and state < 0.45 or (not ground_floor and state < 0.04)
    broken = not boarded and state > 0.78
    if boarded:
        b.box("Plywood", (x, y + h * 0.5, face_z + out * 0.012), (w + 0.12, h + 0.1, 0.02), yaw=rng.uniform(-1.5, 1.5))
        for k in range(2):
            b.box("WoodPlanks", (x, y + h * (0.3 + 0.4 * k), face_z + out * 0.035), (w + 0.3, 0.12, 0.03), yaw=0, pitch=0)
        return
    # рама по периметру
    b.box(frame, (x, y + h - t * 0.5, fz), (w, t, 0.07), bevel=0.006)
    b.box(frame, (x, y + t * 0.5, fz), (w, t, 0.07), bevel=0.006)
    b.box(frame, (x - w * 0.5 + t * 0.5, y + h * 0.5, fz), (t, h, 0.07), bevel=0.006)
    b.box(frame, (x + w * 0.5 - t * 0.5, y + h * 0.5, fz), (t, h, 0.07), bevel=0.006)
    panes = []
    if kind == "stair":
        # окно лестницы: две створки, без форточки
        b.box(frame, (x, y + h * 0.5, fz), (t * 0.8, h - t, 0.07), bevel=0.005)
        panes = [(x - w * 0.25, y + h * 0.5, w * 0.5 - t, h - 2 * t), (x + w * 0.25, y + h * 0.5, w * 0.5 - t, h - 2 * t)]
    elif w > 1.3:
        # трёхстворчатое: широкая глухая слева, справа створка и форточка над ней
        split = x - w * 0.5 + w * 0.42
        b.box(frame, (split, y + h * 0.5, fz), (t * 0.9, h - t, 0.075), bevel=0.005)
        mid = split + (x + w * 0.5 - split) * 0.5
        b.box(frame, (mid, y + h * 0.5, fz), (t * 0.8, h - t, 0.075), bevel=0.005)
        trans_y = y + h * 0.68
        b.box(frame, (mid + (x + w * 0.5 - mid) * 0.5, trans_y, fz), ((x + w * 0.5 - mid) - t, t * 0.8, 0.075), bevel=0.005)
        lw = split - (x - w * 0.5) - t
        panes = [(x - w * 0.5 + t * 0.5 + lw * 0.5 + t * 0.25, y + h * 0.5, lw, h - 2 * t),
                 ((split + mid) * 0.5, y + h * 0.5, mid - split - t, h - 2 * t),
                 ((mid + x + w * 0.5) * 0.5, (y + trans_y) * 0.5, x + w * 0.5 - mid - t * 1.5, trans_y - y - t * 1.5),
                 ((mid + x + w * 0.5) * 0.5, (trans_y + y + h) * 0.5, x + w * 0.5 - mid - t * 1.5, y + h - trans_y - t * 1.5)]
    else:
        b.box(frame, (x, y + h * 0.5, fz), (t * 0.9, h - t, 0.075), bevel=0.005)
        b.box(frame, (x + w * 0.25, y + h * 0.7, fz), (w * 0.5 - t, t * 0.8, 0.075), bevel=0.005)
        panes = [(x - w * 0.25, y + h * 0.5, w * 0.5 - t, h - 2 * t), (x + w * 0.25, y + h * 0.35, w * 0.5 - t, h * 0.7 - 2 * t),
                 (x + w * 0.25, y + h * 0.85, w * 0.5 - t, h * 0.3 - 2 * t)]
    for (px, py, pw, ph) in panes:
        if broken and rng.random() < 0.6:
            # выбито: на месте стекла — острый осколок у края
            b.box("Glass", (px - pw * 0.3, py - ph * 0.35, fz + out * 0.005), (pw * 0.3, ph * 0.22, 0.006), yaw=0, pitch=0)
            continue
        b.box("Glass", (px, py, fz + out * 0.003), (pw, ph, 0.006))
    if kind != "stair" and rng.random() < 0.55:
        c = rng.choice(CURTAINS)
        cw = w * rng.uniform(0.35, 0.95)
        b.box(c, (x + rng.uniform(-0.2, 0.2) * w, y + h * 0.5, fz - out * 0.12), (cw, h * 0.95, 0.02))


def wall_with_window(b: Builder, mat: str, x0: float, x1: float, y0: float, y1: float, face_z: float, out: float,
                     thick: float, win: tuple | None, bevel: float) -> None:
    """Панель (или простенок) x0..x1 × y0..y1 с прямоугольным проёмом win=(cx, wy, ww, wh)."""
    zc = face_z - out * thick * 0.5
    if not win:
        b.box(mat, ((x0 + x1) * 0.5, (y0 + y1) * 0.5, zc), (x1 - x0, y1 - y0, thick), bevel=bevel)
        return
    cx, wy, ww, wh = win
    wx0, wx1 = cx - ww * 0.5, cx + ww * 0.5
    b.box(mat, ((x0 + x1) * 0.5, (y0 + wy) * 0.5, zc), (x1 - x0, wy - y0, thick), bevel=bevel)
    b.box(mat, ((x0 + x1) * 0.5, (wy + wh + y1) * 0.5, zc), (x1 - x0, y1 - wy - wh, thick), bevel=bevel)
    b.box(mat, ((x0 + wx0) * 0.5, wy + wh * 0.5, zc), (wx0 - x0, wh, thick), bevel=bevel)
    b.box(mat, ((wx1 + x1) * 0.5, wy + wh * 0.5, zc), (x1 - wx1, wh, thick), bevel=bevel)


def balcony(b: Builder, rng: random.Random, x: float, y: float, w: float, face_z: float, out: float,
            top: bool, style: str | None = None) -> None:
    """Балкон на плите: решётка, обшивка профлистом/доской, иногда остеклён деревянными рамами."""
    depth = 0.95
    zc = face_z + out * depth * 0.5
    b.box("Concrete", (x, y - 0.08, zc), (w, 0.16, depth), bevel=0.02)
    b.collide((x, y - 0.08, zc), (w, 0.16, depth))
    style = style or rng.choice(["bars", "bars", "corr", "corr", "planks", "glazed", "glazed", "glazed"])
    edge = face_z + out * (depth - 0.03)
    clad = rng.choice(["CorrGreen", "CorrYellow", "CorrBlue", "CorrGrey", "Paint"])
    rail_h = 1.0
    # стойки и поручень
    for sx in (x - w * 0.5 + 0.03, x + w * 0.5 - 0.03):
        b.box("Bars", (sx, y + rail_h * 0.5, edge), (0.04, rail_h, 0.04))
        b.box("Bars", (sx, y + rail_h * 0.5, face_z + out * depth * 0.5), (0.04, rail_h, depth - 0.05))
    b.box("Bars", (x, y + rail_h, edge), (w, 0.05, 0.05))
    if style == "bars":
        n = int(w / 0.14)
        for k in range(n):
            bx = x - w * 0.5 + (k + 0.5) * w / n
            b.box("Bars", (bx, y + rail_h * 0.5, edge), (0.018, rail_h - 0.05, 0.018))
        for sx in (x - w * 0.5 + 0.03, x + w * 0.5 - 0.03):
            for k in range(1, 6):
                b.box("Bars", (sx, y + rail_h * 0.5, face_z + out * k * depth / 6), (0.018, rail_h - 0.05, 0.018))
    else:
        mat = clad if style in ("corr", "glazed") else "WoodPlanks"
        b.box(mat, (x, y + rail_h * 0.5, edge + out * 0.02), (w, rail_h, 0.02))
        for sx in (x - w * 0.5 + 0.01, x + w * 0.5 - 0.01):
            b.box(mat, (sx, y + rail_h * 0.5, face_z + out * depth * 0.5), (0.02, rail_h, depth))
    if style == "glazed":
        frame = rng.choice(["FrameBrown", "FrameWhite", "FrameWhite", "FramePVC"])
        gh = 1.45
        gy = y + rail_h
        b.box(frame, (x, gy + 0.03, edge), (w, 0.06, 0.08))
        b.box(frame, (x, gy + gh - 0.03, edge), (w, 0.06, 0.08))
        n = rng.choice([4, 5, 6])
        for k in range(n + 1):
            fx = x - w * 0.5 + k * w / n
            b.box(frame, (fx, gy + gh * 0.5, edge), (0.06, gh, 0.08))
            if k < n:
                if rng.random() > 0.12:
                    b.box("Glass", ((fx + x - w * 0.5 + (k + 1) * w / n) * 0.5, gy + gh * 0.5, edge), (w / n - 0.06, gh - 0.1, 0.006))
        for sx in (x - w * 0.5 + 0.04, x + w * 0.5 - 0.04):
            b.box(frame, (sx, gy + gh * 0.5, face_z + out * depth * 0.5), (0.06, gh, depth - 0.1))
            b.box("Glass", (sx, gy + gh * 0.5, face_z + out * depth * 0.5), (0.006, gh - 0.1, depth - 0.2))
        if top:
            # верхний этаж: козырёк из профлиста над остеклением
            b.box("CorrGrey", (x, gy + gh + 0.05, face_z + out * (depth + 0.05) * 0.5), (w + 0.1, 0.03, depth + 0.15), pitch=-out * 6)


def entrance(b: Builder, rng: random.Random, x: float, face_z: float, out: float, plinth: float, style: str) -> dict:
    """Подъезд: проём, металлическая дверь (часть открыта — тёмный тамбур), крыльцо, козырёк."""
    dw, dh = 1.5, 2.2
    sill = 0.45
    # тамбур за дверью — тёмный объём, чтобы открытая дверь не просвечивала
    b.box("Void", (x, sill + dh * 0.5, face_z - out * 1.2), (dw + 0.2, dh, 0.05))
    b.box("Concrete", (x, sill - 0.05, face_z - out * 0.6), (dw, 0.1, 1.2))
    open_door = rng.random() < 0.6
    leaf = dw * 0.62
    if open_door:
        # створка распахнута наружу на ~100°
        hinge_x = x - dw * 0.5
        b.box("DoorMetal", (hinge_x - 0.05, sill + dh * 0.5 - 0.02, face_z + out * leaf * 0.5), (0.05, dh - 0.04, leaf), bevel=0.008)
    else:
        b.box("DoorMetal", (x - dw * 0.5 + leaf * 0.5, sill + dh * 0.5 - 0.02, face_z - out * 0.08), (leaf, dh - 0.04, 0.05), bevel=0.008)
    b.box("DoorMetal", (x + dw * 0.5 - (dw - leaf) * 0.5, sill + dh * 0.5 - 0.02, face_z - out * 0.08), (dw - leaf, dh - 0.04, 0.05), bevel=0.008)
    b.box("DoorMetal", (x, sill + dh + 0.03, face_z - out * 0.08), (dw + 0.1, 0.06, 0.08))
    # крыльцо: площадка и ступени (по 15 см)
    land_d = 1.6
    b.box("Concrete", (x, sill * 0.5 - 0.15, face_z + out * land_d * 0.5), (dw + 1.4, sill + 0.3, land_d), bevel=0.02)
    steps = int(round(sill / 0.15))
    for k in range(steps):
        sy = sill - (k + 1) * 0.15
        b.box("Concrete", (x, sy * 0.5 + 0.075 - 0.15, face_z + out * (land_d + 0.3 * k + 0.15)), (dw + 0.9, sy + 0.15 + 0.3, 0.3), bevel=0.015)
    b.collide((x, sill * 0.5 - 0.15, face_z + out * land_d * 0.5), (dw + 1.4, sill + 0.3, land_d))
    # перила по краям ступеней
    for side in (-1, 1):
        rx = x + side * (dw + 0.8) * 0.5
        top0 = Vector((rx, sill + 0.95, face_z + out * 0.2))
        top1 = Vector((rx, 0.9, face_z + out * (land_d + 0.3 * steps)))
        b.cyl("Railing", top0, top1, 0.022, 6)
        for t in (0.0, 0.5, 1.0):
            p = top0.lerp(top1, t)
            b.cyl("Railing", (p.x, p.y - 0.95, p.z), p, 0.016, 6)
    if style == "slab":
        cy = sill + dh + 0.55
        b.box("Concrete", (x, cy, face_z + out * 0.75), (dw + 1.2, 0.16, 1.5), bevel=0.025)
        for side in (-1, 1):
            b.box("Concrete", (x + side * (dw * 0.5 + 0.4), cy - 0.25, face_z + out * 0.35), (0.14, 0.35, 0.7))
    else:
        # навес из профлиста на трубах (Казань)
        cy = sill + dh + 0.35
        b.box("CorrGrey", (x, cy, face_z + out * 1.0), (dw + 1.4, 0.03, 2.1), pitch=-out * 10)
        for side in (-1, 1):
            b.cyl("Railing", (x + side * (dw * 0.5 + 0.6), 0.0, face_z + out * 1.9), (x + side * (dw * 0.5 + 0.6), cy, face_z + out * 1.9), 0.04, 8)
    # доска объявлений у двери
    b.box("Paint", (x + dw * 0.5 + 0.45, sill + 1.3, face_z + out * 0.015), (0.5, 0.6, 0.02))
    return dict(x=round(x, 3), z=round(face_z + out * (land_d + 0.3 * steps + 0.3), 3), sill=sill)


# ------------------------------------------------------------------ здания

def build_panel(seed: int) -> tuple[Builder, dict]:
    """1-464: 18 модулей по 3.2 м (57.6 м), глубина 11.6, 5 этажей по 2.8, цоколь 1.1, 4 подъезда."""
    rng = random.Random(seed)
    b = Builder()
    M, N, FH, P, D, FLOORS = 3.2, 18, 2.8, 1.1, 11.6, 5
    L = M * N
    seam = 0.045
    thick = 0.32
    top = P + FLOORS * FH
    stairs = [2, 7, 11, 16]
    # «мастика» за панелями: светлые швы видны в зазорах
    for out in (-1, 1):
        b.box("Mastic", (0, (P + top) * 0.5, out * (D * 0.5 - thick - 0.01)), (L - 0.05, top - P, 0.02))
    for out in (-1, 1):
        b.box("Mastic", (out * (L * 0.5 - thick - 0.01), (P + top) * 0.5, 0), (0.02, top - P, D - 0.1))
    entries = []
    for side in (-1, 1):   # −1 улица (балконы), +1 двор (подъезды)
        face = side * D * 0.5
        for f in range(FLOORS):
            y0 = P + f * FH
            for i in range(N):
                x0 = -L * 0.5 + i * M + seam * 0.5
                x1 = x0 + M - seam
                cx = (x0 + x1) * 0.5
                stair = side > 0 and i in stairs
                is_balc = side < 0 and i % 3 == 1 and f > 0 and rng.random() > 0.1
                if stair:
                    if f == 0:
                        # проём подъезда в нижней панели, окно лестницы над входом — в следующей
                        wall_with_window(b, "PanelConcrete", x0, x1, y0 + seam * 0.5, y0 + FH - seam * 0.5, face, side, thick,
                                         (cx, y0 + 1.25, 1.25, 0.9), 0.012)
                        window(b, rng, cx, y0 + 1.25, 1.25, 0.9, face, side, 0.14, False, "stair")
                    else:
                        wall_with_window(b, "PanelConcrete", x0, x1, y0 + seam * 0.5, y0 + FH - seam * 0.5, face, side, thick,
                                         (cx, y0 + 1.25, 1.25, 0.9), 0.012)
                        window(b, rng, cx, y0 + 1.25, 1.25, 0.9, face, side, 0.14, False, "stair")
                    continue
                if is_balc:
                    # балконная панель: дверь 0.75 + окно
                    win = (cx + 0.2, y0 + 0.0 + 0.02, 1.9, 2.15)
                    wall_with_window(b, "PanelConcrete", x0, x1, y0 + seam * 0.5, y0 + FH - seam * 0.5, face, side, thick, win, 0.012)
                    b.box(rng.choice(FRAMES), (cx + 0.2 - 0.95 + 0.4, y0 + 1.1, face - side * 0.14), (0.75, 2.1, 0.06))
                    window(b, rng, cx + 0.2 + 0.38, y0 + 0.85, 1.12, 1.3, face, side, 0.14, False)
                    balcony(b, rng, cx, y0, M - 0.2, face, side, f == FLOORS - 1)
                    continue
                kitchen = i % 3 == 2
                ww = 1.2 if kitchen else 1.45
                win = (cx + rng.choice([0.0, 0.0, 0.25, -0.25]) * (0 if kitchen else 1), y0 + 0.85, ww, 1.4)
                wall_with_window(b, "PanelConcrete", x0, x1, y0 + seam * 0.5, y0 + FH - seam * 0.5, face, side, thick, win, 0.012)
                window(b, rng, win[0], win[1], win[2], win[3], face, side, 0.14, f == 0)
                if f == 0 and rng.random() < 0.3:
                    # решётка на окне первого этажа
                    for k in range(6):
                        b.box("Bars", (win[0] - ww * 0.5 + (k + 0.5) * ww / 6, win[1] + 0.7, face + side * 0.04), (0.014, 1.4, 0.014))
        # подъезды
        if side > 0:
            for k, i in enumerate(stairs):
                cx = -L * 0.5 + (i + 0.5) * M
                entries.append(entrance(b, rng, cx, face, side, P, "slab" if k % 3 != 2 else "sheet"))
    # торцы: глухие панели 4×5 со швами
    for out in (-1, 1):
        fx = out * L * 0.5
        cols = 4
        pw = D / cols
        for f in range(FLOORS):
            for c in range(cols):
                z0 = -D * 0.5 + c * pw + seam * 0.5
                b.box("PanelConcrete", (fx - out * thick * 0.5, P + f * FH + FH * 0.5, z0 + (pw - seam) * 0.5),
                      (thick, FH - seam, pw - seam), bevel=0.012)
    # цоколь с продухами
    plinth_wall(b, rng, L, D, P, "Plinth")
    # крыша: плита, парапет с оцинкованным колпаком, вентшахты, выходы, антенны
    b.box("Roofing", (0, top + 0.05, 0), (L - 0.3, 0.1, D - 0.3))
    for out in (-1, 1):
        b.box("PanelConcrete", (0, top + 0.22, out * (D * 0.5 - 0.12)), (L, 0.45, 0.24), bevel=0.01)
        b.box("Galv", (0, top + 0.46, out * (D * 0.5 - 0.12)), (L + 0.04, 0.03, 0.34))
        b.box("PanelConcrete", (out * (L * 0.5 - 0.12), top + 0.22, 0), (0.24, 0.45, D), bevel=0.01)
        b.box("Galv", (out * (L * 0.5 - 0.12), top + 0.46, 0), (0.34, 0.03, D + 0.04))
    roof_details(b, rng, L, D, top, stairs, M)
    gas_pipe(b, L, D * 0.5, 1, P + 1.25, [-L * 0.5 + (i + 0.5) * M for i in stairs])
    b.collide((0, top * 0.5, 0), (L, top + 0.5, D))
    info = dict(kind="panel_1_464", length=L, depth=D, height=top + 0.5, plinth=P, floors=FLOORS, floor_height=FH, entrances=entries)
    return b, info


def plinth_wall(b: Builder, rng: random.Random, L: float, D: float, P: float, mat: str) -> None:
    """Цоколь: пояс до первого этажа (ниже земли на 0.6 — под неровный рельеф), продухи подвала."""
    for out in (-1, 1):
        b.box(mat, (0, (P - 0.6) * 0.5, out * (D * 0.5 - 0.15 + 0.03)), (L + 0.06, P + 0.6, 0.3), bevel=0.01)
        b.box(mat, (out * (L * 0.5 - 0.15 + 0.03), (P - 0.6) * 0.5, 0), (0.3, P + 0.6, D + 0.06), bevel=0.01)
        n = int(L / 6.4)
        for k in range(n):
            vx = -L * 0.5 + (k + 0.5) * L / n + 1.1
            vz = out * (D * 0.5 + 0.035)
            b.box("Void", (vx, 0.45, vz - out * 0.02), (0.42, 0.26, 0.02))
            b.box(mat, (vx, 0.3, vz), (0.5, 0.04, 0.06))
            if rng.random() < 0.5:
                for g in range(4):
                    b.box("Bars", (vx - 0.15 + g * 0.1, 0.45, vz), (0.012, 0.26, 0.012))


def roof_details(b: Builder, rng: random.Random, L: float, D: float, top: float, stairs: list, M: float) -> None:
    for i in stairs:
        cx = -L * 0.5 + (i + 0.5) * M
        # выход на кровлю (будка над лестницей) и вентшахты
        b.box("PanelConcrete", (cx, top + 1.0, D * 0.25), (2.4, 2.0, 2.0), bevel=0.02)
        b.box("Roofing", (cx, top + 2.05, D * 0.25), (2.6, 0.1, 2.2))
        b.box("DoorMetal", (cx, top + 0.9, D * 0.25 - 1.02), (0.8, 1.6, 0.05))
        for dx in (-4.5, 4.5):
            b.box("BrickRed", (cx + dx, top + 0.6, -D * 0.15), (0.9, 1.2, 0.55), bevel=0.01)
            b.box("Concrete", (cx + dx, top + 1.25, -D * 0.15), (1.05, 0.08, 0.7))
        if rng.random() < 0.8:
            ax = cx + rng.uniform(-6, 6)
            az = rng.uniform(-3, 3)
            b.cyl("Galv", (ax, top, az), (ax, top + 3.5, az), 0.025, 6)
            for k in range(4):
                y = top + 2.2 + k * 0.35
                b.cyl("Galv", (ax - 0.8 + k * 0.1, y, az), (ax + 0.8 - k * 0.1, y, az), 0.008, 4)
            for k in range(3):
                b.cyl("Galv", (ax, top + 2.0, az), (ax + rng.uniform(-3, 3), top, az + rng.uniform(-3, 3)), 0.004, 3)


def gas_pipe(b: Builder, L: float, face: float, out: int, y: float, risers: list) -> None:
    """Жёлтая газовая труба вдоль дворового фасада на кронштейнах, ввод у каждого подъезда."""
    z = face + out * 0.18
    b.cyl("GasPipe", (-L * 0.5 + 0.4, y, z), (L * 0.5 - 0.4, y, z), 0.04, 8)
    n = int(L / 2.5)
    for k in range(n + 1):
        x = -L * 0.5 + 0.4 + k * (L - 0.8) / n
        b.box("GasPipe", (x, y - 0.06, face + out * 0.09), (0.04, 0.04, 0.18))
    for rx in risers:
        b.cyl("GasPipe", (rx + 2.0, y, z), (rx + 2.0, 0.0, z), 0.035, 8)
        b.box("GasPipe", (rx + 2.0, 0.7, z), (0.12, 0.08, 0.12))


def build_brick(seed: int) -> tuple[Builder, dict]:
    """1-447: силикатный кирпич, 16 осей по 3.4 м (54.4 м), глубина 12, 5 этажей по 2.7, цоколь 0.8 (красный
    кирпич), скатная крыша из шифера с карнизом, наружные водостоки, 4 подъезда с навесами."""
    rng = random.Random(seed)
    b = Builder()
    M, N, FH, P, D, FLOORS = 3.4, 16, 2.7, 0.8, 12.0, 5
    L = M * N
    thick = 0.51
    top = P + FLOORS * FH
    stairs = [1, 6, 9, 14]
    entries = []
    for side in (-1, 1):
        face = side * D * 0.5
        for f in range(FLOORS):
            y0 = P + f * FH
            for i in range(N):
                x0 = -L * 0.5 + i * M
                x1 = x0 + M
                cx = (x0 + x1) * 0.5
                stair = side > 0 and i in stairs
                is_balc = side < 0 and i % 4 in (1, 2) and f > 0 and (i + f) % 2 == 0
                if stair:
                    # окно лестницы — на полэтажа выше (площадка), высокое, в мелкую расстекловку
                    win = (cx, y0 + 1.6, 1.1, 1.5) if f < FLOORS - 1 else (cx, y0 + 1.0, 1.1, 1.1)
                    if f == 0:
                        win = (cx, y0 + 1.75, 1.1, 1.0)
                    wall_with_window(b, "Brick", x0, x1, y0, y0 + FH, face, side, thick, win, 0.0)
                    window(b, rng, *win, face, side, 0.2, False, "stair")
                    b.box("Lintel", (win[0], win[1] + win[3] + 0.1, face - side * 0.1), (win[2] + 0.5, 0.2, 0.22))
                    continue
                ww = 1.5 if i % 2 == 0 else 1.2
                if is_balc:
                    win = (cx, y0 + 0.02, 1.9, 2.15)
                    wall_with_window(b, "Brick", x0, x1, y0, y0 + FH, face, side, thick, win, 0.0)
                    b.box(rng.choice(FRAMES), (cx - 0.55, y0 + 1.1, face - side * 0.2), (0.75, 2.1, 0.06))
                    window(b, rng, cx + 0.38, y0 + 0.85, 1.12, 1.3, face, side, 0.2, False)
                    b.box("Lintel", (cx, y0 + 2.27, face - side * 0.1), (2.4, 0.2, 0.22))
                    balcony(b, rng, cx, y0, M - 0.6, face, side, f == FLOORS - 1,
                            rng.choice(["corr", "corr", "glazed", "glazed", "bars"]))
                    continue
                win = (cx, y0 + 0.85, ww, 1.4)
                wall_with_window(b, "Brick", x0, x1, y0, y0 + FH, face, side, thick, win, 0.0)
                window(b, rng, *win, face, side, 0.2, f == 0)
                # бетонная перемычка над окном и подоконник
                b.box("Lintel", (cx, win[1] + win[3] + 0.1, face - side * 0.1), (ww + 0.5, 0.2, 0.22))
        if side > 0:
            for k, i in enumerate(stairs):
                cx = -L * 0.5 + (i + 0.5) * M
                entries.append(entrance(b, rng, cx, face, side, P, "sheet" if k % 2 == 0 else "slab"))
    for out in (-1, 1):
        b.box("Brick", (out * (L * 0.5 - thick * 0.5), (P + top) * 0.5, 0), (thick, top - P, D))
    # межэтажный поясок не делаем (у 1-447 его нет); цоколь — красный кирпич
    plinth_wall(b, rng, L, D, P, "BrickRed")
    # карниз: два выступающих ряда кирпича
    for out in (-1, 1):
        b.box("Brick", (0, top + 0.12, out * (D * 0.5 + 0.06)), (L + 0.12, 0.24, 0.12))
        b.box("Brick", (0, top + 0.3, out * (D * 0.5 + 0.14)), (L + 0.28, 0.14, 0.12))
    # скатная крыша: шифер по стропилам, свес 0.5 м, конёк по оси
    pitch_deg = 22.0
    over = 0.55
    half = D * 0.5 + over
    rise = half * math.tan(math.radians(pitch_deg))
    eave_y = top + 0.32
    slope_len = half / math.cos(math.radians(pitch_deg))
    for out in (-1, 1):
        b.box("Slate", (0, eave_y + rise * 0.5, out * half * 0.5), (L + 1.0, 0.04, slope_len), pitch=out * pitch_deg)
        # водосток (жёлоб) по краю ската
        b.box("Galv", (0, eave_y - 0.04, out * (half - 0.02)), (L + 1.0, 0.1, 0.14))
    b.box("Galv", (0, eave_y + rise + 0.02, 0), (L + 1.0, 0.06, 0.32))
    # фронтоны — кирпичные треугольники
    for out in (-1, 1):
        fx = out * (L * 0.5 - thick * 0.5)
        steps = 12
        for k in range(steps):
            z0 = -D * 0.5 + k * D / steps
            z1 = z0 + D / steps
            zc = (z0 + z1) * 0.5
            h = (half - over - abs(zc)) * math.tan(math.radians(pitch_deg))
            if h > 0.02:
                b.box("Brick", (fx, eave_y + h * 0.5, zc), (thick, h, D / steps))
        b.box("Void", (fx + out * 0.26, eave_y + rise * 0.45, 0), (0.02, 0.5, 0.9))
    # вентшахты-трубы над крышей
    for i in stairs:
        cx = -L * 0.5 + (i + 0.5) * M
        for dz in (-2.0, 2.4):
            hh = rise * (1 - abs(dz) / half) + 1.2
            b.box("Brick", (cx + 2.2, eave_y + hh * 0.5, dz), (1.0, hh, 0.6))
            b.box("Concrete", (cx + 2.2, eave_y + hh + 0.04, dz), (1.15, 0.08, 0.75))
    # наружные водосточные трубы
    for out in (-1, 1):
        for xk in (-0.49, -0.25, 0.0, 0.25, 0.49):
            x = xk * L + (0.6 if xk < 0 else -0.6)
            z = out * (D * 0.5 + 0.12)
            pipe = "RustMetal" if rng.random() < 0.6 else "Galv"
            b.cyl(pipe, (x, 0.25, z), (x, eave_y - 0.1, z), 0.055, 8)
            b.cyl(pipe, (x, eave_y - 0.1, z), (x, eave_y - 0.05, out * (half - 0.05)), 0.055, 8)
            b.cyl(pipe, (x, 0.25, z), (x, 0.08, z + out * 0.3), 0.06, 8)
            for y in range(2, int(eave_y), 2):
                b.box(pipe, (x, y, z - out * 0.06), (0.03, 0.03, 0.12))
    gas_pipe(b, L, D * 0.5, 1, P + 1.35, [-L * 0.5 + (i + 0.5) * M for i in stairs])
    b.collide((0, top * 0.5, 0), (L, top + 0.5, D))
    b.collide((0, eave_y + rise * 0.5, 0), (L + 1.0, rise, D + 1.0))
    info = dict(kind="brick_1_447", length=L, depth=D, height=eave_y + rise, plinth=P, floors=FLOORS, floor_height=FH, entrances=entries)
    return b, info


# ------------------------------------------------------------------ экспорт

def export(name: str, b: Builder) -> int:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    obj = b.to_object(name)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(OUT / f"{name}.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                              export_animations=False)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print("KHRUSHCHEVKA", name, "tris", tris, "materials", len(obj.data.materials), flush=True)
    return tris


def main() -> None:
    manifest = {}
    for name, fn, seed in [("khrushchevka_panel_a", build_panel, 11), ("khrushchevka_panel_b", build_panel, 29),
                           ("khrushchevka_brick", build_brick, 5)]:
        b, info = fn(seed)
        info["triangles"] = export(name, b)
        info["collisions"] = b.collisions
        info["materials"] = sorted(b.data)
        manifest[name] = info
    (OUT / "khrushchevka.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
