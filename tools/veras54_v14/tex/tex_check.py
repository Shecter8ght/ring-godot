# ВЕРАС-54 v14: проверка файла развёртки против принятой формы.
#   rig <out.json>   — на любом файле: положения подвижных деталей при каждом ползунке VERAS54_Controls (0 и крайнее
#                      значение) → JSON; запускается на v14_04 и на файле развёртки, сравнение — «compare»
#   uv <out.json>    — на файле развёртки: объекты / треугольники / габарит против описи dump.json (v14_04), у каждой
#                      сетки один слой UV «UVMap» в квадрате 0…1, по наборам — растром asset_kit.uv.verify: острова
#                      не налезают друг на друга, отступы между деталями и внутри группы (группы — из npz tex_uv.py),
#                      экземпляры патронов не проверяются (это намеренный внахлёст), материал = набор
#   compare <a.json> <b.json> — без Blender (python): расхождение положений рига
# blender -b <файл> --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_check.py -- rig|uv <out.json>
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))


def compare(pa, pb):
    import math
    a = json.load(open(pa, encoding="utf-8"))
    b = json.load(open(pb, encoding="utf-8"))
    worst = 0.0
    moved = 0
    for k, objs in a.items():
        for n, m in objs.items():
            mb = b[k][n]
            d = max(abs(x - y) for x, y in zip(m, mb))
            worst = max(worst, d)
        moved += len(objs)
    print(f"RIG compare: ползунков {len(a)}, записей {moved}, наибольшее расхождение {worst:.3g}")
    return worst


def rig(out):
    import bpy
    import numpy as np
    ctl = bpy.data.objects["VERAS54_Controls"]
    keys = [k for k in ctl.keys() if isinstance(ctl[k], (int, float))]
    base = {k: float(ctl[k]) for k in keys}
    mesh = [o for o in bpy.data.objects if o.type == "MESH"]

    def snap():
        ctl.update_tag()
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
        bpy.context.view_layer.update()
        return {o.name: [round(float(v), 7) for v in np.array(o.matrix_world).ravel()] for o in mesh}
    s0 = snap()
    res = {"rest": s0}
    for k in keys:
        for v in (0.0, 1.0) if base[k] != 0.0 else (1.0,):
            ctl[k] = v
            if k == "carrier" or k == "cycle":
                ctl["selector"] = 0.6     # с предохранителя (рама упирается в переводчик)
            s = snap()
            moved = {n: m for n, m in s.items() if max(abs(x - y) for x, y in zip(m, s0[n])) > 1e-7}
            res[f"{k}={v}"] = moved
            print(f"RIG {k}={v}: сдвинуто {len(moved)} деталей", flush=True)
            for kk in keys:
                ctl[kk] = base[kk]
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f)


def uv_check(out):
    import bpy
    import numpy as np
    from asset_kit import uv as kit_uv
    import tex_sets as T
    dump = json.load(open(T.WORK + "/dump.json", encoding="utf-8"))
    ref = {r["name"]: r for r in dump["objects"]}
    rep = {"objects": len(bpy.data.objects), "objects_ref": len(dump["objects"]), "problems": []}
    P = rep["problems"]
    # габарит — в позе по умолчанию с пулей в патроннике как в описи (привод держит её × 0,001 и там, и тут)
    bpy.context.view_layer.update()
    tris = 0
    for o in bpy.data.objects:
        r = ref.get(o.name)
        if r is None:
            P.append("лишний объект " + o.name)
            continue
        if o.type != "MESH":
            continue
        me = o.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        tris += nt
        if nt != r["tris"]:
            P.append(f"{o.name}: треугольников {nt} против {r['tris']}")
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        mw = np.array(o.matrix_world, np.float64)
        cw = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        lo, hi = cw.min(0) * 1000, cw.max(0) * 1000
        d = max(np.abs(lo - r["bbox_mm"][0]).max(), np.abs(hi - r["bbox_mm"][1]).max())
        if d > 0.011:
            P.append(f"{o.name}: габарит расходится на {d:.3f} мм")
        if [u.name for u in me.uv_layers] != ["UVMap"]:
            P.append(f"{o.name}: слои UV {[u.name for u in me.uv_layers]}")
            continue
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers["UVMap"].uv.foreach_get("vector", uv)
        if uv.min() < 0.0 or uv.max() > 1.0:
            P.append(f"{o.name}: UV вне квадрата {uv.min():.4f}…{uv.max():.4f}")
        s = o.get("v14_set")
        if s != T.set_of(o.name) or [m.name if m else "" for m in me.materials] != [s]:
            P.append(f"{o.name}: набор {s}, материалы {[m.name if m else '' for m in me.materials]}")
    rep["tris"] = tris
    rep["tris_ref"] = dump["tris_total"]
    # пересечения и отступы по наборам
    import tex_uv as U
    sets = {}
    for s, (res, _aim, names) in T.SETS.items():
        objs = [bpy.data.objects[n] for n in names]
        z = np.load(f"{T.WORK}/uv/{s}.npz")
        for o in objs:                   # группы укладки — в память (в файл не пишутся)
            me = o.data
            at = me.attributes.get("uv_group") or me.attributes.new("uv_group", "INT", "FACE")
            at.data.foreach_set("value", z["grp__" + o.name])
        m, g = U.PAD[res]
        v = kit_uv.verify(objs, res, uv="UVMap", margin=m, group_margin=g)
        # пересечения внутри набора: растр треугольников без отступа — пиксель, накрытый двумя островами
        v0 = kit_uv.verify(objs, res, uv="UVMap", margin=0, group_margin=0)
        sets[s] = dict(res=res, margin=[m, g], verify=v, overlap_px=v0["px_closer_than_group_margin"])
        print("UV", s, sets[s], flush=True)
        if v["out_of_square"] or v0["px_closer_than_group_margin"]:
            P.append(f"{s}: острова за квадратом / налезают — {v}, {v0}")
    rep["sets"] = sets
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("CHECK", "проблем:", len(P), "объектов", rep["objects"], "/", rep["objects_ref"], "треугольников", tris, "/",
          rep["tris_ref"], flush=True)
    for p in P[:40]:
        print("  ", p)


if __name__ == "__main__":
    if "--" in sys.argv:
        a = sys.argv[sys.argv.index("--") + 1:]
    else:
        a = sys.argv[1:]
    if a[0] == "compare":
        compare(a[1], a[2])
    elif a[0] == "rig":
        rig(a[1])
    else:
        uv_check(a[1])
