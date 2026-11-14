# «Частокол»: развёртка принятой high-poly под Substance Painter — один набор текстур на процесс (наборы идут
# параллельно), результат — массивы UV по сеткам в <WORK>/uv/<набор>.npz; в файл формы их пишет tex_uv_apply.py.
# Порядок (как у АСТЕН-919, tools/asten919/tex_uv.py): острова по изломам (Smart UV) → швы по их границам → каждый
# остров заново по швам (Minimum Stretch; где хуже — остаётся проекция) → длинные ленты (проволока пружин, ствол)
# режутся на куски → укладка asset_kit.uv.layout (ровная плотность, отступы по целым пикселям) → проверка растром.
# Изнанка коробок для ленты и канал ствола получают сторону острова tex_sets.INNER_K — видимое плотнее.
# Укладка всегда в сетке 4096: у наборов 8192 отступы в пикселях вдвое больше, привязка к пикселю та же.
# blender -b "<Частокол_геометрия_v03.blend>" --factory-startup --python-exit-code 1 --python tools/pkp/tex_uv.py -- <набор>
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
PACK = 4096
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
    ok = a3 > 1e-14
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
    """Ленту длиннее max_len (м) — на куски не длиннее piece поперёк её главной оси (иначе укладчик ужимает весь
    атлас, чтобы она влезла). Куски разнесены в UV — шов между ними."""
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    a3 = m.tri_a3[isl.tris].sum()
    if a2 <= 1e-16 or a3 <= 1e-16:
        return 0
    p = (uv[isl.loops] - uv[isl.loops].mean(0)) * math.sqrt(a3 / a2)
    w, v = np.linalg.eigh(np.cov(p.T))
    t_loop = p @ v[:, int(np.argmax(w))]
    span = float(t_loop.max() - t_loop.min())
    if span <= max_len:
        return 0
    nb = int(math.ceil(span / piece))
    t0 = float(t_loop.min())
    # центр грани вдоль оси — средним по её петлям (векторно)
    loops = np.asarray(isl.loops)
    tl = np.zeros(len(m.uv))
    tl[loops] = t_loop
    polys = np.asarray(isl.polys)
    ls, lt = m.ls[polys].astype(np.int64), m.lt[polys].astype(np.int64)
    idx = np.repeat(ls, lt) + (np.arange(int(lt.sum())) - np.repeat(np.cumsum(lt) - lt, lt))
    tc = np.add.reduceat(tl[idx], np.concatenate([[0], np.cumsum(lt)[:-1]])) / lt
    b = np.minimum(nb - 1, ((tc - t0) / span * nb).astype(np.int64))
    uv[idx, 0] += np.repeat(2.0 * b, lt)
    return nb


def split_ring(m, isl, uv, parts=4):
    """Кольцо (ребро охлаждения ствола: остров с пустой серединой — доля площади в описанном квадрате мала) — на
    четверти дуги по углу вокруг середины: дуги вкладываются друг в друга, середина кольца не пропадает."""
    lo, hi = uv[isl.loops].min(0), uv[isl.loops].max(0)
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    box = float(np.prod(hi - lo))
    if box <= 1e-16 or a2 / box > 0.35 or len(isl.polys) < 24:
        return 0
    c = 0.5 * (lo + hi)
    polys = np.asarray(isl.polys)
    ls, lt = m.ls[polys].astype(np.int64), m.lt[polys].astype(np.int64)
    idx = np.repeat(ls, lt) + (np.arange(int(lt.sum())) - np.repeat(np.cumsum(lt) - lt, lt))
    st = np.concatenate([[0], np.cumsum(lt)[:-1]])
    pc = np.stack([np.add.reduceat(uv[idx, k], st) / lt for k in (0, 1)], 1)
    # центр кольца должен лежать в пустоте — иначе это не кольцо, а изогнутая лента
    r = np.hypot(pc[:, 0] - c[0], pc[:, 1] - c[1])
    if r.min() < 0.25 * r.max():
        return 0
    ang = np.arctan2(pc[:, 1] - c[1], pc[:, 0] - c[0])
    b = np.minimum(parts - 1, ((ang + math.pi) / (2 * math.pi) * parts).astype(np.int64))
    uv[idx, 1] += np.repeat(3.0 * (b + 1), lt)
    return parts


def unwrap(um, angle, max_len, piece, rings=False):
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
        m.uv = res
        nr = 0
        for isl in kit_uv.islands_of([m]):
            n = split_long(m, isl, res, max_len, piece)
            if n:
                print(f"   {o.name}: лента {len(isl.polys)} граней → {n} кусков", flush=True)
            elif rings:
                nr += bool(split_ring(m, isl, res))
        if nr:
            print(f"   {o.name}: колец на четверти — {nr}", flush=True)
        _set_uv(o.data, res)
    return kept, total, sorted(worst, reverse=True)[:6]


