"""Контейнеры для лута, партия 1 — формы для просмотра владельцем (без текстур, развёртки и игровых версий).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/loot_containers/build_batch1.py -- "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Containers_v01.blend" \
      [preview <папка> [ключи предметов через запятую]] [check]

Шесть предметов, у каждого закрытое и открытое состояние (свой корень и коллекция): сейф напольный, сейф-ячейка,
оружейный шкаф, кассовое место, медицина (сумка-укладка и аптечка), картотечный шкаф. Соглашения — как у партии 3
вещей общежития (build_items3.py): корень-пустышка на опоре, лицо к −Y, подвижные детали — узлы с осью в шарнире.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import lc  # noqa: E402
import safes  # noqa: E402
import cabinets  # noqa: E402
import cash  # noqa: E402
import medical  # noqa: E402
from lc import L, V  # noqa: E402
import build_furniture as B  # noqa: E402

# ключ, подпись, функция, ширина места в ряду; (закрыт, открыт)
ITEMS = [
    ("safe", "Сейф напольный", safes.floor_safe, 0.75),
    ("cell", "Сейф-ячейка", safes.wall_cell, 0.9),
    ("gun", "Оружейный шкаф", cabinets.gun_cabinet, 1.9),
    ("file", "Картотечный шкаф", cabinets.file_cabinet, 1.0),
    ("cash", "Кассовое место", cash.cash_place, 1.0),
    ("bag", "Медицинская сумка-укладка", medical.med_bag, 1.2),
    ("aid", "Аптечка настенная", medical.med_cabinet, 0.8),
]
WALL_ITEMS = {"cell": 1.3, "aid": 1.3}   # настенные: корень на стене студии, высота


def build(out: str):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    m = lc.mats()
    top = L.collection("Партия1_контейнеры_v01")
    x = 0.0
    placed = []
    for key, label, fn, width in ITEMS:
        for open_ in (False, True):
            name = label + (" открыт" if open_ else "")
            c = L.collection(name, top)
            wall = key in WALL_ITEMS
            # открытое — на 0,0 ... рядом: сдвиг по X
            at = (x + width / 2, 1.4 if wall else 0.0, WALL_ITEMS.get(key, 0.0))
            if wall:
                at = (x + width / 2, 1.4, WALL_ITEMS[key])
            root = fn(c, m, at, open_)
            placed.append((key, open_, name, c, root))
            x += width + 0.3
    B.studio(L.collection("Студия"), x)
    wm = bpy.data.materials["Студия_стена"]
    wm.diffuse_color = (0.07, 0.08, 0.09, 1)
    for n in wm.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (0.07, 0.08, 0.09, 1)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)
    return placed


VIEWS = {
    # ключ: [(имя файла, открыт?, цель относительно корня (x,y,z), дистанция, азимут, подъём, фокус)]
    "safe": [("34", False, (0, 0, 0.35), 1.7, -32, 18, 45), ("34", True, (0, -0.1, 0.35), 2.3, -50, 20, 45),
             ("lock", False, (0, -0.225, 0.38), 0.7, -25, 12, 50), ("hinge", True, (-0.22, -0.23, 0.36), 0.7, -60, 15, 50),
             ("inside", True, (0, -0.05, 0.38), 1.1, -15, 14, 40), ("inside2", True, (0.1, -0.2, 0.36), 1.0, 40, 12, 40)],
    "cell": [("34", False, (0, -0.0, 0.13), 0.8, -28, 15, 45), ("34", True, (0, -0.05, 0.13), 0.9, -50, 15, 45),
             ("lock", False, (0.05, 0.0, 0.13), 0.45, -22, 10, 50), ("inside", True, (0, 0.0, 0.13), 0.65, -10, 12, 40)],
    "gun": [("34", False, (0, 0, 0.9), 3.6, -30, 12, 45), ("34", True, (0, -0.1, 0.9), 4.2, -30, 14, 45),
            ("lock", False, (0.28, -0.25, 0.95), 0.9, -28, 6, 50), ("hinge", True, (-0.5, -0.3, 1.0), 1.4, -50, 8, 50),
            ("inside", True, (0, 0.0, 1.0), 3.0, -5, 8, 40), ("inside2", True, (-0.1, -0.1, 0.4), 1.6, 25, 25, 40)],
    "file": [("34", False, (0, 0, 0.66), 2.9, -30, 14, 45), ("34", True, (0, -0.2, 0.66), 3.3, -35, 16, 45),
             ("lock", False, (0.1, -0.31, 1.15), 0.8, -25, 6, 50), ("front", False, (0, -0.31, 0.75), 0.9, -8, 4, 50), ("inside", True, (0, -0.4, 0.95), 1.3, -20, 42, 40)],
    "cash": [("34", False, (0, 0, 0.25), 1.5, -32, 20, 45), ("34", True, (0, -0.1, 0.2), 1.9, -40, 25, 45),
             ("lock", False, (0, -0.15, 0.25), 0.8, -20, 28, 50), ("inside", True, (0, -0.25, 0.1), 0.9, -10, 55, 40)],
    "bag": [("34", False, (0, 0, 0.15), 1.5, -35, 20, 45), ("34", True, (0, 0, 0.2), 1.7, -35, 22, 45),
            ("lock", False, (-0.15, -0.15, 0.2), 0.7, -20, 20, 50), ("inside", True, (0, 0, 0.1), 1.0, -5, 60, 40)],
    "aid": [("34", False, (0, -0.05, 0), 1.2, -30, 14, 45), ("34", True, (0, -0.1, 0), 1.5, -45, 14, 45),
            ("lock", False, (0.1, -0.1, 0), 0.5, -20, 8, 50), ("inside", True, (0, -0.05, 0), 0.9, -8, 8, 40)],
}


def preview(placed, folder: str, only=None) -> None:
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1000, 780
    sc.render.film_transparent = False
    try:
        sc.eevee.taa_render_samples = 24
    except AttributeError:
        pass
    cam = sc.camera
    wall = bpy.data.objects.get("студия_стена")
    for key, label, _, _ in ITEMS:
        if only and key not in only:
            continue
        for k, (name, open_, tgt, dist, az, el, lens) in enumerate(VIEWS.get(key, [])):
            tag = next(p for p in placed if p[0] == key and p[1] == open_)
            for p in placed:
                p[3].hide_render = p is not tag
            if wall:
                wall.hide_render = key != "aid"
            root = tag[4]
            c = V(root.location) + V(tgt)
            a, e = math.radians(az), math.radians(el)
            cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = lens
            cam.data.clip_start = 0.02
            sc.render.filepath = os.path.join(folder, f"{key}_{'open' if open_ else 'closed'}_{name}.png")
            bpy.ops.render.render(write_still=True)
        print("preview", key, flush=True)
    for p in placed:
        p[3].hide_render = False


def check(placed, argv=()) -> None:
    """Габариты и треугольники по состояниям; пересечения подвижных деталей с корпусом в открытом положении."""
    for key, open_, name, c, root in placed:
        mn, mx = lc.bounds([c])
        sz = mx - mn
        print(f"SIZE {name}: {sz.x*1000:.0f} x {sz.z*1000:.0f} (в) x {sz.y*1000:.0f} (г) мм; tri {lc.tri_count([c])}")
    dg = bpy.context.evaluated_depsgraph_get()

    def tree(obs):
        vs, ps = [], []
        for ob in obs:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            base = len(vs)
            vs += [ev.matrix_world @ v.co for v in me.vertices]
            ps += [tuple(base + i for i in p.vertices) for p in me.polygons]
            ev.to_mesh_clear()
        return BVHTree.FromPolygons(vs, ps) if ps else None
    for key, open_, name, c, root in placed:
        if not open_:
            continue
        movers = [o for o in lc.MOVERS.get(c.name, [])]
        under = set()
        for mv in movers:
            under |= {mv} | {o for o in mv.children_recursive}
        statics = [o for o in c.objects if o.type == "MESH" and o not in under]
        t2 = tree(statics)
        for mv in movers:
            kids = [mv] + [o for o in mv.children_recursive if o.type == "MESH"]
            kids = [o for o in kids if o.type == "MESH"]
            # дочерние подвижные (ручка на двери) к двери не считаем: сравниваем с неподвижным
            t1 = tree(kids)
            pairs = t1.overlap(t2) if t1 and t2 else []
            print(f"OVERLAP {name}: {mv.name} -> неподвижное: {len(pairs)} пар граней")
            if pairs and "detail" in argv:
                for so in statics:
                    ts = tree([so])
                    for kd in kids:
                        tk = tree([kd])
                        k = len(tk.overlap(ts)) if ts and tk else 0
                        if k:
                            print(f"    {kd.name} с {so.name}: {k}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed = build(argv[0])
    if "check" in argv:
        check(placed, argv)
    if "preview" in argv:
        i = argv.index("preview")
        folder = argv[i + 1]
        only = set(argv[i + 2].split(",")) if len(argv) > i + 2 and argv[i + 2] != "check" else None
        preview(placed, folder, only)
        bpy.ops.wm.save_as_mainfile(filepath=argv[0], compress=True)
