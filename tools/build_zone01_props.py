"""Реквизит двора хрущёвок (зона 1, объект 5) и деревья района, bpy → GLB.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_zone01_props.py

Готовых моделей под CC0/CC-BY для этого нет (поиск — docs/zone01_assets.md): «ракушка», сушилки,
газонные дуги, советские баки 0.75 м³, козырьки. Сделано по фото-референсам (референсы/zone05/)
в реальных размерах; материал — имя слота (assets/zone01/materials/<слот>.tres), UV в метрах.
Пишет assets/zone01/models/<имя>.glb и assets/zone01/models/props.json (коллизии, размеры).
Деревья (берёза, тополь, клён) — поздняя осень: почти голые, редкие листья гроздьями-карточками.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_khrushchevka as kh  # noqa: E402

Builder = kh.Builder
OUT = kh.OUT
kh.SLOT_COLORS.update({
    "BenchWood": (.45, .32, .2), "PaintGreenMetal": (.25, .4, .3), "GarageMetal": (.4, .3, .22), "GarageBlue": (.3, .4, .5),
    "PlayRed": (.7, .2, .15), "PlayBlue": (.2, .35, .6), "PlayYellow": (.8, .65, .2), "Sand": (.6, .52, .4),
    "BarkBirch": (.85, .84, .8), "BarkDark": (.3, .26, .22), "LeavesBirch": (.75, .6, .2), "LeavesMaple": (.6, .3, .15),
    "LampHead": (.4, .42, .42), "Wire": (.05, .05, .05),
})


def card(b: Builder, mat: str, corners, uvs) -> None:
    """Плоская карточка с заданными UV (листва) — без проекции по осям."""
    verts, faces, face_uvs = b._slot(mat)
    base = len(verts)
    verts.extend([Vector(c) for c in corners])
    faces.append([base, base + 1, base + 2, base + 3])
    face_uvs.append(list(uvs))


# ------------------------------------------------------------------ мелкий реквизит

def bench(back: bool) -> Builder:
    """Лавка у подъезда: бетонные боковины, деревянные брусья 2 м (сидение 3, спинка 2)."""
    b = Builder()
    for x in (-0.8, 0.8):
        b.box("Concrete", (x, 0.22, 0.0), (0.12, 0.44, 0.45), bevel=0.02)
        if back:
            b.box("Concrete", (x, 0.62, 0.2), (0.1, 0.5, 0.08), bevel=0.015)
    for k in range(3):
        b.box("BenchWood", (0, 0.46, -0.16 + k * 0.13), (2.0, 0.045, 0.1), bevel=0.008, yaw=random.uniform(-0.6, 0.6))
    if back:
        for k in range(2):
            b.box("BenchWood", (0, 0.66 + k * 0.17, 0.23), (2.0, 0.1, 0.035), bevel=0.008, pitch=-12)
    b.collide((0, 0.25, 0), (2.0, 0.5, 0.5))
    return b


def dumpster(lid_open: bool) -> Builder:
    """Мусорный контейнер 0.75 м³: трапеция, рёбра жёсткости, 4 колеса, крышки-половинки, ручки."""
    b = Builder()
    w, d, h = 1.25, 0.82, 1.0
    b.box("PaintGreenMetal", (0, 0.2 + h * 0.5, 0), (w, h, d), bevel=0.02)
    for x in (-0.4, 0, 0.4):
        b.box("PaintGreenMetal", (x, 0.2 + h * 0.5, -d * 0.5 - 0.02), (0.05, h * 0.9, 0.04))
        b.box("PaintGreenMetal", (x, 0.2 + h * 0.5, d * 0.5 + 0.02), (0.05, h * 0.9, 0.04))
    b.box("PaintGreenMetal", (0, 0.2 + h - 0.05, 0), (w + 0.08, 0.08, d + 0.08), bevel=0.01)
    for x in (-w * 0.5 + 0.12, w * 0.5 - 0.12):
        for z in (-d * 0.5 + 0.12, d * 0.5 - 0.12):
            b.cyl("Bars", (x - 0.03, 0.09, z), (x + 0.03, 0.09, z), 0.09, 10)
            b.box("Galv", (x, 0.16, z), (0.06, 0.1, 0.06))
    for side in (-1, 1):
        b.cyl("Galv", (side * (w * 0.5 + 0.06), 0.9, -0.25), (side * (w * 0.5 + 0.06), 0.9, 0.25), 0.025, 6)
    if lid_open:
        b.box("PaintGreenMetal", (0, 0.2 + h + 0.3, d * 0.5 + 0.1), (w, 0.6, 0.03), pitch=-75)
    else:
        b.box("PaintGreenMetal", (0, 0.2 + h + 0.03, 0), (w, 0.03, d), pitch=3)
    b.collide((0, 0.2 + h * 0.5, 0), (w, h + 0.2, d))
    return b


def container_site() -> Builder:
    """Контейнерная площадка: бетонная плита 5.5×2.6 и ограждение из профлиста на трубах с трёх сторон."""
    b = Builder()
    w, d, h = 5.5, 2.6, 1.5
    b.box("Concrete", (0, 0.05, 0), (w, 0.2, d), bevel=0.02)
    for (x, z, sw, sd) in [(0, -d * 0.5, w, 0.02), (-w * 0.5, 0, 0.02, d), (w * 0.5, 0, 0.02, d)]:
        b.box("CorrGrey", (x, 0.15 + h * 0.5, z), (sw, h, sd))
    for x in (-w * 0.5, 0, w * 0.5):
        b.cyl("Galv", (x, 0, -d * 0.5 - 0.04), (x, h + 0.2, -d * 0.5 - 0.04), 0.04, 8)
    for z in (0, d * 0.5):
        for x in (-w * 0.5, w * 0.5):
            b.cyl("Galv", (x, 0, z), (x, h + 0.2, z), 0.04, 8)
    b.collide((0, 0.05, 0), (w, 0.2, d))
    b.collide((0, h * 0.5 + 0.15, -d * 0.5), (w, h, 0.1))
    b.collide((-w * 0.5, h * 0.5 + 0.15, 0), (0.1, h, d))
    b.collide((w * 0.5, h * 0.5 + 0.15, 0), (0.1, h, d))
    return b


def garage_box(mat: str, open_gate: bool) -> Builder:
    """Металлический гараж 3.2×6×2.3: листы со сварными швами, ворота-створки, навесной замок."""
    b = Builder()
    w, l, h = 3.2, 6.0, 2.3
    # стены листами по 1.5 м с выступающими швами
    for side in (-1, 1):
        b.box(mat, (side * w * 0.5, h * 0.5, 0), (0.03, h, l))
        for k in range(5):
            b.box(mat, (side * (w * 0.5 + 0.015), h * 0.5, -l * 0.5 + k * 1.5), (0.03, h, 0.04))
    b.box(mat, (0, h * 0.5, l * 0.5), (w, h, 0.03))
    b.box(mat, (0, h + 0.08, 0), (w + 0.12, 0.04, l + 0.15), pitch=1.5)
    b.box("Void", (0, h * 0.5, 0), (w - 0.1, h - 0.05, l - 0.1))
    gate_w = w * 0.5 - 0.05
    if open_gate:
        b.box(mat, (-w * 0.5 - 0.02, (h - 0.1) * 0.5, -l * 0.5 - gate_w * 0.5), (0.03, h - 0.1, gate_w), bevel=0.005)
        b.box(mat, (w * 0.25, (h - 0.1) * 0.5, -l * 0.5 - 0.02), (gate_w, h - 0.1, 0.03), bevel=0.005)
    else:
        for side in (-1, 1):
            b.box(mat, (side * w * 0.25, (h - 0.1) * 0.5, -l * 0.5 - 0.02), (gate_w, h - 0.1, 0.03), bevel=0.005)
        b.box("Bars", (0.05, 1.1, -l * 0.5 - 0.06), (0.06, 0.08, 0.04))
    b.box("Galv", (0, h - 0.05, -l * 0.5 - 0.04), (w, 0.08, 0.06))
    b.collide((0, h * 0.5, 0), (w, h, l))
    return b


def rakushka(mat: str) -> Builder:
    """Гараж-«ракушка»: гнутый лист по профилю (вертикальная спинка, выпуклая крыша к низкому носу)."""
    b = Builder()
    w = 2.6
    prof = []
    for k in range(17):
        t = k / 16
        z = -2.6 + 5.4 * t
        y = 1.95 * math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.7 if t < 0.97 else 0.0
        y = max(y, 0.0)
        prof.append((z, y))
    prof[0] = (-2.6, 0.0)
    prof.insert(1, (-2.6, 1.3))
    for (z0, y0), (z1, y1) in zip(prof, prof[1:]):
        seg = math.hypot(z1 - z0, y1 - y0)
        ang = math.degrees(math.atan2(y1 - y0, z1 - z0))
        b.box(mat, (0, (y0 + y1) * 0.5, (z0 + z1) * 0.5), (w, 0.025, seg + 0.02), pitch=-ang)
        for x in (-w * 0.5, w * 0.5):
            b.box(mat, (x, (y0 + y1) * 0.25, (z0 + z1) * 0.5), (0.02, max(0.02, (y0 + y1) * 0.5), seg + 0.02))
    for k in range(5):
        x = -w * 0.5 + 0.2 + k * (w - 0.4) / 4
        b.box(mat, (x, 1.0, 0.0), (0.03, 0.03, 5.0), yaw=0)
    b.box("Bars", (0.0, 0.5, 2.7), (0.08, 0.06, 0.05))
    b.collide((0, 0.95, 0), (w, 1.9, 5.3))
    return b


def shed_row(n: int, seed: int) -> Builder:
    """Ряд дощатых сараев 2.4×3×2.3 под общей односкатной крышей из профлиста."""
    rng = random.Random(seed)
    b = Builder()
    w, d, h = 2.4, 3.0, 2.3
    L = n * w
    for k in range(n):
        x = -L * 0.5 + (k + 0.5) * w
        for z in (-d * 0.5, d * 0.5):
            for p in range(int(w / 0.15)):
                b.box("WoodPlanks", (x - w * 0.5 + (p + 0.5) * 0.15, h * 0.5, z), (0.14, h - rng.uniform(0, 0.1), 0.025), yaw=rng.uniform(-1, 1))
        b.box("WoodPlanks", (x - w * 0.5, h * 0.5, 0), (0.03, h, d))
        door_open = rng.random() < 0.35
        if door_open:
            b.box("Void", (x, 1.0, -d * 0.5 + 0.05), (0.85, 1.9, 0.02))
            b.box("WoodPlanks", (x - 0.42, 1.0, -d * 0.5 - 0.4), (0.04, 1.9, 0.8))
        else:
            b.box("WoodPlanks", (x, 1.0, -d * 0.5 - 0.03), (0.85, 1.9, 0.04))
            b.box("Bars", (x + 0.35, 1.1, -d * 0.5 - 0.07), (0.05, 0.07, 0.04))
    b.box("WoodPlanks", (L * 0.5, h * 0.5, 0), (0.03, h, d))
    b.box("CorrGrey", (0, h + 0.15, 0), (L + 0.4, 0.03, d + 0.5), pitch=-6)
    b.collide((0, h * 0.5, 0), (L, h, d))
    return b


def laundry_pair() -> Builder:
    """Сушилка белья: две Т-образные стойки из труб через 4 м и четыре провисших проволоки."""
    b = Builder()
    for z in (-2.0, 2.0):
        b.cyl("Railing", (0, -0.3, z), (0, 2.1, z), 0.035, 8)
        b.cyl("Railing", (-0.9, 2.05, z), (0.9, 2.05, z), 0.03, 8)
        b.box("Concrete", (0, 0.02, z), (0.3, 0.1, 0.3))
    for x in (-0.75, -0.25, 0.25, 0.75):
        prev = Vector((x, 2.05, -2.0))
        for k in range(1, 9):
            t = k / 8
            p = Vector((x, 2.05 - 0.18 * math.sin(math.pi * t), -2.0 + 4.0 * t))
            b.cyl("Wire", prev, p, 0.004, 3)
            prev = p
    b.collide((0, 1.0, -2.0), (0.1, 2.1, 0.1))
    b.collide((0, 1.0, 2.0), (0.1, 2.1, 0.1))
    return b


def lawn_fence() -> Builder:
    """Газонное ограждение 3 м: столбики и перекрещённые дуги из гнутой трубы, крашеные, с ржавчиной."""
    b = Builder()
    for x in (-1.5, 0.0, 1.5):
        b.cyl("PaintGreenMetal", (x, -0.15, 0), (x, 0.55, 0), 0.025, 6)
    for x0 in (-1.5, -0.75, 0.0):
        prev = None
        for k in range(9):
            t = k / 8
            p = Vector((x0 + 1.5 * t, 0.12 + 0.42 * math.sin(math.pi * t), 0))
            if prev is not None:
                b.cyl("PaintGreenMetal", prev, p, 0.014, 5)
            prev = p
    b.cyl("PaintGreenMetal", (-1.5, 0.12, 0), (1.5, 0.12, 0), 0.014, 5)
    return b


def lamp_post() -> Builder:
    """Фонарь: бетонная опора 9 м (конус), стальной кронштейн, светильник-«кобра»."""
    b = Builder()
    for k in range(6):
        y0, y1 = k * 1.5, (k + 1) * 1.5
        r = 0.13 - k * 0.012
        b.box("Concrete", (0, (y0 + y1) * 0.5, 0), (r * 2, 1.52, r * 2), bevel=0.01)
    b.cyl("Galv", (0, 8.6, 0), (0, 9.1, 1.4), 0.035, 8)
    b.cyl("Galv", (0, 9.1, 1.4), (0, 9.15, 1.8), 0.035, 8)
    b.box("LampHead", (0, 9.08, 2.05), (0.32, 0.14, 0.62), bevel=0.03, pitch=8)
    b.box("Glass", (0, 9.0, 2.05), (0.26, 0.02, 0.48), pitch=8)
    b.cyl("Wire", (0, 8.4, 0), (0, 8.4, -6.0), 0.006, 3)
    b.collide((0, 4.5, 0), (0.3, 9.0, 0.3))
    return b


# ------------------------------------------------------------------ детская площадка

def swing() -> Builder:
    """Качели: две А-образные стойки из труб, перекладина 2.3 м, сиденья на жёстких подвесах."""
    b = Builder()
    for x in (-1.2, 1.2):
        for z in (-0.8, 0.8):
            b.cyl("PlayBlue", (x, 0, z), (x, 2.3, 0), 0.04, 8)
    b.cyl("PlayBlue", (-1.25, 2.3, 0), (1.25, 2.3, 0), 0.045, 8)
    for sx, ang in ((-0.55, 0.0), (0.55, 18.0)):
        top = Vector((sx, 2.28, 0))
        seat = Vector((sx, 0.5, math.sin(math.radians(ang)) * 1.7))
        for dx in (-0.22, 0.22):
            b.cyl("Galv", top + Vector((dx, 0, 0)), seat + Vector((dx, 0.05, 0)), 0.012, 4)
        b.box("PlayYellow", tuple(seat), (0.5, 0.04, 0.25), pitch=ang, bevel=0.01)
    b.collide((-1.2, 1.15, 0), (0.1, 2.3, 1.6))
    b.collide((1.2, 1.15, 0), (0.1, 2.3, 1.6))
    return b


def slide() -> Builder:
    """Горка: лестница, площадка 1.5 м с перилами, стальной скат."""
    b = Builder()
    for x in (-0.35, 0.35):
        b.cyl("PlayRed", (x, 0, -1.2), (x, 1.5, -0.4), 0.035, 8)
        b.cyl("PlayRed", (x, 1.5, -0.4), (x, 2.4, -0.4), 0.03, 8)
        b.cyl("PlayRed", (x, 0, 0.4), (x, 2.4, 0.4), 0.035, 8)
    for k in range(6):
        t = (k + 1) / 7
        b.cyl("Galv", (-0.35, 1.5 * t, -1.2 + 0.8 * t), (0.35, 1.5 * t, -1.2 + 0.8 * t), 0.02, 6)
    b.box("PlayRed", (0, 1.5, 0), (0.8, 0.05, 0.85), bevel=0.01)
    b.cyl("PlayRed", (-0.35, 2.4, -0.4), (-0.35, 2.4, 0.4), 0.025, 6)
    b.cyl("PlayRed", (0.35, 2.4, -0.4), (0.35, 2.4, 0.4), 0.025, 6)
    run = 3.0
    ang = math.degrees(math.atan2(1.5, run))
    b.box("Galv", (0, 0.78, 0.42 + run * 0.5), (0.5, 0.03, math.hypot(1.5, run)), pitch=ang)
    for x in (-0.27, 0.27):
        b.box("Galv", (x, 0.88, 0.42 + run * 0.5), (0.03, 0.18, math.hypot(1.5, run)), pitch=ang)
    b.collide((0, 0.75, 0.0), (0.9, 1.5, 0.9))
    return b


def carousel() -> Builder:
    """Карусель: круглая площадка Ø1.7 на ступице, поручни-скобы."""
    b = Builder()
    b.cyl("Galv", (0, 0, 0), (0, 0.35, 0), 0.08, 10)
    b.cyl("PlayYellow", (0, 0.32, 0), (0, 0.38, 0), 0.85, 20)
    b.cyl("PlayRed", (0, 0.38, 0), (0, 0.95, 0), 0.04, 8)
    for k in range(4):
        a = k * math.pi / 2
        p = Vector((math.cos(a) * 0.65, 0.38, math.sin(a) * 0.65))
        b.cyl("PlayRed", p, p + Vector((0, 0.5, 0)), 0.025, 6)
        b.cyl("PlayRed", p + Vector((0, 0.5, 0)), Vector((0, 0.95, 0)), 0.02, 6)
    b.collide((0, 0.35, 0), (1.7, 0.7, 1.7))
    return b


def climbing_arch() -> Builder:
    """Дуга-лестница («радуга»): две гнутые трубы 4 м и перекладины."""
    b = Builder()
    pts = []
    for k in range(13):
        t = k / 12
        pts.append((-2.0 + 4.0 * t, 1.9 * math.sin(math.pi * t)))
    for z in (-0.4, 0.4):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            b.cyl("PlayBlue", (x0, y0, z), (x1, y1, z), 0.035, 8)
    for x, y in pts[1:-1]:
        b.cyl("PlayYellow", (x, y, -0.4), (x, y, 0.4), 0.02, 6)
    b.collide((0, 0.95, 0), (4.0, 1.9, 0.8))
    return b


def sandbox() -> Builder:
    """Песочница 3×3: брусья по краю (сиденья), песок с бугром."""
    b = Builder()
    for (x, z, w, d) in [(0, -1.45, 3.0, 0.2), (0, 1.45, 3.0, 0.2), (-1.45, 0, 0.2, 3.0), (1.45, 0, 0.2, 3.0)]:
        b.box("BenchWood", (x, 0.15, z), (w, 0.3, d), bevel=0.01)
    b.box("Sand", (0, 0.08, 0), (2.7, 0.16, 2.7))
    b.box("Sand", (0.4, 0.17, -0.3), (1.0, 0.1, 0.8), yaw=20, bevel=0.04)
    return b


# ------------------------------------------------------------------ деревья

TREE_KINDS = {
    # высота, радиус ствола, доля голого ствола, ветвей 1-го порядка, угол от вертикали, кора, листва, доля листьев
    "birch": (15.0, 0.17, 0.32, 14, 38.0, "BarkBirch", "LeavesBirch", 0.4),
    "poplar": (22.0, 0.32, 0.22, 16, 26.0, "BarkDark", "LeavesMaple", 0.08),
    "maple": (10.0, 0.14, 0.25, 9, 58.0, "BarkDark", "LeavesMaple", 0.22),
}


def tree(kind: str, seed: int) -> Builder:
    rng = random.Random(seed)
    b = Builder()
    H, R, bare, primaries, spread, bark, leaves, leafy = TREE_KINDS[kind]
    H *= rng.uniform(0.85, 1.12)
    lean = Vector((rng.uniform(-0.08, 0.08), 1.0, rng.uniform(-0.08, 0.08))).normalized()

    def limb(start: Vector, direction: Vector, length: float, radius: float, depth: int) -> None:
        # бюджет: ствол 8 граней, ветки 5–4, веточки — 3 грани в 2 сегмента, без торцов
        segs = 5 if depth == 0 else (4 if depth == 1 else (3 if depth == 2 else 2))
        sides = (8, 5, 4, 3)[min(depth, 3)]
        mat = bark
        p = start.copy()
        d = direction.normalized()
        pts = [p.copy()]
        for k in range(segs):
            # ветви первого порядка тянутся вверх, мелкие — свисают (берёза) или торчат
            if depth == 0:
                d = (d + Vector((rng.gauss(0, 0.04), 0.02, rng.gauss(0, 0.04)))).normalized()
            elif depth == 1:
                d = (d + Vector((rng.gauss(0, 0.12), 0.06, rng.gauss(0, 0.12)))).normalized()
            else:
                droop = 0.22 if kind == "birch" else 0.06
                d = (d + Vector((rng.gauss(0, 0.2), -droop, rng.gauss(0, 0.2)))).normalized()
            p = p + d * (length / segs)
            pts.append(p.copy())
        for k in range(segs):
            r0 = radius * (1 - k / segs * 0.75)
            r1 = radius * (1 - (k + 1) / segs * 0.75)
            b.cyl(mat, pts[k], pts[k + 1], (r0 + r1) * 0.5, sides, caps=False)
        if depth >= 3:
            if rng.random() < leafy:
                leaf_card(pts[-1], d)
            return
        if depth == 0:
            count = primaries
            t0 = bare
        else:
            count = (5, 4, 3)[depth - 1] if depth < 3 else 0
            t0 = 0.25
        for c in range(count):
            t = t0 + (1 - t0) * (c + rng.random()) / count
            idx = min(int(t * segs), segs - 1)
            frac = t * segs - idx
            base = pts[idx].lerp(pts[idx + 1], frac)
            az = rng.uniform(0, 2 * math.pi) if depth == 0 else rng.uniform(0, 2 * math.pi)
            ang = math.radians(spread if depth == 0 else rng.uniform(30, 55))
            side = Vector((math.cos(az), 0, math.sin(az)))
            child_dir = (d * math.cos(ang) + side * math.sin(ang)).normalized()
            if depth == 0:
                child_len = length * (0.42 if kind != "poplar" else 0.33) * (1.15 - 0.6 * t) * rng.uniform(0.8, 1.15)
            else:
                child_len = length * rng.uniform(0.4, 0.6)
            limb(base, child_dir, child_len, radius * (0.42 if depth == 0 else 0.5) * (1.1 - 0.5 * t), depth + 1)
        if depth >= 2 and rng.random() < leafy:
            leaf_card(pts[-1], d)

    def leaf_card(at: Vector, d: Vector) -> None:
        s = rng.uniform(0.7, 1.1)
        for k in range(2):
            a = rng.uniform(0, math.pi) + k * math.pi / 2
            ax = Vector((math.cos(a), 0, math.sin(a))) * s * 0.5
            up = Vector((0, s, 0))
            c0 = at - ax - up * 0.3
            card(b, leaves, [c0, c0 + ax * 2, c0 + ax * 2 + up, c0 + up], [(0, 0), (1, 0), (1, 1), (0, 1)])

    if kind == "maple":
        # клён ясенелистный — 2–3 ствола из одного корня
        for k in range(rng.choice([2, 3])):
            az = rng.uniform(0, 2 * math.pi)
            d = (lean + Vector((math.cos(az), 0, math.sin(az))) * 0.35).normalized()
            limb(Vector((0, -0.2, 0)), d, H * rng.uniform(0.75, 0.95), R, 0)
    else:
        limb(Vector((0, -0.3, 0)), lean, H, R, 0)
    b.collide((0, H * 0.3, 0), (R * 2.2, H * 0.6, R * 2.2))
    return b


# ------------------------------------------------------------------ экспорт

def main() -> None:
    random.seed(7)
    items = {
        "bench_back": bench(True), "bench_plain": bench(False),
        "dumpster": dumpster(False), "dumpster_open": dumpster(True), "container_site": container_site(),
        "garage_box_brown": garage_box("GarageMetal", False), "garage_box_blue": garage_box("GarageBlue", False),
        "garage_box_open": garage_box("GarageMetal", True),
        "rakushka_green": rakushka("CorrGreen"), "rakushka_rust": rakushka("RustMetal"),
        "shed_row": shed_row(4, 3), "laundry_pair": laundry_pair(), "lawn_fence": lawn_fence(), "lamp_post": lamp_post(),
        "play_swing": swing(), "play_slide": slide(), "play_carousel": carousel(), "play_arch": climbing_arch(),
        "play_sandbox": sandbox(),
    }
    for kind in ("birch", "poplar", "maple"):
        for v in range(3):
            items[f"tree_{kind}_{v}"] = tree(kind, 100 + v * 17 + len(kind))
    manifest = {}
    for name, b in items.items():
        tris = kh.export(name, b)
        manifest[name] = dict(triangles=tris, collisions=b.collisions, materials=sorted(b.data))
    (OUT / "props.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


main()