def classes_of(objs):
    """Классы граней: изнанка коробок для ленты (нормаль к центру габарита детали) — ROOMY, канал ствола (ближе
    4,5 мм к оси, нормаль к оси) — HIDDEN; остальное видимое."""
    out = []
    for o in objs:
        m = kit_uv._Mesh(o, UV)
        cls = np.full(m.npoly, kit_uv.VISIBLE, np.int32)
        if o.name.startswith(("Box100_Body", "Box200_Body", "Box100_Lid", "Box200_Lid")):
            c = 0.5 * (m.co.min(0) + m.co.max(0))
            inward = ((m.poly_c - c) * m.poly_n).sum(1) < 0.0
            cls[inward] = kit_uv.ROOMY
        if o.name == "Barrel":
            r = np.hypot(m.poly_c[:, 1], m.poly_c[:, 2])
            rad = np.stack([np.zeros(m.npoly), m.poly_c[:, 1], m.poly_c[:, 2]], 1) / np.maximum(r, 1e-9)[:, None]
            bore = (r < 0.0045) & ((rad * m.poly_n).sum(1) < -0.5)
            cls[bore] = kit_uv.HIDDEN
        a = m.poly_a3
        print(f"   {o.name}: изнанка {a[cls == kit_uv.ROOMY].sum() / a.sum():.0%}, канал "
              f"{a[cls == kit_uv.HIDDEN].sum() / a.sum():.0%}", flush=True)
        out.append(cls)
    return out


def dump_tris(path, objs):
    names, tri, obj = [], [], []
    for i, o in enumerate(objs):
        m = kit_uv._Mesh(o, UV)
        names.append(o.name)
        tri.append(m.uv[m.tri].astype(np.float32))
        obj.append(np.full(len(m.tri), i, np.int32))
    np.savez_compressed(path, names=np.array(names), tri=np.concatenate(tri), obj=np.concatenate(obj))


def main():
    s = sys.argv[sys.argv.index("--") + 1]
    res, aim, names = T.SETS[s]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    # в слой вида всё: правка сеток в режиме редактирования требует объект в слое (коробка 200, кронштейны выключены)
    def _show(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            _show(ch)
    _show(bpy.context.view_layer.layer_collection)
    objs, seen = [], set()
    for n in names:
        o = bpy.data.objects[n]
        if o.data.name in seen:
            continue
        seen.add(o.data.name)
        objs.append(o)
    keep = {o.data.name for o in objs}
    # остальные сетки — прочь (память: в файле 15 млн треугольников; файл не сохраняется)
    for me in list(bpy.data.meshes):
        if me.name not in keep:
            bpy.data.meshes.remove(me)
    for o in objs:
        o.hide_set(False)
        o.hide_viewport = False
        sc = o.matrix_world.to_scale()
        if max(abs(v - 1.0) for v in sc) > 1e-3:
            print(f"   внимание: масштаб {o.name} {tuple(round(v, 4) for v in sc)}", flush=True)
    print(f"SET {s}: {len(objs)} сеток, {sum(len(o.data.polygons) for o in objs)} граней, загрузка "
          f"{time.time() - t0:.0f} с", flush=True)
    kept, total, worst = unwrap(objs, T.ANGLES.get(s, T.ANGLE), 0.95 * res / aim / 1000.0, 0.45 * res / aim / 1000.0,
                                rings=s in T.RING_SPLIT)
    t1 = time.time()
    print(f"   развёртка {t1 - t0:.0f} с, проекция оставлена {kept}/{total}", flush=True)
    classes = classes_of(objs)
    kit_uv.CLASS_K[kit_uv.ROOMY] = T.INNER_K["box"]
    kit_uv.CLASS_K[kit_uv.HIDDEN] = T.INNER_K["bore"]
    rep = kit_uv.layout(objs, PACK, uv=UV, classes=classes, stack=False, margin=T.PADDING_PX,
                        group_margin=T.GROUP_PX, log=lambda *x: print("  ", *x, flush=True))
    ver = kit_uv.verify(objs, PACK, uv=UV, margin=T.PADDING_PX, group_margin=T.GROUP_PX, classes=classes)
    dump_tris(f"{OUT}/{s}_tris.npz", objs)
    arrays = {}
    for o in objs:
        arrays["uv__" + o.data.name] = _uv(o.data).astype(np.float32)
        arrays["n__" + o.data.name] = np.array([len(o.data.loops)], np.int64)
    np.savez_compressed(f"{OUT}/{s}.npz", **arrays)
    report = dict(set=s, res=res, aim_px_mm=aim, meshes=[o.data.name for o in objs], islands=rep["islands"],
                  fill=rep["fill"], px_mm=round(rep["px_mm"] * res / PACK, 2), inner_k=T.INNER_K,
                  projection_kept=f"{kept}/{total}", worst_projection=worst, verify=ver,
                  unwrap_sec=round(t1 - t0), sec=round(time.time() - t0))
    with open(f"{OUT}/{s}_report.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("DONE", s, json.dumps({k: report[k] for k in ("islands", "fill", "px_mm", "sec")}), flush=True)


if __name__ == "__main__":
    main()
