# АСТЕН-919: треугольники деталей с развёрткой, положением и нормалью — для масок в развёртке (tex_marks.py).
# blender --background <АСТЕН-919_развёртка_v01.blend> --factory-startup --python-exit-code 1 --python tools/asten919/tex_geo_dump.py -- <папка> Деталь [Деталь …]
# Выход: <папка>/<Деталь>_geo.npz — uv (N, 3, 2), pos (N, 3, 3) в мм в осях модели (исходное положение), nrm (N, 3).
import os
import sys

import bpy
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
os.makedirs(out, exist_ok=True)
for name in a[1:]:
    o = bpy.data.objects[name]
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    loops = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("loops", loops)
    verts = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", verts)
    nrm = np.empty(n * 3, np.float32)
    me.loop_triangles.foreach_get("normal", nrm)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].uv.foreach_get("vector", uv)
    # сетки построены в осях модели (родитель — пустышка без сдвига), единицы — метры
    pos = co.reshape(-1, 3)[verts].reshape(n, 3, 3) * 1000.0
    np.savez_compressed(os.path.join(out, name + "_geo.npz"), uv=uv.reshape(-1, 2)[loops].reshape(n, 3, 2), pos=pos,
                        nrm=nrm.reshape(n, 3), set=o.get("asten_set", ""))
    print("GEO", name, n, "треугольников")
