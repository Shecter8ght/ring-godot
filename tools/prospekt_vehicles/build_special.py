"""Транспорт «Проспекта», партия 2: такси и полиция на принятом седане (форма v01) — навесные детали на крышу.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_special.py -- \
        <taxi|police> <выход.blend>

Кузов — без изменений из Sedan_geometry_v01.blend (принят владельцем 2026-10-25); раскраска (шашки, полосы, надписи,
бортовой номер) — отделкой. Здесь только то, чего у седана нет:
- такси — плафон «шашечки» на магнитных лапках поперёк крыши, провод к двери водителя;
- полиция — балка проблесковых маячков (синий слева, красный справа, громкоговоритель посередине) на кронштейнах,
  зацепленных за проёмы дверей, и антенна рации на задней части крыши (не на крышке багажника: у «Открыт» она поднята).
Варианты — коллекции седана «Целый», «Открыт», «Битый» (у битого такси плафон сбит набок); «Сгоревший» не берётся —
пластик плафона и балки сгорел бы вместе с салоном. Детали — дочерние к корню варианта (двигаются с машиной).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401 — подключает модули купе (engine_bay, parts)
import parts as pt  # noqa: E402
from build_car import link, make_mesh  # noqa: E402
from engine_bay import rounded_block, tube  # noqa: E402

SEDAN = Path("E:/Models Blender/VEHICLES/Город_партия1/Седан/models/Sedan_geometry_v01.blend")
KEEP = ("Целый", "Открыт", "Битый")


def roof_top(col: bpy.types.Collection, root: bpy.types.Object) -> tuple[float, float, float]:
    """Верх крыши в осях корня: середина крыши по длине (y), высота там (z) и ширина плоской части (по z − 3 см)."""
    roof = next(o for o in col.objects if o.type == "MESH" and o.name.startswith("Roof"))
    inv = root.matrix_world.inverted()
    P = np.array([tuple(inv @ (roof.matrix_world @ v.co)) for v in roof.data.vertices])
    yc = float(np.median(P[:, 1]))
    mid = P[np.abs(P[:, 1] - yc) < 0.12]
    z = float(mid[np.abs(mid[:, 0]) < 0.25][:, 2].max())
    flat = mid[mid[:, 2] > z - 0.03]
    return yc, z, float(np.abs(flat[:, 0]).max())


def taper(mesh, k_top: float, z0: float, z1: float):
    """Сужение по высоте вдоль Y (трапеция плафона): у низа ×1, у верха ×k_top."""
    V, F = mesh
    V = np.asarray(V, float).copy()
    t = np.clip((V[:, 2] - z0) / (z1 - z0), 0.0, 1.0)
    cy = (V[:, 1].min() + V[:, 1].max()) / 2
    V[:, 1] = cy + (V[:, 1] - cy) * (1.0 - (1.0 - k_top) * t)
    return V, F


def taxi(yc: float, z: float, half: float) -> list:
    """Плафон «шашечки»: трапеция 0,54 × 0,15 × 0,15 м поперёк крыши, торцы скруглены, четыре резиновые лапки-магнита,
    провод по крыше к стойке водителя."""
    zb = z + 0.022
    body = taper(rounded_block((0.0, yc, zb + 0.075), 0.54, 0.15, 0.15, 0.03), 0.62, zb, zb + 0.15)
    feet = [rounded_block((sx * 0.20, yc + sy * 0.045, z + 0.010), 0.07, 0.05, 0.022, 0.008)
            for sx in (1, -1) for sy in (1, -1)]
    wire = tube([(0.27, yc, zb + 0.03), (0.32, yc - 0.05, z + 0.01), (half - 0.05, yc - 0.20, z - 0.005),
                 (half + 0.06, yc - 0.30, z - 0.06)], 0.0035, 6, 16)
    return [("Taxi_Sign", "sign_plastic", body), ("Taxi_Sign_Feet", "rubber", pt.merge(feet)),
            ("Taxi_Sign_Wire", "trim_black", wire)]


def police(yc: float, z: float, half: float, ant_at: tuple[float, float]) -> list:
    """Балка маячков 1,10 × 0,28 × 0,13 м: основание, колпаки синий (слева, +X) и красный, громкоговоритель между ними;
    два кронштейна поперёк крыши с крючками за проёмы дверей; антенна рации на крыше за балкой (ant — точка y, z)."""
    zb = z + 0.045
    base = rounded_block((0.0, yc, zb + 0.025), 1.10, 0.28, 0.05, 0.02)
    lens_l = rounded_block((0.30, yc, zb + 0.090), 0.46, 0.25, 0.09, 0.035)
    lens_r = rounded_block((-0.30, yc, zb + 0.090), 0.46, 0.25, 0.09, 0.035)
    spk = rounded_block((0.0, yc - 0.01, zb + 0.085), 0.13, 0.22, 0.08, 0.025)
    brackets = []
    for sy in (-0.09, 0.09):
        brackets.append(rounded_block((0.0, yc + sy, z + 0.018), 2 * half - 0.10, 0.035, 0.012, 0.004))
        for sx in (1, -1):
            brackets.append(rounded_block((sx * 0.40, yc + sy, z + 0.032), 0.05, 0.05, 0.03, 0.01))
            brackets.append(tube([(sx * (half - 0.05), yc + sy, z + 0.018), (sx * (half + 0.02), yc + sy, z - 0.02),
                                  (sx * (half + 0.03), yc + sy, z - 0.10)], 0.006, 6, 10))
    ty, tz = ant_at
    ant = pt.merge([rounded_block((0.0, ty, tz + 0.010), 0.06, 0.06, 0.022, 0.01),
                    tube([(0.0, ty, tz + 0.02), (0.0, ty + 0.01, tz + 0.70)], 0.0025, 6, 4)])
    return [("Police_Bar_Base", "trim_black", base), ("Police_Bar_Lens_L", "lamp_blue", lens_l),
            ("Police_Bar_Lens_R", "lamp_red", lens_r), ("Police_Bar_Speaker", "trim_black", spk),
            ("Police_Bar_Brackets", "steel_dark", pt.merge(brackets)), ("Police_Antenna", "trim_black", ant)]


def roof_point(col: bpy.types.Collection, root: bpy.types.Object, y: float) -> tuple[float, float]:
    """Верх крыши по середине ширины в сечении y (осях корня) — место антенны."""
    roof = next(o for o in col.objects if o.type == "MESH" and o.name.startswith("Roof"))
    inv = root.matrix_world.inverted()
    P = np.array([tuple(inv @ (roof.matrix_world @ v.co)) for v in roof.data.vertices])
    near = P[(np.abs(P[:, 1] - y) < 0.05) & (np.abs(P[:, 0]) < 0.15)]
    return y, float(near[:, 2].max())


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    kind, out = argv[0], Path(argv[1])
    bpy.ops.wm.open_mainfile(filepath=str(SEDAN))
    for c in list(bpy.data.collections):
        if c.name not in KEEP:
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
    for i, name in enumerate(KEEP):
        col = bpy.data.collections[name]
        root = next(o for o in col.objects if o.parent is None)
        yc, z, half = roof_top(col, root)
        if kind == "taxi":
            items = taxi(yc, z, half)
        else:
            items = police(yc - 0.10, z, half, roof_point(col, root, yc + 0.40))
        for nm, mat, (V, F) in items:
            if kind == "taxi" and name == "Битый" and nm == "Taxi_Sign_Wire":
                continue                                    # провод оборван
            ob = link(f"{nm}_{name}", make_mesh(nm, mat, V, F), col, root)
            if kind == "taxi" and name == "Битый":
                # плафон сбит ударом: опрокинулся назад через заднее ребро низа и лёг на крышу, развёрнут и сдвинут
                pivot = Vector((0.0, yc + 0.075, z + 0.022))
                ob.matrix_basis = (Matrix.Translation((0.06, 0.04, 0.0)) @ Matrix.Translation(pivot) @
                                   Matrix.Rotation(math.radians(28.0), 4, "Z") @ Matrix.Rotation(math.radians(-90.0), 4, "X") @
                                   Matrix.Translation(-pivot))
        print(f"{kind} {name}: крыша y={yc:.2f} z={z:.3f}, полуширина плоской части {half:.2f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("сохранено:", out)


if __name__ == "__main__":
    main()
