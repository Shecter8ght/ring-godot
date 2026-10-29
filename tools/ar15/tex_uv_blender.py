# AR-15 «ГРАНЬ-15»: производственная развёртка в Blender. RizomUV 2024.1 на этой сетке не справился (29.10: на
# булевых многоугольниках и гранях нулевой площади острова схлопывались в круги с наложениями, программа падала на
# Unfold / Optimize) — по слову владельца развёртка «как раньше», в Blender.
# Порядок на набор текстур (tex_sets.SETS): острова по изломам (Smart UV, как у прежних стволов) → швы по их границам
# → каждый остров развёрнут заново по швам без проекционных искажений (Minimum Stretch; где вышло хуже — остаётся
# проекция) → укладка модулем проекта asset_kit.uv.layout (ровная плотность набора, отступы по целым пикселям) →
# независимая проверка растром (asset_kit.uv.verify). Геометрия, порядок граней, риг и AR15_Controls не меняются.
# blender --background <AR-15_геометрия_v06.blend> --factory-startup --python-exit-code 1 --python tools/ar15/tex_uv_blender.py -- [out.blend] [набор,набор]
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402
import tex_sets as T  # noqa: E402
from tex_uv import set_objects, unique_meshes  # noqa: E402

UV = "UVMap"
ANGLE = 60.0             # излом, по которому Smart UV делит острова (как game_lp у стволов)
# рукоять: угол шире — меньше швов на площадках и выступах под пальцы; бугорки рифления — замкнутые оболочки
# в самой геометрии, каждая своим островом (~7300), их без правки сетки не объединить
ANGLES = {"grip": 85.0}
PX_MM_MIN = 12.0         # остров длиннее 1.2 стороны атласа при такой плотности режется на куски (проволока пружин;
#                          ниже порог резал и фаски цевья — укладка выходила хуже)
OUT = T.WORK + "/bl"


def _uv(me):
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[UV].uv.foreach_get("vector", a)
    return a.reshape(-1, 2).astype(np.float64)


def _set_uv(me, uv):
    me.uv_layers[UV].uv.foreach_set("vector", uv.astype(np.float32).ravel())
    me.update()


def _stretch(m, isl, uv):
    """Доля площади острова с плотностью дальше ±25 % от медианы острова и доля вывернутых треугольников."""
    q = uv[m.tri[isl.tris]]
    a2 = 0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1]) - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))
    a3 = m.tri_a3[isl.tris]
    ok = a3 > 1e-12
    if not ok.any():
        return 0.0, 0.0
    w = a3[ok] / a3[ok].sum()
    s = np.sign(np.median(a2[ok])) or 1.0
    flip = float(w[(a2[ok] * s) <= 0].sum())
    r = np.sqrt(np.abs(a2[ok]) / a3[ok])
    med = np.median(r[r > 0]) if (r > 0).any() else 1.0
    bad = float(w[np.abs(np.log(np.maximum(r, 1e-12) / med)) > math.log(1.25)].sum())
    return bad, flip


def split_long(m, isl, uv, max_len):
    """Длинную ленту (проволока пружины, развёрнутая во всю длину витков, ~1.4 м у буферной) — на куски не длиннее
    max_len (м) поперёк её главной оси: иначе укладчик ужимает весь атлас, чтобы она влезла. Куски разнесены в UV —
    шов между ними; укладка потом ставит каждый на своё место."""
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    a3 = m.tri_a3[isl.tris].sum()
    if a2 <= 1e-14 or a3 <= 1e-14:
        return 0
    p = (uv[isl.loops] - uv[isl.loops].mean(0)) * math.sqrt(a3 / a2)
    w, v = np.linalg.eigh(np.cov(p.T))
    t_loop = p @ v[:, int(np.argmax(w))]
    span = float(t_loop.max() - t_loop.min())
    nb = int(math.ceil(span / max_len))
    if nb <= 1:
        return 0
    pos = {int(li): float(t) for li, t in zip(isl.loops, t_loop)}
    t0 = float(t_loop.min())
    for pi in isl.polys:
        ls, lt = int(m.ls[pi]), int(m.lt[pi])
        tc = sum(pos[li] for li in range(ls, ls + lt)) / lt
        b = min(nb - 1, int((tc - t0) / span * nb))
        uv[ls:ls + lt, 0] += 2.0 * b
    return nb


