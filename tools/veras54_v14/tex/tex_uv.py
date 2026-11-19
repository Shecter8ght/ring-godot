# ВЕРАС-54 v14: развёртка принятой high-poly под Substance Painter — один набор текстур на процесс (наборы идут
# параллельно, не больше трёх Blender сразу), результат — массивы UV по сеткам в <WORK>/uv/<набор>.npz; в файл
# развёртки их пишет tex_uv_apply.py. Порядок — как у «Частокола» (tools/pkp/tex_uv.py): острова по изломам
# (Smart UV) → швы по их границам → каждый остров заново по швам (Minimum Stretch; где хуже — остаётся проекция) →
# длинные ленты режутся на куски, кольца — на четверти дуги → укладка asset_kit.uv.layout (ровная плотность, отступы
# по целым пикселям) → проверка растром. Изнанка оболочек и каналы — tex_sets.INNER (сторона острова INNER_K).
# Укладка — в сетке своего разрешения набора, отступы PAD[разрешение].
# blender -b "<ВЕРАС-54_геометрия_v14_04.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_uv.py -- <набор>
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402
import tex_sets as T  # noqa: E402

UV = "UVMap"
OUT = T.WORK + "/uv"
# отступы (между деталями, внутри группы одной детали) в пикселях набора
PAD = {4096: (12, 6), 2048: (8, 4), 1024: (6, 3)}


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


def _poly_loops(m, polys):
    ls, lt = m.ls[polys].astype(np.int64), m.lt[polys].astype(np.int64)
    idx = np.repeat(ls, lt) + (np.arange(int(lt.sum())) - np.repeat(np.cumsum(lt) - lt, lt))
    return idx, lt


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
    tl = np.zeros(len(m.uv))
    tl[np.asarray(isl.loops)] = t_loop
    idx, lt = _poly_loops(m, np.asarray(isl.polys))
    tc = np.add.reduceat(tl[idx], np.concatenate([[0], np.cumsum(lt)[:-1]])) / lt
    b = np.minimum(nb - 1, ((tc - t0) / span * nb).astype(np.int64))
    uv[idx, 0] += np.repeat(2.0 * b, lt)
    return nb


def split_ring(m, isl, uv, parts=4):
    """Кольцо (остров с пустой серединой — доля площади в описанном квадрате мала) — на четверти дуги по углу вокруг
    середины: дуги вкладываются друг в друга, середина кольца не пропадает."""
    lo, hi = uv[isl.loops].min(0), uv[isl.loops].max(0)
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    box = float(np.prod(hi - lo))
    if box <= 1e-16 or a2 / box > 0.35 or len(isl.polys) < 24:
        return 0
    c = 0.5 * (lo + hi)
    idx, lt = _poly_loops(m, np.asarray(isl.polys))
    st = np.concatenate([[0], np.cumsum(lt)[:-1]])
    pc = np.stack([np.add.reduceat(uv[idx, k], st) / lt for k in (0, 1)], 1)
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
    """Классы граней по правилам tex_sets.INNER: изнанка оболочек — ROOMY, каналы — HIDDEN; остальное видимое."""
    out = []
    for o in objs:
        m = kit_uv._Mesh(o, UV)
        cls = np.full(m.npoly, kit_uv.VISIBLE, np.int32)
        rule = T.INNER.get(o.name)
        lo, hi = m.co.min(0), m.co.max(0)
        c = 0.5 * (lo + hi)
        if rule == "shell":
            # стенка смотрит к средней плоскости детали и лежит глубже наружной стенки (наружная — у края габарита)
            dy = m.poly_c[:, 1] - c[1]
            half = 0.5 * (hi[1] - lo[1])
            inward = (np.abs(m.poly_n[:, 1]) > 0.6) & (m.poly_n[:, 1] * dy < 0.0) & (np.abs(dy) < half - 0.0006)
            cls[inward] = kit_uv.ROOMY
        elif isinstance(rule, tuple) and rule[0] == "bore":
            rr = rule[1] * 0.001
            yz = m.poly_c[:, 1:] - c[1:]
            r = np.hypot(yz[:, 0], yz[:, 1])
            rad = np.concatenate([np.zeros((m.npoly, 1)), yz], 1) / np.maximum(r, 1e-9)[:, None]
            bore = (r < rr) & ((rad * m.poly_n).sum(1) < -0.5)
            cls[bore] = kit_uv.HIDDEN
        a = m.poly_a3
        if rule:
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


