# Цевьё Dolinskyi: треугольники low-poly с развёрткой → npz для масок «мазков» (masks.py): по каждому треугольнику —
# UV трёх углов, положения в мм и нормали углов (с учётом жёстких рёбер).
#   blender --background <развёртка.blend> --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/mesh_dump.py
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "_asset_src", "handguard_dolinskyi", "masks", "mesh.npz")


def main():
    o = bpy.data.objects["handguard_low"]
    me = o.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    n = len(tris)
    loops = np.empty(n * 3, np.int32)
    tris.foreach_get("loops", loops)
    verts = np.empty(n * 3, np.int32)
    tris.foreach_get("vertices", verts)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) * 1000.0
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    nrm = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(-1, 3)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(OUT, uv=uv[loops].reshape(n, 3, 2), pos=co[verts].reshape(n, 3, 3),
                        nrm=nrm[loops].reshape(n, 3, 3))
    print("DUMP", n, OUT)


main()
