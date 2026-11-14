# «Частокол»: треугольники деталей с развёрткой, положением и нормалью — для масок маркировки в развёртке (tex_marks.py).
# blender -b "<Частокол_развёртка_v01.blend>" --factory-startup --python-exit-code 1 --python tools/pkp/tex_geo_dump.py -- <папка> Деталь[:материал] …
# Выход: <папка>/<Деталь>[_<материал>]_geo.npz — uv (N, 3, 2), pos (N, 3, 3) в мм в осях пулемёта (положение как
# в файле), nrm (N, 3), set — набор. «:материал» — только грани этого материала формы (куски патрона); «@local» — в осях
# самой сетки (патрон построен вдоль X от донца — одна сетка на все копии ленты).
import os
import sys

import bpy
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
os.makedirs(out, exist_ok=True)
for item in a[1:]:
    local = item.endswith("@local")
    item = item[:-6] if local else item
    name, _, mat = item.partition(":")
    o = bpy.data.objects[name]
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    loops = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("loops", loops)
    verts = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", verts)
    mi = np.empty(n, np.int32)
    me.loop_triangles.foreach_get("material_index", mi)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    mw = np.eye(4) if local else np.array(o.matrix_world, np.float64)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].uv.foreach_get("vector", uv)
    pos = co[verts].reshape(n, 3, 3) * 1000.0
    e1, e2 = pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0]
    nrm = np.cross(e1, e2)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
    sel = np.ones(n, bool)
    if mat:
        names = [sl.material.name if sl.material else "" for sl in o.material_slots]
        sel = mi == names.index(mat)
    tag = name + (f"_{mat}" if mat else "")
    np.savez_compressed(os.path.join(out, tag + "_geo.npz"), uv=uv.reshape(-1, 2)[loops].reshape(n, 3, 2)[sel],
                        pos=pos[sel].astype(np.float32), nrm=nrm[sel].astype(np.float32), set=o.get("pkp_set", ""))
    print("GEO", tag, int(sel.sum()), "треугольников")
