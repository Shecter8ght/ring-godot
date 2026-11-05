# «Осока»: габариты модели (оценённые сетки в мире, положение покоя) против источников.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup <файл.blend> --python tools/osoka/measure.py
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def bbox(names=None, prefix=None, exclude=()):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get():
            continue
        if names and o.name not in names:
            continue
        if prefix and not o.name.startswith(prefix):
            continue
        if any(o.name.startswith(e) for e in exclude):
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        for v in me.vertices:
            p = oe.matrix_world @ v.co
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
        oe.to_mesh_clear()
    return lo * 1000, hi * 1000


def radius(name):
    dg = bpy.context.evaluated_depsgraph_get()
    o = bpy.data.objects[name].evaluated_get(dg)
    me = o.to_mesh()
    r = max(math.hypot((o.matrix_world @ v.co).y, (o.matrix_world @ v.co).z) for v in me.vertices) * 1000
    o.to_mesh_clear()
    return r


def row(name, src, val, got):
    if got is None:
        return
    dev = "" if val is None else f"{got - val:+.1f} мм ({(got - val) / val * 100:+.1f} %)"
    print(f"MEASURE | {name} | {src} | {'' if val is None else round(val, 1)} | {got:.1f} | {dev}")


def main():
    ctrl = bpy.data.objects["OSOKA_Controls"]
    for k in ctrl.keys():
        if not k.startswith("_"):
            ctrl[k] = 1.0 if k in ("front_sight", "rear_sight") else 0.0
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    lo, hi = bbox(exclude=("Missile",))
    row("Длина с крышками", "труба «Иглы» 9П39 1,71 м (weaponsystems) = масштаб снимка КБМ", 1710.0, hi.x - lo.x)
    row("Высота: верх целика … низ рукояти", "снимок КБМ 305…755 пикс", 450 * 0.66330, hi.z - lo.z)
    row("Ширина наибольшая (крышка Ø114 / прицельные слева)", "оценка", None, hi.y - lo.y)
    row("Труба Ø", "снимок КБМ 116 пикс", 116 * 0.66330, 2 * radius("Tube_body"))
    row("Передняя крышка Ø", "снимок КБМ 172 пикс", 172 * 0.66330, 2 * radius("Front_cap"))
    row("Хомут ГСН Ø", "снимок КБМ 166 пикс", 166 * 0.66330, 2 * radius("Tube_collar"))
    row("Задняя крышка Ø", "снимок КБМ 146 пикс", 146 * 0.66330, 2 * radius("Rear_cap"))
    g0, g1 = bbox(prefix="Launcher_grip")
    row("Спусковая рама с рукоятью: высота", "снимок КБМ 575…755 пикс", 180 * 0.66330, g1.z - g0.z)
    row("Рукоять: длина низа (перёд — зад)", "снимок КБМ 615…682.5 пикс", 67.5 * 0.66330, None)
    row("Рукоять: толщина", "Sketchfab (оценка)", 30.0, g1.y - g0.y)
    b0, b1 = bbox(names=("Box_lower",))
    row("Короб: длина", "снимок КБМ 753…1053 пикс", 300 * 0.66330, b1.x - b0.x)
    row("Короб: ширина", "Sketchfab (оценка)", 58.0, b1.y - b0.y)
    p0, p1 = bbox(names=("Power_source",))
    row("Источник питания Ø", "снимок КБМ 98 пикс", 65.0, 2 * radius("Power_source") if False else (p1.y - p0.y))
    s0, s1 = bbox(names=("Power_socket",))
    row("Шар гнезда Ø", "снимок КБМ 143 пикс", 95.0, s1.y - s0.y)
    # ракета — в своих осях (корень на X0)
    m0, m1 = bbox(prefix="Missile_body")
    n0, n1 = bbox(names=("Missile_needle",))
    row("Ракета: Ø корпуса", "КБМ: 72 мм", 72.0, 2 * radius("Missile_body"))
    row("Ракета: длина корпуса", "снимок cap_01: L/D 21.4", 1545.0, m1.x - m0.x)
    row("Ракета: с иглой", "оценка (игла 62)", 1607.0, n1.x - m0.x)
    row("Ракета: «Игла» для сверки", "КБМ: 1655 мм (9М39)", 1655.0, n1.x - m0.x)
    tri = 0
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.data.calc_loop_triangles(); tri += len(o.data.loop_triangles)
    print("MEASURE_TRIS", tri)


main()
