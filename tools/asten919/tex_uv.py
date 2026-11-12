# АСТЕН-919: развёртка принятой high-poly под Substance Painter (по образцу tools/ar15/tex_uv_blender.py).
# Порядок на набор текстур (tex_sets.SETS): острова по изломам (Smart UV) → швы по их границам → каждый остров развёрнут
# заново по швам (Minimum Stretch; где вышло хуже — остаётся проекция) → длинные ленты (проволока пружин) режутся на
# куски → укладка модулем проекта asset_kit.uv.layout (ровная плотность набора, отступы по целым пикселям) →
# независимая проверка растром (asset_kit.uv.verify). Геометрия, нормали из поля, родители и ASTEN919_Controls не
# меняются.
# blender --background <АСТЕН-919_геометрия_v03.blend> --factory-startup --python-exit-code 1 --python tools/asten919/tex_uv.py -- [out.blend] [набор,набор]
# Повтор отдельных наборов — на уже развёрнутом файле (остальные наборы остаются как есть).
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

UV = "UVMap"
PX_MM_AIM = 20.0         # ожидаемая плотность набора: остров длиннее 0.95 стороны атласа при ней режется на куски
#                          по 0.45 стороны (проволока пружин; иначе лента ужимает весь атлас)
OUT = T.WORK + "/uv"


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


def split_long(m, isl, uv, max_len, piece):
    """Ленту длиннее max_len (м; проволока пружины, развёрнутая во всю длину витков) — на куски не длиннее piece
    поперёк её главной оси: иначе укладчик ужимает весь атлас, чтобы она влезла. Куски разнесены в UV — шов между
    ними. Борта затвора и магазина короче порога и остаются целыми."""
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
    if span <= max_len:
        return 0
    nb = int(math.ceil(span / piece))
    pos = {int(li): float(t) for li, t in zip(isl.loops, t_loop)}
    t0 = float(t_loop.min())
    for pi in isl.polys:
        ls, lt = int(m.ls[pi]), int(m.lt[pi])
        tc = sum(pos[li] for li in range(ls, ls + lt)) / lt
        b = min(nb - 1, int((tc - t0) / span * nb))
        uv[ls:ls + lt, 0] += 2.0 * b
    return nb


def unwrap(um, angle, max_len=None, piece=None):
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
    # остров за островом: развёрнутый или проекция — что ровнее
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
                n = split_long(m, isl, res, max_len, piece)
                if n:
                    print(f"   {o.name}: лента {len(isl.polys)} граней → {n} кусков")
        _set_uv(o.data, res)
    return kept, total, sorted(worst, reverse=True)[:6]


def dump_tris(path, objs):
    """Треугольники развёртки по деталям — для картинки раскладки (tex_uv_view.py, обычный Python)."""
    names, tri, obj = [], [], []
    for i, o in enumerate(objs):
        m = kit_uv._Mesh(o, UV)
        t = m.uv[m.tri].astype(np.float32)
        names.append(o.name)
        tri.append(t)
        obj.append(np.full(len(t), i, np.int32))
    np.savez_compressed(path, names=np.array(names), tri=np.concatenate(tri), obj=np.concatenate(obj))


def set_objects():
    """{набор: [объекты с разными сетками]}; копии патрона в магазине идут за Round_9x19_loose."""
    out = {s: [] for s in T.SETS}
    loose = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        s = T.set_of(o.name)
        if s is None:
            if o.data.name != T.SHARED:
                loose.append(o.name)
        else:
            out[s].append(o)
    return out, loose


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = a[0] if a else T.UV_BLEND
    only = a[1].split(",") if len(a) > 1 else None
    os.makedirs(OUT, exist_ok=True)
    # все коллекции видимы: правка сеток в режиме редактирования требует объект в слое вида
    for c in bpy.data.collections:
        c.hide_viewport = False
    keep = {}                 # исходная видимость: после развёртки возвращается (ствол с резьбой выключен)

    def _show(lc):
        keep[lc.name] = (lc.exclude, lc.hide_viewport)
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            _show(ch)
    _show(bpy.context.view_layer.layer_collection)
    for o in bpy.data.objects:
        o.hide_set(False)
        o.hide_viewport = False
    sets, loose = set_objects()
    if loose:
        raise RuntimeError("детали без набора: " + ", ".join(loose))
    report = {}
    for s, objs in sets.items():
        if only and s not in only:
            continue
        t0 = time.time()
        res = T.SETS[s][0]
        kept, total, worst = unwrap(objs, T.ANGLES.get(s, T.ANGLE), 0.95 * res / PX_MM_AIM / 1000.0,
                                   0.45 * res / PX_MM_AIM / 1000.0)
        t1 = time.time()
        margin = T.PADDING_PX
        rep = kit_uv.layout(objs, res, uv=UV, stack=False, margin=margin, group_margin=6,
                            log=lambda *x: print("  ", *x))
        ver = kit_uv.verify(objs, res, uv=UV, margin=margin, group_margin=6)
        dump_tris(f"{OUT}/{s}_tris.npz", objs)
        for o in objs:
            o["asten_set"] = s
            o["asten_mat"] = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ""
        report[s] = dict(res=res, islands=rep["islands"], fill=rep["fill"], px_mm=rep["px_mm"],
                         projection_kept=f"{kept}/{total}", worst_projection=worst, verify=ver,
                         unwrap_sec=round(t1 - t0), sec=round(time.time() - t0))
        print("SET", s, json.dumps(report[s], ensure_ascii=False))
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data.name == T.SHARED:
            o["asten_set"] = "magazine"
            o["asten_mat"] = "Brass"
    with open(f"{OUT}/report{'_' + '_'.join(only) if only else ''}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    def _restore(lc):                 # родитель раньше детей: exclude родителя переписывает детей
        lc.exclude, lc.hide_viewport = keep[lc.name]
        for ch in lc.children:
            _restore(ch)
    _restore(bpy.context.view_layer.layer_collection)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    main()