def unwrap(um, angle=ANGLE, max_len=None):
    for o in um:
        me = o.data
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name=UV)
    kit_uv.smart_unwrap(um, uv=UV, angle=math.radians(angle))
    proj = {o.name: _uv(o.data) for o in um}
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    # остров за островом: развёрнутый или проекция — что ровнее (развёртка иногда выворачивает остров на гранях
    # нулевой площади)
    kept = total = 0
    worst = []
    for o in um:
        m = kit_uv._Mesh(o, UV)
        un = m.uv.copy()
        pj = proj[o.name]
        res = un.copy()
        for isl in kit_uv.islands_of([m]):
            b1, f1 = _stretch(m, isl, un)
            b0, f0 = _stretch(m, isl, pj)
            total += 1
            if f1 > 0.001 or b1 > b0 + 0.02:
                res[isl.loops] = pj[isl.loops]
                kept += 1
                worst.append((round(max(b0, f0), 3), o.name))
        if max_len:
            m.uv = res
            for isl in kit_uv.islands_of([m]):
                n = split_long(m, isl, res, max_len)
                if n:
                    print(f"   {o.name}: лента {len(isl.polys)} граней → {n} кусков")
        _set_uv(o.data, res)
    return kept, total, sorted(worst, reverse=True)[:6]


def dump_obj(path, um):
    """OBJ с UV (как у RizomUV) для замера tools/ar15/tex_uv_check.py: мм, вершины и грани исходные."""
    with open(path, "w", encoding="ascii", newline="\n") as f:
        vb = vtb = 1
        for o in um:
            me = o.data
            f.write(f"o {me.name}\n")
            for v in me.vertices:
                c = v.co * 1000.0
                f.write(f"v {c.x:.5f} {c.y:.5f} {c.z:.5f}\n")
            uv = _uv(me)
            for u in uv:
                f.write(f"vt {u[0]:.6f} {u[1]:.6f}\n")
            for p in me.polygons:
                f.write("f " + " ".join(f"{vb + me.loops[li].vertex_index}/{vtb + li}" for li in p.loop_indices) + "\n")
            vb += len(me.vertices)
            vtb += len(me.loops)


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = a[0] if a else T.UV_BLEND
    only = a[1].split(",") if len(a) > 1 else None
    os.makedirs(OUT, exist_ok=True)
    sets, loose = set_objects()
    if loose:
        raise RuntimeError("детали без набора: " + ", ".join(loose))
    report = {}
    for s, objs in sets.items():
        if only and s not in only:
            continue
        t0 = time.time()
        res = T.SETS[s][0]
        um = unique_meshes(objs)
        kept, total, worst = unwrap(um, ANGLES.get(s, ANGLE), 1.2 * res / PX_MM_MIN / 1000.0)
        margin = T.PADDING_PX if res >= 4096 else 8
        rep = kit_uv.layout(um, res, uv=UV, stack=False, margin=margin, group_margin=6,
                            log=lambda *x: print("  ", *x))
        ver = kit_uv.verify(um, res, uv=UV, margin=margin, group_margin=6)
        dump_obj(f"{OUT}/{s}_out.obj", um)
        for o in objs:
            o["ar15_set"] = s
            o["ar15_mat"] = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ""
        report[s] = dict(res=res, islands=rep["islands"], fill=rep["fill"], px_mm=rep["px_mm"],
                         projection_kept=f"{kept}/{total}", worst_projection=worst, verify=ver,
                         sec=round(time.time() - t0))
        print("SET", s, json.dumps(report[s], ensure_ascii=False))
    cart = bpy.data.objects["Cartridge_556"]
    for o in bpy.data.objects:
        if o.type == "MESH" and "ar15_set" not in o and o.data == cart.data:
            o["ar15_set"] = cart.get("ar15_set", "rounds")
            o["ar15_mat"] = cart.get("ar15_mat", "Brass")
    with open(f"{OUT}/report{'_' + '_'.join(only) if only else ''}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    main()
