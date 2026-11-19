# ВЕРАС-54 v14: треугольники деталей с развёрткой, положением и нормалью — для масок маркировки в развёртке (заливка
# гравировок краской: «ВЕРАС-54», «5,45×39», «АВ / 2 / ОД» на коробке, «0547» на раме, шкала планки целика, цифры окон
# магазина). По образцу tools/pkp/tex_geo_dump.py.
# blender -b "<ВЕРАС-54_развёртка_v14_01.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_geo_dump.py -- <папка> Деталь[@local] …
# Выход: <папка>/<Деталь>_geo.npz — uv (N, 3, 2), pos (N, 3, 3) в мм в осях автомата (положение по умолчанию рига, как
# в файле; «@local» — в осях самой сетки), nrm (N, 3) нормаль грани, set — набор, res — разрешение набора.
# Карты в пикселях развёртки: --raster <пикс> — ещё <Деталь>_pos.npy (H, W, 3) мм и _nrm.npy (H, W, 3), _mask.npy
# (H, W) — растром по треугольникам (центры пикселей), 0 вне островов детали.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
import tex_sets as T  # noqa: E402


def raster(uv, pos, nrm, size):
    """Положение и нормаль в каждом пикселе развёртки: барицентрика по треугольникам, центры пикселей."""
    P = np.zeros((size, size, 3), np.float32)
    N = np.zeros((size, size, 3), np.float32)
    M = np.zeros((size, size), np.uint8)
    px = uv * size - 0.5
    for t in range(len(px)):
        a, b, c = px[t]
        x0, x1 = int(max(0, np.floor(min(a[0], b[0], c[0])))), int(min(size - 1, np.ceil(max(a[0], b[0], c[0]))))
        y0, y1 = int(max(0, np.floor(min(a[1], b[1], c[1])))), int(min(size - 1, np.ceil(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
        l3 = 1.0 - l1 - l2
        ins = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        if not ins.any():
            continue
        yy, xx = ys[ins], xs[ins]
        w = np.stack([l1[ins], l2[ins], l3[ins]], 1)
        P[yy, xx] = w @ pos[t]
        N[yy, xx] = nrm[t]
        M[yy, xx] = 1
    return P, N, M


a = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(a[0])
items = a[1:]
size = 0
if "--raster" in items:
    i = items.index("--raster")
    size = int(items[i + 1])
    items = items[:i] + items[i + 2:]
os.makedirs(out, exist_ok=True)
for item in items:
    local = item.endswith("@local")
    name = item[:-6] if local else item
    o = bpy.data.objects[name]
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    loops = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("loops", loops)
    verts = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", verts)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    mw = np.eye(4) if local else np.array(o.matrix_world, np.float64)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].uv.foreach_get("vector", uv)
    pos = co[verts].reshape(n, 3, 3) * 1000.0
    nrm = np.cross(pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
    s = o.get("v14_set", T.set_of(name) or "")
    res = T.SETS[s][0] if s in T.SETS else 0
    uvt = uv.reshape(-1, 2)[loops].reshape(n, 3, 2)
    tag = T.sp_name(name)
    np.savez_compressed(os.path.join(out, tag + "_geo.npz"), uv=uvt, pos=pos.astype(np.float32),
                        nrm=nrm.astype(np.float32), set=s, res=res, obj=name)
    print("GEO", tag, n, "треугольников, набор", s, res, flush=True)
    if size:
        P, N, M = raster(uvt.astype(np.float64), pos, nrm, size)
        np.save(os.path.join(out, tag + "_pos.npy"), P)
        np.save(os.path.join(out, tag + "_nrm.npy"), N)
        np.save(os.path.join(out, tag + "_mask.npy"), M)
        print("RASTER", tag, size, int(M.sum()), "пикселей", flush=True)
