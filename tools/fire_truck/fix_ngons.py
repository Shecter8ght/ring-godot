"""Пожарная АЦ: многоугольники, которые Blender триангулирует через проём, — заново отсечением ушей.

После деления длинных рёбер (tex_uv.subdivide_long, сетка с заполнением) грань с вырезом («замочная скважина»: створка
двери с окном, стенка лонжерона с отверстиями) распадалась на 70-угольники, и обычная триангуляция затягивала проём
(красный треугольник на окне двери экипажа). Грань, у которой сумма треугольников больше её площади, разбивается на
треугольники ear clip — граница та же, UV углов сохраняются, развёртка и карты не меняются.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/fire_truck/fix_ngons.py [-- <выход.blend>]
"""
from __future__ import annotations

import sys

import bmesh
import bpy


def fix(objs, verbose=True) -> int:
    total = 0
    done = set()
    for o in objs:
        me = o.data
        if o.type != "MESH" or me in done:
            continue
        done.add(me)
        me.calc_loop_triangles()
        tri_area = [0.0] * len(me.polygons)
        for t in me.loop_triangles:
            tri_area[t.polygon_index] += t.area
        bad = [p.index for p in me.polygons if len(p.vertices) > 4 and tri_area[p.index] > p.area * 1.01 + 1e-7]
        if not bad:
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        faces = [bm.faces[i] for i in bad]
        bmesh.ops.triangulate(bm, faces=faces, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        bm.to_mesh(me)
        bm.free()
        me.update()
        total += len(bad)
        if verbose:
            print(f"  {o.name}: перетриангулировано {len(bad)} граней", flush=True)
    return total


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    n = fix([o for o in bpy.data.objects if o.type == "MESH"])
    print("ИТОГО граней", n)
    out = a[0] if a else bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    main()
