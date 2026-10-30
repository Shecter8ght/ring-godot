# AR-15: поиск острых рёбер — где скругления нет или оно сжалось почти в ноль (владелец 30.10: «сохранились острые
# кромки, грани и углы выпуклостей и впадин… скрипт, который показывает количество и местоположение»).
# Острое ребро — общее ребро двух граней с углом между нормалями больше порога (по умолчанию 35°): у скругления из 3+
# сегментов на ребро в 90° шаг ≤ 30°, так что сюда попадает то, что не скруглено или скруглено одним-двумя сегментами.
# Ещё острыми считаются сжатые фаски: угол меньше порога, но радиус (ширина грани поперёк ребра / угол) меньше R_MIN —
# так фаска выглядит после зажима по соседним коротким рёбрам (use_clamp_overlap).
#   blender -b <файл.blend> --python tools/ar15/sharp_edges.py -- [--angle 35] [--min-len 0.3] [--json <отчёт.json>]
#                                                                  [--show <out.blend>]
# --show: в копию файла добавляется коллекция «Острые рёбра» — по объекту на деталь, только эти рёбра (каркас,
# выпуклые красным, вогнутые синим), чтобы владелец видел места в Blender.
import json
import math
import sys
from collections import defaultdict

import bmesh
import bpy

MM = 0.001
R_MIN = 0.35        # мм: скругление меньше этого радиуса на виде не читается — тоже «острое» (зажатая фаска)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"angle": 35.0, "min_len": 0.3, "json": None, "show": None}
    i = 0
    while i < len(a):
        k = a[i].lstrip("-").replace("-", "_")
        o[k] = a[i + 1] if k in ("json", "show") else float(a[i + 1])
        i += 2
    return o


def scan(o, dg, angle, min_len):
    """Острые рёбра детали в мировых мм: (длина, середина, выпуклое?) и сводка."""
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(o.matrix_world)
    bm.normal_update()
    out = []
    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        a = e.calc_face_angle(0.0)
        ln = e.calc_length() / MM
        if ln < min_len or a < math.radians(8.0):
            continue
        if a <= lim:
            # фаска есть, но сжалась: радиус ≈ ширина грани поперёк ребра / угол поворота на ребре
            wid = min(f.calc_area() for f in e.link_faces) / max(e.calc_length(), 1e-9) / MM
            if wid / a >= R_MIN:
                continue
        mid = (e.verts[0].co + e.verts[1].co) * (0.5 / MM)
        out.append((ln, (mid.x, mid.y, mid.z), e.is_convex, e.verts[0].co.copy(), e.verts[1].co.copy()))
    bm.free()
    oe.to_mesh_clear()
    return out


def cluster(edges, cell=6.0):
    """Скопления острых рёбер по ячейкам cell мм: где их больше всего (место, длина, число)."""
    g = defaultdict(lambda: [0.0, 0, [0.0, 0.0, 0.0]])
    for ln, mid, _cv, _a, _b in edges:
        k = tuple(int(math.floor(c / cell)) for c in mid)
        r = g[k]
        r[0] += ln
        r[1] += 1
        for i in range(3):
            r[2][i] += mid[i] * ln
    res = []
    for _k, (ln, n, s) in g.items():
        res.append((round(ln, 1), n, [round(v / ln, 1) for v in s]))
    return sorted(res, reverse=True)


def show(objs_edges):
    col = bpy.data.collections.get("Острые рёбра") or bpy.data.collections.new("Острые рёбра")
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    for kind, color in (("выпуклые", (1.0, 0.1, 0.05, 1.0)), ("вогнутые", (0.1, 0.35, 1.0, 1.0))):
        for name, edges in objs_edges.items():
            sel = [e for e in edges if e[2] == (kind == "выпуклые")]
            if not sel:
                continue
            me = bpy.data.meshes.new(f"sharp_{name}_{kind}")
            verts, ed = [], []
            for _ln, _mid, _cv, a, b in sel:
                verts += [a, b]
                ed.append((len(verts) - 2, len(verts) - 1))
            me.from_pydata(verts, ed, [])
            ob = bpy.data.objects.new(f"Острые_{kind}_{name}", me)
            ob.color = color
            ob.show_in_front = True
            ob.hide_render = True
            col.objects.link(ob)
    # каркас виден в любом режиме вьюпорта: цвет объекта в «Solid», для Rendered — тоже поверх
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.wireframe_color_type = "OBJECT"


def main():
    o = args()
    dg = bpy.context.evaluated_depsgraph_get()
    per = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.visible_get() or ob.name.startswith(("Острые_", "sharp_")):
            continue
        e = scan(ob, dg, o["angle"], o["min_len"])
        if e:
            per[ob.name] = e
    rows = sorted(((sum(x[0] for x in e), len(e), sum(1 for x in e if x[2]), n) for n, e in per.items()), reverse=True)
    tot_len = sum(r[0] for r in rows)
    tot_n = sum(r[1] for r in rows)
    print(f"SHARP_TOTAL рёбер {tot_n}, длина {tot_len / 1000:.2f} м, деталей {len(rows)} (порог {o['angle']}°)")
    for ln, n, cv, name in rows[:40]:
        print(f"SHARP {name:28s} {n:6d} рёбер {ln:9.0f} мм  выпуклых {cv}, вогнутых {n - cv}")
    report = {"angle": o["angle"], "total_edges": tot_n, "total_len_mm": round(tot_len, 1), "objects": {}}
    for ln, n, cv, name in rows:
        report["objects"][name] = {"edges": n, "len_mm": round(ln, 1), "convex": cv, "concave": n - cv,
                                   "hot_spots": cluster(per[name])[:8]}
    if o["json"]:
        with open(o["json"], "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("JSON", o["json"])
    if o["show"]:
        show(per)
        bpy.ops.wm.save_as_mainfile(filepath=o["show"], copy=True, compress=True)
        print("SHOW", o["show"])


main()
