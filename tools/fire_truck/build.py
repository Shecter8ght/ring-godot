"""Пожарная автоцистерна (по мотивам АЦ-3,2-40/4 на КамАЗ-43253) в sand3d: сборка high-poly формы в .blend.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/fire_truck/build.py -- <выход.blend> [части: chassis,cab,body,roof]

Коллекции: «Целая» (рольставни закрыты) и «Отсеки открыты» (рольставни подняты, видны отсеки с полками);
общие детали лежат в обеих — переключать видимость коллекций в Outliner.
Материалы проверочные (цвета частей); UV и отделка — после принятия формы.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402

import lib  # noqa: E402
from lib import s3d  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0]) if argv else None
PARTS = argv[1].split(",") if len(argv) > 1 else ["chassis", "cab", "body", "roof"]


def tris_of(objs) -> int:
    n = 0
    for ob in objs:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            n += len(ob.data.loop_triangles)
    return n


def tree(root) -> list:
    out = [root]
    for ch in root.children:
        out += tree(ch)
    return out


def main() -> None:
    s3d.empty_scene()
    s3d.units("m")
    t0 = time.time()
    common, closed, opened = [], [], []
    report = []
    for name in PARTS:
        t = time.time()
        mod = __import__(name)
        got = mod.build()                     # {"common": [...], "closed": [...], "open": [...]}
        for key, dst in (("common", common), ("closed", closed), ("open", opened)):
            for root in got.get(key, []):
                dst.extend(tree(root))
        objs = [o for k in ("common", "closed", "open") for r in got.get(k, []) for o in tree(r)]
        report.append(f"{name}: {time.time() - t:.1f} с, объектов {len(objs)}, треугольников {tris_of(objs):,}")
        print(report[-1], flush=True)

    scene = bpy.context.scene
    col_closed = bpy.data.collections.new("Целая")
    col_open = bpy.data.collections.new("Отсеки открыты")
    scene.collection.children.link(col_closed)
    scene.collection.children.link(col_open)

    def put(ob, cols) -> None:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        for c in cols:
            c.objects.link(ob)

    for ob in common:
        put(ob, [col_closed, col_open])
    for ob in closed:
        put(ob, [col_closed])
    for ob in opened:
        put(ob, [col_open])
    col_open.hide_viewport = False
    vl = bpy.context.view_layer
    vl.layer_collection.children["Отсеки открыты"].hide_viewport = True
    # нулевые грани после булевых и скруглений (точно нулевой площади) — растворить; больше ничего не трогается
    import bmesh
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        zero = [f for f in bm.faces if f.calc_area() < 1e-10]
        if zero:
            # вершины, сошедшиеся в точку (углы проёма окна после скругления), — слить только их
            bmesh.ops.remove_doubles(bm, verts=list({v for f in zero for v in f.verts}), dist=1e-5)
            zero = [f for f in bm.faces if f.is_valid and f.calc_area() < 1e-10]
            bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list({e for f in zero for e in f.edges}))
            left = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
            bm.to_mesh(ob.data)
            print(f"  {ob.name}: нулевые грани убраны, осталось {left}")
        bm.free()
        ob.data.update()
    all_closed = [o for o in common + closed]
    all_open = [o for o in common + opened]
    print(f"итого: {time.time() - t0:.1f} с; «Целая» {tris_of(all_closed):,} тр., «Отсеки открыты» {tris_of(all_open):,} тр.")
    # открыть файл сразу в режиме просмотра материалов, вид на машину спереди-слева
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "MATERIAL"
                        sp.clip_end = 500.0
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    if OUT:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
        print("сохранено:", OUT)


main()