def prepare(names):
    """Детали набора в слой вида; патрон в патроннике — в полный размер (привод live_round держит его × 0,001);
    остальные сетки — прочь (память; файл не сохраняется)."""
    def _show(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            _show(ch)
    _show(bpy.context.view_layer.layer_collection)
    b = bpy.data.objects.get("Chambered_Bullet")
    if b is not None and b.animation_data:
        for d in list(b.animation_data.drivers):
            if d.data_path == "delta_scale":
                b.animation_data.drivers.remove(d)
        b.delta_scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    objs = [bpy.data.objects[n] for n in names]
    keep = {o.data.name for o in objs}
    for me in list(bpy.data.meshes):
        if me.name not in keep:
            bpy.data.meshes.remove(me)
    for o in objs:
        o.hide_set(False)
        o.hide_viewport = False
        sc = o.matrix_world.to_scale()
        if max(abs(v - 1.0) for v in sc) > 1e-3:
            print(f"   внимание: масштаб {o.name} {tuple(round(v, 4) for v in sc)}", flush=True)
    return objs


def main():
    s = sys.argv[sys.argv.index("--") + 1]
    res, aim, names = T.SETS[s]
    margin, gmargin = PAD[res]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    objs = prepare(names)
    print(f"SET {s}: {len(objs)} сеток, {sum(len(o.data.polygons) for o in objs)} граней, загрузка "
          f"{time.time() - t0:.0f} с", flush=True)
    kept, total, worst = unwrap(objs, T.ANGLES.get(s, T.ANGLE), 0.95 * res / aim / 1000.0, 0.45 * res / aim / 1000.0,
                                rings=s in T.RING_SPLIT)
    t1 = time.time()
    print(f"   развёртка {t1 - t0:.0f} с, проекция оставлена {kept}/{total}", flush=True)
    classes = classes_of(objs)
    kit_uv.CLASS_K[kit_uv.ROOMY] = T.INNER_K["shell"]
    kit_uv.CLASS_K[kit_uv.HIDDEN] = T.INNER_K["bore"]
    rep = kit_uv.layout(objs, res, uv=UV, classes=classes, stack=False, margin=margin, group_margin=gmargin,
                        log=lambda *x: print("  ", *x, flush=True))
    ver = kit_uv.verify(objs, res, uv=UV, margin=margin, group_margin=gmargin, classes=classes)
    dump_tris(f"{OUT}/{s}_tris.npz", objs)
    arrays = {}
    for o in objs:
        me = o.data
        arrays["uv__" + o.name] = _uv(me).astype(np.float32)
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        arrays["lv__" + o.name] = lv
        g = np.zeros(len(me.polygons), np.int32)
        if "uv_group" in me.attributes:
            me.attributes["uv_group"].data.foreach_get("value", g)
        arrays["grp__" + o.name] = g
        cl = classes[objs.index(o)].astype(np.int8)
        arrays["cls__" + o.name] = cl
    np.savez_compressed(f"{OUT}/{s}.npz", **arrays)
    # острова по деталям
    per = {}
    for o in objs:
        m = kit_uv._Mesh(o, UV)
        per[o.name] = len(kit_uv.islands_of([m]))
    report = dict(set=s, res=res, aim_px_mm=aim, margin_px=margin, group_margin_px=gmargin, objects=names,
                  islands=rep["islands"], islands_by_object=per, fill=rep["fill"], px_mm=rep["px_mm"],
                  inner_k=T.INNER_K, projection_kept=f"{kept}/{total}", worst_projection=worst, verify=ver,
                  loss_margins=rep.get("loss_margins"), loss_empty=rep.get("loss_empty"),
                  unwrap_sec=round(t1 - t0), sec=round(time.time() - t0))
    with open(f"{OUT}/{s}_report.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("DONE", s, json.dumps({k: report[k] for k in ("islands", "fill", "px_mm", "sec")}), flush=True)


if __name__ == "__main__":
    main()
