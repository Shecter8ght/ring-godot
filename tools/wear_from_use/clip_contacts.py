"""Следы использования из данных игры, шаг 1: позы кистей и деталей оружия по кадрам клипа рук.

Из файла клипа (риг FPS_ArmsRig + риг оружия, как собирает tools/veras54_v13/clips/build_clips.py) снимается по каждому кадру:
вершины перчаток (сетка FPS_Arms с арматурой) в осях оружия в покое и матрицы костей оружия — где каждая подвижная деталь
(затвор, магазин, переводчик…) стоит относительно коробки. Касание считает wear_masks.py: точка детали сравнивается
с кистью в осях этой детали, поэтому магазин в руке и рама в отводе дают след на своих местах.

Оси покоя — оси узла VERAS54 (дуло +X, +Y влево стрелка, +Z вверх, метры), в них же лежит high-poly. Кадр = 1/fps.
Метки вершин: сторона (0 — левая, 1 — правая) и область по главной кости: 0 — плечо/предплечье, 1 — ладонь,
2 — основная и средняя фаланги, 3 — ногтевые фаланги (подушечки — отпечатки).

blender --background --factory-startup <клип.blend> --python-exit-code 1 --python tools/wear_from_use/clip_contacts.py -- <выход.npz> [кадр_от кадр_до]
"""
from __future__ import annotations

import sys

import bpy
import numpy as np
from mathutils import Matrix

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
sc = bpy.context.scene
F0, F1 = (int(ARGS[1]), int(ARGS[2])) if len(ARGS) > 2 else (sc.frame_start, sc.frame_end)

arms = bpy.data.objects["FPS_Arms"]
wr = bpy.data.objects["VERAS54_WeaponRig"]
root = bpy.data.objects["VERAS54"]


def region(group: str) -> int:
    g = group.split(".")
    if group.startswith(("upper_arm", "forearm")):
        return 0
    if group.startswith(("hand", "palm")):
        return 1
    if group.startswith(("f_", "thumb")):
        return 3 if g[1] == "03" else 2
    return 0


me = arms.data
nv = len(me.vertices)
side = np.zeros(nv, np.int8)
reg = np.zeros(nv, np.int8)
for v in me.vertices:
    if not v.groups:
        continue
    g = max(v.groups, key=lambda g: g.weight)
    name = arms.vertex_groups[g.group].name
    side[v.index] = 1 if name.endswith(".R") else 0
    reg[v.index] = region(name)
me.calc_loop_triangles()
tris = np.zeros(len(me.loop_triangles) * 3, np.int32)
me.loop_triangles.foreach_get("vertices", tris)
tris = tris.reshape(-1, 3)
# только кисти: треугольник, у которого хоть одна вершина не на плече/предплечье
keep_t = (reg[tris] > 0).any(axis=1)
tris = tris[keep_t]
used = np.unique(tris)
remap = -np.ones(nv, np.int64)
remap[used] = np.arange(len(used))
tris = remap[tris].astype(np.int32)
side_u, reg_u = side[used], reg[used]

bones = [b.name for b in wr.data.bones]
rest = {b.name: b.matrix_local.copy() for b in wr.data.bones}


def np44(m: Matrix) -> np.ndarray:
    return np.array([list(r) for r in m], np.float64)


frames = list(range(F0, F1 + 1))
hand = np.zeros((len(frames), len(used), 3), np.float32)
mats = np.zeros((len(frames), len(bones), 4, 4), np.float64)
for fi, f in enumerate(frames):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    wv = root.matrix_world.copy()
    a = wr.matrix_world.copy()
    lrig = wv.inverted() @ a          # рига относительно VERAS54 (постоянна)
    # кость B: точка в осях покоя VERAS54 → мир в кадре t; затем в оси VERAS54 этого кадра (мир → VERAS54(t))
    m_root = None
    for bi, bn in enumerate(bones):
        pb = wr.pose.bones[bn]
        mb = lrig @ pb.matrix @ rest[bn].inverted() @ lrig.inverted()      # покой → VERAS54(t)
        mats[fi, bi] = np44(mb)
        if bn == "WeaponRoot":
            m_root = mb
    ev = arms.evaluated_get(dg)
    m = ev.to_mesh()
    co = np.zeros(len(m.vertices) * 3, np.float64)
    m.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)[used]
    # мир → оси VERAS54 этого кадра → оси покоя коробки (WeaponRoot)
    tw = np44(m_root.inverted() @ wv.inverted() @ arms.matrix_world)
    hand[fi] = (co @ tw[:3, :3].T + tw[:3, 3]).astype(np.float32)
    # матрицы костей — относительно коробки в этом кадре: деталь B в осях покоя коробки
    inv_root = np.linalg.inv(np44(m_root))
    for bi in range(len(bones)):
        mats[fi, bi] = inv_root @ mats[fi, bi]

# проверка: сетки игровой модели, привязанные к костям, в осях покоя не должны «плыть» между кадрами
check = {}
for o in bpy.data.objects:
    if o.type != "MESH" or o.parent != wr or o.parent_type != "BONE" or len(o.data.vertices) < 20:
        continue
    bi = bones.index(o.parent_bone)
    pts = []
    for f in (frames[0], frames[len(frames) // 2], frames[-1]):
        sc.frame_set(f)
        wv = root.matrix_world
        v = np.array([list(p.co) for p in o.data.vertices[:200]])
        mw = np44(wv.inverted() @ o.matrix_world)
        loc = v @ mw[:3, :3].T + mw[:3, 3]
        fi = frames.index(f)
        # VERAS54(t) → покой детали: (коробка(t) · матрица кости)^-1
        a = wr.matrix_world
        lrig = wv.inverted() @ a
        pr = wr.pose.bones["WeaponRoot"]
        m_root = np44(lrig @ pr.matrix @ rest["WeaponRoot"].inverted() @ lrig.inverted())
        full = m_root @ mats[fi, bi]
        inv = np.linalg.inv(full)
        pts.append(loc @ inv[:3, :3].T + inv[:3, 3])
    check[o.name] = float(max(np.abs(pts[1] - pts[0]).max(), np.abs(pts[2] - pts[0]).max()))
print("REST_DRIFT_M", {k: round(v, 6) for k, v in check.items()}, flush=True)

np.savez_compressed(OUT, hand=hand, tris=tris, side=side_u, region=reg_u, bones=np.array(bones), mats=mats.astype(np.float32),
                    frames=np.array(frames), fps=np.array(sc.render.fps),
                    arms_action=np.array(arms.parent.animation_data.action.name if arms.parent.animation_data and arms.parent.animation_data.action else ""))
print("CLIP_CONTACTS", OUT, len(frames), "кадров,", len(used), "вершин кистей,", len(tris), "треугольников", flush=True)
